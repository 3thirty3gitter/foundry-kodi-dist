import importlib.util,json,sys,types,unittest
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
class Tests(unittest.TestCase):
 source=ROOT.parent/'script.foundry.helper/resources/lib/modules/search_provider.py'
 def setUp(self):
  guard=patch.dict(sys.modules);guard.start();self.addCleanup(guard.stop)
  self.x=types.SimpleNamespace(executeJSONRPC=Mock(),getCondVisibility=Mock(return_value=True),getInfoLabel=Mock(return_value=''),executebuiltin=Mock())
  self.d=types.SimpleNamespace(select=Mock(return_value=-1),yesno=Mock(return_value=True),ok=Mock())
  sys.modules['xbmc']=self.x;sys.modules['xbmcgui']=types.SimpleNamespace(Dialog=lambda:self.d)
  sys.modules['modules']=types.ModuleType('modules');self.repos=Mock();sys.modules['modules.repo_installer']=types.SimpleNamespace(show_repos=self.repos)
  s=importlib.util.spec_from_file_location('picker',self.source);self.m=importlib.util.module_from_spec(s);s.loader.exec_module(self.m)
 def inventory(self,items):self.x.executeJSONRPC.return_value=json.dumps({'result':{'addons':items}})
 def test_dynamic_inventory_not_id_prefix_and_sort(self):
  self.inventory([{'addonid':'plugin.other.video','name':'Zed','enabled':True},{'addonid':'plugin.video.fen','name':'Alpha','enabled':True}]);p=self.m.installed_video_providers();self.assertEqual([x['slot'] for x in p],['0','plugin.other.video']);req=json.loads(self.x.executeJSONRPC.call_args.args[0]);self.assertEqual(req['params']['type'],'xbmc.addon.video');self.assertTrue(req['params']['installed'])
 def test_selected_id_and_legacy_slot(self):
  self.inventory([{'addonid':'plugin.video.fen','name':'FEN','enabled':True}]);self.d.select.return_value=0;self.x.getInfoLabel.return_value='0';self.m.choose_search_provider();self.assertEqual(self.d.select.call_args.kwargs['preselect'],0);self.assertIn('Skin.SetString(current_search_provider,"0")',[c.args[0] for c in self.x.executebuiltin.call_args_list])
 def test_unknown_requires_disclosure(self):
  self.inventory([{'addonid':'plugin.other.video','name':'Other','enabled':True}]);self.d.select.return_value=0;self.m.choose_search_provider();self.assertIn('no integrated',self.d.yesno.call_args.args[1]);self.assertIn('Skin.SetString(current_search_provider,"plugin.other.video")',[c.args[0] for c in self.x.executebuiltin.call_args_list])
 def test_cancel_leaves_settings(self):
  self.inventory([{'addonid':'plugin.other.video','name':'Other','enabled':True}]);self.m.choose_search_provider();self.x.executebuiltin.assert_not_called()
 def test_disabled_is_visible_but_not_enabled(self):
  self.inventory([{'addonid':'plugin.video.disabled','name':'Disabled','enabled':False}]);self.d.select.return_value=0;self.m.choose_search_provider();self.assertIn('(disabled)',self.d.select.call_args.args[1][0]);self.x.executebuiltin.assert_not_called()
 def test_uninstalled_after_dialog(self):
  self.inventory([{'addonid':'plugin.video.fen','name':'FEN','enabled':True}]);self.d.select.return_value=0;self.x.getCondVisibility.return_value=False;self.m.choose_search_provider();self.x.executebuiltin.assert_not_called()
 def test_error_does_not_reset(self):
  self.x.executeJSONRPC.return_value='{"error":{}}';self.m.choose_search_provider();self.x.executebuiltin.assert_not_called();self.d.ok.assert_called_once()
 def test_fallback_honest_root_and_validated(self):
  self.x.getInfoLabel.return_value='plugin.other.video';self.m.open_selected_video_provider();self.x.executebuiltin.assert_called_once_with('ActivateWindow(Videos,"plugin://plugin.other.video/",return)');self.x.executebuiltin.reset_mock();self.x.getInfoLabel.return_value='evil),Quit(';self.m.open_selected_video_provider();self.x.executebuiltin.assert_not_called()
 def test_refresh_each_open(self):
  self.inventory([]);self.m.choose_search_provider();self.inventory([{'addonid':'plugin.video.new','enabled':True}]);self.m.choose_search_provider();self.assertEqual(self.x.executeJSONRPC.call_count,2);self.d.select.assert_called_once()
 def test_external_entry_guard_preserves_native(self):
  for value in ('','0','1','2','3','4'):
   self.x.getInfoLabel.return_value=value
   self.assertFalse(self.m.use_external_video_provider())
  self.x.executebuiltin.assert_not_called()
 def test_external_entry_guard_routes_generic(self):
  self.x.getInfoLabel.return_value='plugin.qa.video'
  self.assertTrue(self.m.use_external_video_provider())
  self.x.executebuiltin.assert_called_once_with('ActivateWindow(Videos,"plugin://plugin.qa.video/",return)')
class SlateTests(Tests):
 source=ROOT/'src/script.foundry.slate.helper/resources/lib/modules/search_provider.py'

if __name__=='__main__':unittest.main()
