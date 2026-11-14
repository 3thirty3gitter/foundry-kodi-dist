from pathlib import Path
import ast, importlib.util, sys, types, unittest, xml.etree.ElementTree as ET
import os
from unittest.mock import patch
ROOT=Path(os.environ.get('FOUNDRY_APPS',str(Path(__file__).resolve().parents[2])))
HELPER=os.environ.get('FOUNDRY_HELPER','script.foundry.helper')
SKIN=os.environ.get('FOUNDRY_SKIN','skin.foundry-nimbus')
P=ROOT/HELPER/'resources/lib/modules'
class Tests(unittest.TestCase):
 apps=ROOT;helper=HELPER;skin=SKIN
 def setUp(self):
  global commands,rpcs,labels,m,ROOT,HELPER,SKIN,P
  ROOT=self.apps;HELPER=self.helper;SKIN=self.skin;P=ROOT/HELPER/"resources/lib/modules"
  commands=[];rpcs=[];labels={}
  xbmc=types.ModuleType('xbmc');xbmc.executebuiltin=commands.append;xbmc.getInfoLabel=lambda k:labels.get(k,'');xbmc.getCondVisibility=lambda c:True
  pkg=types.ModuleType('testmodules');pkg.__path__=[str(P)]
  src=types.ModuleType('testmodules.catalog_source');src.rpc=lambda *args:rpcs.append(args)
  self.modules=patch.dict(sys.modules,{'xbmc':xbmc,'testmodules':pkg,'testmodules.catalog_source':src})
  self.modules.start();self.addCleanup(self.modules.stop)
  spec=importlib.util.spec_from_file_location('testmodules.catalog_playback',P/'catalog_playback.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 def item(self,url='plugin://plugin.video.fenskeleton/?mode=play_media&title=A%20%26%20B%2C%28C%29',kind='movie',filetype='file'):
  return dict(file=url,type=kind,filetype=filetype)
 def test_action_keeps_exact_url_and_never_resolves(self):
  i=self.item();m.play_item(i);self.assertEqual(commands,['RunPlugin("'+i['file']+'")']);self.assertEqual(rpcs,[])
 def test_generic_resolver_unchanged(self):
  i=self.item('plugin://plugin.video.youtube/?action=play_video&videoid=a');m.play_item(i);self.assertEqual(rpcs,[('Player.Open',{'item':{'file':i['file']}})]);self.assertEqual(commands,[])
 def test_local_unchanged(self):
  i=self.item('C:/media/test.mp4');m.play_item(i);self.assertEqual(rpcs,[('Player.Open',{'item':{'file':i['file']}})])
 def test_namespace_and_kind_guards(self):
  for i in [self.item('plugin://plugin.video.fenskeleton.evil/?mode=x'),self.item(kind='tvshow'),self.item(filetype='directory')]:self.assertFalse(m.action_provider(i))
 def test_info_captures_then_closes_then_action(self):
  i=self.item();labels.update({'ListItem.FileNameAndPath':i['file'],'ListItem.DBTYPE':'movie'});self.assertTrue(m.play_info_action());self.assertEqual(commands,['Dialog.Close(videoinfo)','RunPlugin("'+i['file']+'")']);self.assertEqual(rpcs,[])
 def test_info_other_provider_noop(self):
  labels.update({'ListItem.FileNameAndPath':'plugin://plugin.video.youtube/a','ListItem.DBTYPE':'movie'});self.assertFalse(m.play_info_action());self.assertEqual(commands,[])
 def test_bad_url_rejected(self):
  with self.assertRaises(ValueError):m.run_action('plugin://plugin.video.fenskeleton/?x="),Quit()')
  self.assertEqual(commands,[])
 def test_no_dialog_error_suppression(self):
  s=(P/'catalog_playback.py').read_text();self.assertNotIn('okdialog',s);self.assertNotIn('onPlayBackError',s);self.assertNotIn('Playlist.Clear',s)
 def test_all_files_compile_xml(self):
  for p in P.glob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'))
  x=ET.parse(ROOT/SKIN/'xml/DialogVideoInfo.xml');plays=[e for e in x.iter('onclick') if e.text in ('SendClick(8)','RunScript('+HELPER+',mode=vod_play_info_action)')];self.assertEqual(len(plays),2);self.assertTrue(all(e.get('condition') for e in plays))
class SlateTests(Tests):
 apps=Path(__file__).resolve().parents[1]/'src';helper='script.foundry.slate.helper';skin='skin.foundry.slate'
if __name__=='__main__':unittest.main(verbosity=2)
