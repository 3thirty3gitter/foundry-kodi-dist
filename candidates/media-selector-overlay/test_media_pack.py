import importlib.util,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
BASE=Path(__file__).parent
class Window:
 def __init__(self):self.data={};self.writes=0
 def setProperty(self,k,v):self.data[k]=v;self.writes+=1
 def clearProperty(self,k):self.data.pop(k,None);self.writes+=1
 def getProperty(self,k):return self.data.get(k,'')
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.win=Window();self.skin='skin.foundry';self.labels={};self.enabled=True;self.actions=[];self.selection=-1
  self.id='resource.images.foundry.media.test'
  self.data={'schema_version':1,'kind':'foundry-media-flags','release_status':'approved','name':'Test','asset_root':'flags','categories':['videocodec','videoresolution','videohdr','aspectratio','audiocodec','audiochannel']}
  self.save()
  xbmc=types.SimpleNamespace(getSkinDir=lambda:self.skin,getInfoLabel=lambda s:self.labels.get(s,''),getCondVisibility=self.visible,executebuiltin=self.act,executeJSONRPC=lambda s:json.dumps({'result':{'addons':[{'addonid':self.id}]}}))
  addon=types.SimpleNamespace(Addon=lambda i:types.SimpleNamespace(getAddonInfo=lambda k:str(self.root) if k=='path' else 'Test'))
  gui=types.SimpleNamespace(Window=lambda i:self.win,Dialog=lambda:types.SimpleNamespace(select=lambda *a,**k:self.selection))
  vfs=types.SimpleNamespace(translatePath=lambda p:p,exists=lambda p:Path(p).exists())
  self.patch=patch.dict(sys.modules,xbmc=xbmc,xbmcaddon=addon,xbmcgui=gui,xbmcvfs=vfs);self.patch.start()
  spec=importlib.util.spec_from_file_location('media_pack',BASE/'script.foundry.helper/resources/lib/modules/media_pack.py');self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
 def tearDown(self):self.patch.stop();self.temp.cleanup()
 def save(self):
  p=self.root/'resources/media-pack.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(self.data))
 def visible(self,s):return self.enabled if s.startswith('System.AddonIsEnabled') else self.labels.get(s,False)
 def act(self,s):
  self.actions.append(s)
  if s.startswith('Skin.SetString'):self.labels['Skin.String(MediaIconPack)']=s.split(',')[1][:-1]
  elif s.startswith('Skin.Reset'):self.labels['Skin.String(MediaIconPack)']=''
 def asset(self,cat,alias):
  p=self.root/'resources/flags'/cat/(alias+'.png');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'fixture');return str(p.resolve())
 def monitor(self):
  self.labels['Skin.String(MediaIconPack)']=self.id;return self.m.MediaPackMonitor()
 def test_discover(self):self.assertEqual(self.m.discover()[0]['id'],self.id)
 def test_experimental_excluded(self):self.data['release_status']='experimental-review-required';self.save();self.assertEqual(self.m.discover(),[])
 def test_missing_release_excluded(self):del self.data['release_status'];self.save();self.assertIsNone(self.m.read_pack(self.id))
 def test_schema_rejected(self):self.data['schema_version']=True;self.save();self.assertIsNone(self.m.read_pack(self.id))
 def test_invalid_manifest(self):self.data=[];self.save();self.assertIsNone(self.m.read_pack(self.id))
 def test_disabled(self):self.enabled=False;self.assertEqual(self.m.discover(),[])
 def test_missing_manifest(self):(self.root/'resources/media-pack.json').unlink();self.assertIsNone(self.m.read_pack(self.id))
 def test_asset_lookup(self):p=self.asset('audiocodec','truehd');self.assertEqual(self.m.resolve(self.m.read_pack(self.id),'audiocodec','TRUEHD'),p)
 def test_traversal(self):p=self.m.read_pack(self.id);self.assertEqual(self.m.resolve(p,'videocodec','../secret'),'');self.assertEqual(self.m.resolve(p,'../bad','h264'),'')
 def test_aliases(self):p=self.asset('videoresolution','4k');self.assertEqual(self.m.resolve(self.m.read_pack(self.id),'videoresolution','2160'),p)
 def test_missing_not_generic(self):self.asset('audiocodec','eac3');self.assertEqual(self.m.resolve(self.m.read_pack(self.id),'audiocodec','eac3-joc'),'')
 def test_cancel_unchanged(self):self.labels['Skin.String(MediaIconPack)']=self.id;self.m.choose();self.assertEqual(self.actions,[])
 def test_choose_and_reset(self):self.selection=1;self.m.choose();self.assertEqual(self.labels['Skin.String(MediaIconPack)'],self.id);self.selection=0;self.m.choose();self.assertEqual(self.labels['Skin.String(MediaIconPack)'],'')
 def test_monitor_contexts(self):
  a=self.asset('audiocodec','truehd');b=self.asset('audiocodec','aac');self.labels.update({'ListItem.AudioCodec':'truehd','Container.ListItem.AudioCodec':'aac','VideoPlayer.AudioCodec':'truehd'});m=self.monitor();m.process();self.assertEqual(self.win.data['foundry.media.list.audiocodec.path'],a);self.assertEqual(self.win.data['foundry.media.container.audiocodec.path'],b)
 def test_clears_empty(self):
  self.asset('audiocodec','aac');self.labels['ListItem.AudioCodec']='aac';m=self.monitor();m.process();self.labels['ListItem.AudioCodec']='';m.process();self.assertNotIn('foundry.media.list.audiocodec.path',self.win.data)
 def test_deleted_file_falls_back(self):
  p=self.asset('audiocodec','aac');self.labels['ListItem.AudioCodec']='aac';m=self.monitor();m.process();Path(p).unlink();m.process();self.assertNotIn('foundry.media.list.audiocodec.path',self.win.data)
 def test_disabled_after_selection(self):
  self.asset('audiocodec','aac');self.labels['ListItem.AudioCodec']='aac';m=self.monitor();m.process();self.enabled=False;m.process();self.assertNotIn('foundry.media.list.audiocodec.path',self.win.data)
 def test_restart_restores(self):
  self.asset('audiocodec','aac');self.labels['ListItem.AudioCodec']='aac';m=self.monitor();m.process();m.clear();m=self.m.MediaPackMonitor();m.process();self.assertTrue(self.win.data['foundry.media.list.audiocodec.path'])
 def test_skin_switch_clears(self):
  m=self.monitor();m.process();self.skin='skin.foundry.slate';m.process();self.assertEqual(self.win.data,{})
 def test_builtin_preserves_selection_on_missing(self):
  m=self.monitor();self.enabled=False;m.process();self.assertEqual(self.labels['Skin.String(MediaIconPack)'],self.id);self.assertEqual(self.win.data['foundry.media.name'],'Built-in icons')
 def test_stable_does_not_write(self):
  self.asset('audiocodec','aac');self.labels['ListItem.AudioCodec']='aac';m=self.monitor();m.process();n=self.win.writes;m.process();self.assertEqual(n,self.win.writes)
 def test_invalid_manifest_refresh(self):
  m=self.monitor();m.process();self.data['release_status']='experimental';self.save();m.next_refresh=0;m.process();self.assertNotIn('foundry.media.pack',self.win.data)
if __name__=='__main__':unittest.main(verbosity=2)

