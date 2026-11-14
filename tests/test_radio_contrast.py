from pathlib import Path
import unittest,xml.etree.ElementTree as E
class RadioContrast(unittest.TestCase):
 def test_dark_rows_have_bright_stateful_focus(self):
  r=Path(__file__).resolve().parents[1]
  f=r/'src/skin.foundry.slate/xml/Includes_Buttons.xml'
  if not f.exists():f=Path(__file__).with_name('Includes_Buttons.radio-contrast.xml')
  tree=E.parse(f)
  for name in ['DefaultSettingButton','DefaultAddonSettingsButton','DefaultSystemSettingsButton','DialogSettingButton']:
   d=tree.find("./include[@name='"+name+"']/definition")
   for state in ['on','off']:
    n=d.find('textureradio'+state+'focus')
    self.assertIsNotNone(n)
    self.assertEqual(n.get('colordiffuse'),'FFDFC4A0')
    self.assertEqual(n.text,'buttons/radio-button-'+state+'.png')
if __name__=='__main__':unittest.main()
