from pathlib import Path
import copy,unittest,xml.etree.ElementTree as ET
from media_invariant_contracts import strip_media_context,strip_live_media_layout,wide_guard
ROOT=Path(__file__).resolve().parents[1]
SKINS=[ROOT.parent/'skin.foundry-nimbus',ROOT/'src/skin.foundry.slate']
class MediaMigrationContracts(unittest.TestCase):
 def test_exact_home_and_search_context_addition_both_skins(self):
  for skin in SKINS:
   for name in ['Home.xml','Custom_1121_SearchResults.xml']:
    root=ET.parse(skin/'xml'/name).getroot();params=root.findall(".//param[@name='media_context']");self.assertEqual(len(params),1)
    self.assertEqual(params[0].attrib,{'name':'media_context','value':'container'});strip_media_context(root);self.assertEqual(root.findall(".//param[@name='media_context']"),[])
 def test_home_context_wrong_value_or_parent_is_not_ignored(self):
  root=ET.parse(SKINS[0]/'xml/Home.xml').getroot();root.find(".//param[@name='media_context']").set('value','player')
  with self.assertRaises(AssertionError):strip_media_context(root)
 def test_live_layout_exact_delta_both_skins(self):
  for skin,prefix in zip(SKINS,['foundry.media','foundry.slate.media']):
   root=ET.parse(skin/'xml/Includes_StreamPilotOSD.xml').getroot().find("include[@name='StreamPilotLiveCard']/control")
   count=len(root.findall('control'));strip_live_media_layout(root,prefix);self.assertEqual(len(root.findall('control')),count-2)
   self.assertEqual(len([c for c in root.findall('control') if c.findtext('right')=='452']),1)
   self.assertEqual(len([c for c in root.findall('control') if c.findtext('width')=='248']),1)
 def test_changed_alternate_action_or_geometry_is_not_ignored(self):
  for mutation in ['geometry','text','guard']:
   root=ET.parse(SKINS[0]/'xml/Includes_StreamPilotOSD.xml').getroot().find("include[@name='StreamPilotLiveCard']/control")
   wide=next(c for c in root.findall('control') if c.findtext('right')=='536')
   if mutation=='geometry':wide.find('height').text='191'
   if mutation=='text':wide.find('control/label').text='Altered'
   if mutation=='guard':wide.find('visible').text='true'
   with self.assertRaises(AssertionError):strip_live_media_layout(root)
if __name__=='__main__':unittest.main(verbosity=2)
