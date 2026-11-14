from pathlib import Path
import unittest,xml.etree.ElementTree as E
class SettingsAspect(unittest.TestCase):
 def test_icons_do_not_crop_on_focus(self):
  f=Path(__file__).resolve().parents[1]/'src/skin.foundry.slate/xml/Includes.xml'
  if not f.exists():f=Path(__file__).with_name('Includes.settings-icon-keep.xml')
  panel=E.parse(f).find("./include[@name='SettingsPanel']")
  for layout in ['itemlayout','focusedlayout']:
   controls=[c for c in panel.find(layout).iter('control') if c.findtext('texture')=='$INFO[ListItem.Icon]']
   self.assertEqual(len(controls),1)
   self.assertEqual(controls[0].findtext('aspectratio'),'keep')
   self.assertEqual(controls[0].findtext('width'),'210')
   self.assertEqual(controls[0].findtext('height'),'140')
if __name__=='__main__':unittest.main()
