from pathlib import Path
import importlib.util,json,sys,types,unittest,xml.etree.ElementTree as E
from unittest.mock import Mock,patch
OUT=Path(__file__).resolve().parent
BASE=OUT.parent.parent
class PulseMigration(unittest.TestCase):
 def setUp(self):
  self.flags={'System.HasAddon(resource.uisounds.foundry.pulse)':True}
  self.calls=[];self.current='resource.uisounds.kodi';self.set_result=True
  fake=types.ModuleType('xbmc');fake.LOGERROR=3;fake.getSkinDir=lambda:'skin.foundry';fake.log=Mock()
  fake.getCondVisibility=lambda name:self.flags.get(name,False)
  fake.executebuiltin=Mock(side_effect=lambda command:self.flags.__setitem__('Skin.HasSetting('+command[len('Skin.SetBool('):-1]+')',True))
  def rpc(text):
   call=json.loads(text);self.calls.append(call)
   return json.dumps({'result':{'value':self.current} if call['method']=='Settings.GetSettingValue' else self.set_result})
  fake.executeJSONRPC=Mock(side_effect=rpc);self.fake=fake;mocked=patch.dict(sys.modules,{'xbmc':fake});mocked.start();self.addCleanup(mocked.stop)
  spec=importlib.util.spec_from_file_location('pulse_candidate',BASE/'script.foundry.helper/resources/lib/modules/experience.py')
  self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
 def test_fresh_default_moves_to_pulse_once(self):
  self.assertTrue(self.module.configure_experience());self.assertFalse(self.module.configure_experience())
  self.assertEqual(len(self.calls),2)
 def test_managed_androidtv_moves_to_pulse(self):
  self.current='resource.uisounds.androidtv';self.flags['Skin.HasSetting(foundry.sounds.default.v1)']=True
  self.assertTrue(self.module.configure_experience())
 def test_unmanaged_androidtv_choice_is_preserved(self):
  self.current='resource.uisounds.androidtv';self.assertFalse(self.module.configure_experience());self.assertEqual(len(self.calls),1)
 def test_later_return_to_kodi_sounds_is_preserved(self):
  self.flags['Skin.HasSetting(foundry.sounds.default.v1)']=True
  self.assertFalse(self.module.configure_experience());self.assertEqual(len(self.calls),1)
 def test_no_sound_choice_is_preserved(self):
  self.current='';self.assertFalse(self.module.configure_experience());self.assertEqual(len(self.calls),1)
 def test_custom_sound_choice_is_preserved(self):
  self.current='resource.uisounds.custom';self.assertFalse(self.module.configure_experience());self.assertEqual(len(self.calls),1)
 def test_current_pulse_marks_completion_without_reapplying(self):
  self.current=self.module.SOUND_ADDON;self.assertFalse(self.module.configure_experience());self.assertEqual(len(self.calls),1)
  self.fake.executebuiltin.assert_called_once_with('Skin.SetBool(foundry.sounds.pulse.v1)')
 def test_missing_addon_waits_without_marking_or_changing_settings(self):
  self.flags.clear();self.assertFalse(self.module.configure_experience());self.assertEqual(self.calls,[]);self.fake.executebuiltin.assert_not_called()
 def test_other_active_skin_is_untouched(self):
  self.fake.getSkinDir=lambda:'skin.estuary';self.assertFalse(self.module.configure_experience());self.assertEqual(self.calls,[])
 def test_bad_setting_read_never_changes_preferences(self):
  for response in ['broken','null','[]','{"result":{}}','{"error":{}}']:
   self.fake.executeJSONRPC.side_effect=lambda text:response
   self.assertFalse(self.module.configure_experience());self.fake.executebuiltin.assert_not_called()
 def test_failed_write_keeps_migration_retryable(self):
  self.set_result=False;self.assertFalse(self.module.configure_experience());self.fake.executebuiltin.assert_not_called()
  self.set_result=True;self.assertTrue(self.module.configure_experience())
 def test_runtime_rpc_error_is_nonfatal(self):
  self.fake.executeJSONRPC.side_effect=RuntimeError('fixture failure');self.assertFalse(self.module.configure_experience());self.fake.executebuiltin.assert_not_called()
 def test_mute_volume_and_playback_audio_settings_are_never_written(self):
  self.module.configure_experience()
  self.assertEqual([c['params']['setting'] for c in self.calls],['lookandfeel.soundskin','lookandfeel.soundskin'])
  self.assertEqual([c['method'] for c in self.calls],['Settings.GetSettingValue','Settings.SetSettingValue'])
class NativeBindings(unittest.TestCase):
 def test_exact_supported_native_action_mapping(self):
  root=E.parse(OUT.parent/'src/resource.uisounds.foundry.pulse/resources/sounds.xml')
  mapping={a.findtext('name'):a.findtext('file') for a in root.findall('actions/action')}
  self.assertEqual(mapping,{'left':'navigate.wav','right':'navigate.wav','up':'navigate.wav','down':'navigate.wav','select':'select.wav','back':'back.wav','previousmenu':'back.wav','error':'error.wav'})
  self.assertIsNone(root.find('windows'))
 def test_native_sound_resource_uses_official_extension_type(self):
  addon=E.parse(OUT.parent/'src/resource.uisounds.foundry.pulse/addon.xml')
  self.assertIsNotNone(addon.find("extension[@point='kodi.resource.uisounds']"))
  self.assertEqual(addon.find("requires/import[@addon='kodi.resource']").get('version'),'1.0.0')
 def test_echo_replaces_only_the_busy_artwork_and_legacy_center_badge(self):
  original=E.parse(OUT/'fixtures/dialogbusy-1.3.9.xml').getroot();candidate=E.parse(BASE/'skin.foundry-nimbus/xml/DialogBusy.xml').getroot()
  for root in [original,candidate]:
   for parent in root.iter():
    for control in list(parent):
     if control.tag=='control' and control.findtext('width')=='30':parent.remove(control)
   for texture in root.iter('texture'):
    if texture.text=='foundry-progress/05-ripple-white.gif':texture.text='loading.gif'
  normal=lambda n:(n.tag,n.attrib,(n.text or '').strip(),[normal(c) for c in n])
  self.assertEqual(normal(original),normal(candidate))
 def test_echo_keeps_native_loop_texture_sizing_and_theme_tint(self):
  root=E.parse(BASE/'skin.foundry-nimbus/xml/DialogBusy.xml')
  control=next(c for c in root.iter('control') if c.findtext('texture')=='foundry-progress/05-ripple-white.gif')
  self.assertEqual([control.findtext(k) for k in ['width','height','aspectratio']],['333','333','keep'])
  self.assertEqual(control.find('texture').get('colordiffuse'),'$VAR[FocusColorTheme]')
class OriginalAssetIntegrity(unittest.TestCase):
 def test_selected_quick_relay_waves_and_existing_error_are_exact(self):
  import hashlib,wave
  expected={'navigate.wav':(5600, 'bbfab20103bf39a11a66c153807614911ffe8f2f5d7eb24e5ac0d4e681d4b93f'),
            'select.wav':(5600, 'bbfab20103bf39a11a66c153807614911ffe8f2f5d7eb24e5ac0d4e681d4b93f'),
            'back.wav':(5600, 'bbfab20103bf39a11a66c153807614911ffe8f2f5d7eb24e5ac0d4e681d4b93f'),
            'error.wav':(19448,'7b1f66ef34928b114aefe6b4a376ecfed5fc6199faf65d4a1457ffcd62c73dc7')}
  for name,(size,digest) in expected.items():
   path=OUT.parent/'src/resource.uisounds.foundry.pulse/resources'/name
   data=path.read_bytes();self.assertEqual(len(data),size);self.assertEqual(hashlib.sha256(data).hexdigest(),digest)
   with wave.open(str(path),'rb') as audio:
    self.assertEqual((audio.getnchannels(),audio.getsampwidth(),audio.getframerate()),(1,2,44100))
    samples=audio.readframes(audio.getnframes())
    self.assertEqual(samples[:2],b'\x00\x00');self.assertEqual(samples[-2:],b'\x00\x00')
 def test_published_original_pulse_package_is_preserved(self):
  import hashlib,zipfile
  archive=OUT.parent/'resource.uisounds.foundry.pulse/resource.uisounds.foundry.pulse-1.0.0.zip'
  with zipfile.ZipFile(archive) as bundle:
   expected={'navigate.wav':'d91fc5e76db9988f97b6317ed01d573100507d4d5ba452ad1f94fe84fecf38cc','select.wav':'97c81d78c73ee2ca1c981cd56036a371842b187dda853e2a45b16fbce794d331','back.wav':'068a883c876f22260199033bf8b290e7a224233a0ff626a3afec7569085c2765'}
   for name,digest in expected.items():
    self.assertEqual(hashlib.sha256(bundle.read('resource.uisounds.foundry.pulse/resources/'+name)).hexdigest(),digest)
 def test_quick_relay_update_keeps_stable_identity_and_bumps_version(self):
  addon=E.parse(OUT.parent/'src/resource.uisounds.foundry.pulse/addon.xml').getroot()
  self.assertEqual(addon.get('id'),'resource.uisounds.foundry.pulse')
  self.assertEqual(addon.get('version'),'1.1.0')
 def test_selected_white_ripple_original_is_unchanged(self):
  import hashlib
  from PIL import Image
  path=BASE/'skin.foundry-nimbus/media/foundry-progress/05-ripple-white.gif'
  self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),'19d66f168399b5cbf7228a2074a00aa5872ebfe949034aaae3119d91ca150400')
  with Image.open(path) as im:
   self.assertEqual(im.size,(320,320));self.assertEqual(im.n_frames,60);self.assertEqual(im.info.get('loop'),0)
   for frame in range(im.n_frames):
    im.seek(frame);self.assertEqual(im.info.get('duration'),50)
 def test_skin_only_installs_require_the_native_sound_resource(self):
  skin=E.parse(BASE/'skin.foundry-nimbus/addon.xml')
  self.assertEqual(skin.find("requires/import[@addon='resource.uisounds.foundry.pulse']").get('version'),'1.0.0')

if __name__=='__main__':unittest.main(verbosity=2)
