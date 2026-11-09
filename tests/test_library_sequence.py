"""Native library phase/input fencing; no Kodi launch or synthetic selection reset."""
import ast
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('library_sequence_runner',ROOT/'tools/render_library.py')
RUNNER=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(RUNNER)
FIXTURE=ast.parse(RUNNER.FIXTURE)


def require(value,message):
    if not value:raise AssertionError(message)


def embedded(name,namespace):
    node=next(node for node in FIXTURE.body if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'library-sequence-fixture','exec',optimize=2),namespace)
    return namespace[name]


class LibrarySequence(unittest.TestCase):
    def setUp(self):
        self.before=dict(case='tv-shows',generation=2,sample=100,parent=10004,native_action_sequence=12)
        self.after=dict(self.before,sample=101,native_action_sequence=13,native_action_id=2)
    def test_input_completion_needs_fresh_same_instance_real_action_callback(self):
        self.assertTrue(RUNNER.native_input_completed(self.after,self.before,2))
        for change in [dict(case='short-row'),dict(generation=3),dict(sample=100),dict(native_action_sequence=12),dict(native_action_id=1)]:
            with self.subTest(change=change):self.assertFalse(RUNNER.native_input_completed(dict(self.after,**change),self.before,2))
    def test_close_ack_rejects_stale_sequence_or_parent_not_actually_restored(self):
        closed=dict(self.before,closed=True,actual_parent=10004,native_action_sequence=13,native_action_id=92)
        self.assertTrue(RUNNER.catalog_close_completed(closed,self.before,92))
        for change in [dict(case='movies'),dict(generation=1),dict(closed=False),dict(actual_parent=13000),dict(parent=13000),dict(native_action_sequence=12),dict(native_action_id=7)]:
            with self.subTest(change=change):self.assertFalse(RUNNER.catalog_close_completed(dict(closed,**change),self.before,92))
    def test_valid_release_still_waits_for_actual_native_parent(self):
        state={'clock':0,'window':13000};events=[]
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);path=base/'catalog-release.json'
            path.write_text(json.dumps(dict(case='short-row',generation=3,after_generation=2,parent=10004)))
            def sleep(_):
                self.assertTrue(path.exists());self.assertFalse(events)
                state['clock']+=.02;state['window']=10004
            await_release=embedded('await_release',{'json':json,'BASE':base,'time':SimpleNamespace(monotonic=lambda:state['clock']),
                'xbmcgui':SimpleNamespace(getCurrentWindowId=lambda:state['window']),'xbmc':SimpleNamespace(sleep=sleep),
                'journal':lambda event,**values:events.append((event,values))})
            await_release('short-row',3,10004)
            self.assertFalse(path.exists())
        self.assertEqual(state['clock'],.02);self.assertEqual(events[0][1]['parent'],10004)
    def test_observer_ack_follows_unchanged_shipped_callback_and_propagates_failure(self):
        events=[]
        class Base:
            def __init__(self,*args,**kwargs):self.closed=False
            def onAction(self,action):
                self.assert_before=self.native_action_sequence
                if action.fail:raise RuntimeError('callback not completed')
                events.append('base completed')
        observer=embedded('ObservedCatalogWindow',{'CatalogWindow':Base,'journal':lambda event,**values:events.append((event,values))})
        window=observer(fixture_case='tv-shows',fixture_generation=2)
        window.onAction(SimpleNamespace(getId=lambda:2,fail=False))
        self.assertEqual(window.assert_before,0);self.assertEqual(window.native_action_sequence,1)
        self.assertEqual(events[0],'base completed');self.assertEqual(events[1][0],'native-action-completed')
        with self.assertRaisesRegex(RuntimeError,'not completed'):window.onAction(SimpleNamespace(getId=lambda:1,fail=True))
        self.assertEqual(window.native_action_sequence,1);self.assertEqual(len(events),2)
    def test_close_is_not_published_until_actual_parent_and_back_callback_complete(self):
        state={'window':13000,'clock':0,'sleeps':0};writes=[]
        window=SimpleNamespace(closed=True,native_action_sequence=0,native_action_id=None,dispose=Mock())
        def sleep(_):
            state['clock']+=.02;state['sleeps']+=1
            if state['sleeps']==1:state['window']=10004
            if state['sleeps']==2:window.native_action_sequence=13;window.native_action_id=92
        def document(path,value):
            self.assertEqual(state['window'],10004);self.assertEqual(window.native_action_id,92)
            window.dispose.assert_called_once_with();writes.append(value)
        with tempfile.TemporaryDirectory() as temporary:
            finish=embedded('finish_case',{'require':require,'time':SimpleNamespace(monotonic=lambda:state['clock']),
                'xbmcgui':SimpleNamespace(getCurrentWindowId=lambda:state['window']),'xbmc':SimpleNamespace(sleep=sleep),
                'BASE':Path(temporary),'document':document,'journal':Mock()})
            finish(window,'tv-shows',2,10004)
        self.assertEqual(state['sleeps'],2);self.assertEqual(len(writes),1)
        self.assertEqual(writes[0]['actual_parent'],10004);self.assertEqual(writes[0]['native_action_sequence'],13)
    def test_stale_release_does_not_open_following_case(self):
        state={'clock':0,'sleeps':0};events=[]
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);path=base/'catalog-release.json'
            path.write_text(json.dumps(dict(case='tv-shows',generation=2,after_generation=1,parent=10004)))
            def sleep(_):
                state['clock']+=.02;state['sleeps']+=1
                self.assertFalse(events)
                RUNNER.atomic_document(path,dict(case='short-row',generation=3,after_generation=2,parent=10004))
            await_release=embedded('await_release',{'json':json,'BASE':base,'time':SimpleNamespace(monotonic=lambda:state['clock']),
                'xbmcgui':SimpleNamespace(getCurrentWindowId=lambda:10004),'xbmc':SimpleNamespace(sleep=sleep),
                'journal':lambda event,**values:events.append((event,values))})
            await_release('short-row',3,10004)
            self.assertFalse(path.exists())
        self.assertEqual(state['sleeps'],1);self.assertEqual(events[0][1]['generation'],3)
    def test_all_original_short_row_selection_and_pixel_assertions_remain(self):
        source=(ROOT/'tools/render_library.py').read_text()
        self.assertIn("state().get('case')=='short-row' and state().get('focus')==50 and state().get('position')==0",source)
        self.assertIn('zip(short,[91,544,357,944])',source)
        self.assertIn("wait_for(lambda:state().get('accent')=='FF1D9BC7')",source)
        self.assertNotIn('setCurrentListPosition',RUNNER.FIXTURE)
        self.assertNotIn('setFocusId',RUNNER.FIXTURE)
        self.assertIn("'library-actions.jsonl','catalog-close.json'",source)


if __name__=='__main__':unittest.main()
