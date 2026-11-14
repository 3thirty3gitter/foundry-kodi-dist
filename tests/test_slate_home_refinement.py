from pathlib import Path
import unittest,xml.etree.ElementTree as E
S=Path(__file__).resolve().parents[1]
class Revision(unittest.TestCase):
 def test_menu_positions(self):
  h=E.parse(S/'src/skin.foundry.slate/xml/Home.xml')
  menu=h.find('.//control[@id="9000"]')
  self.assertEqual(menu.findtext('top'),'240')
  for tag in ('itemlayout','focusedlayout'):
   labels=menu.findall(tag+'/control[@type="label"]')
   self.assertEqual(len(labels),2)
   self.assertEqual([(n.findtext('left'),n.findtext('width'),n.findtext('visible')) for n in labels],[('76','295','!Skin.HasSetting(SlateHideMainMenuIcons)'),('25','346','Skin.HasSetting(SlateHideMainMenuIcons)')])
  self.assertEqual(menu.find('focusedlayout/control[@type="image"]/top').text,'11')
 def test_footer_dimensions_focus(self):
  h=E.parse(S/'src/skin.foundry.slate/xml/Home.xml')
  for i in ('801','802','803'):
   c=h.find('.//control[@id="'+i+'"]')
   self.assertEqual((c.findtext('width'),c.findtext('height')),('48','48'))
   self.assertEqual(c.find('texturefocus').get('colordiffuse'),'accent_color')
   self.assertEqual(len(c.findall('animation')),2)
 def test_hero_entry(self):
  h=(S/'src/skin.foundry.slate/xml/Home.xml').read_text()
  self.assertNotIn('SetFocus(15154)',h);self.assertEqual(h.count('SetFocus(15149)'),2)
 def test_native_contract(self):
  p=S/'tools/render_slate_navigation.py';compile(p.read_text(),str(p),'exec')
  self.assertIn("hidden_label_shift_pixels",p.read_text())
  self.assertIn("selector_alignment",p.read_text())
  self.assertIn("shown_persisted_after_second_restart",p.read_text())
if __name__=='__main__':unittest.main()

