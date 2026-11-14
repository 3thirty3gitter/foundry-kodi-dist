from pathlib import Path
import sys,unittest,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1]; X=ROOT/'src/skin.foundry.slate/xml'
class MenuContract(unittest.TestCase):
 def test_fonts(self):
  for fs in E.parse(X/'Font.xml').findall('fontset'):
   f=[f for f in fs.findall('font') if f.findtext('name')=='SlateNav']
   self.assertEqual(len(f),1);self.assertEqual(int(f[0].findtext('size')),round(28*1.1))
 def test_menu_icons_only(self):
  home=E.parse(X/'Home.xml');conditions=[]
  for layout in ('itemlayout','focusedlayout'):
   menu=home.find('.//control[@id="9000"]/'+layout)
   images=[c for c in menu.findall('control') if c.findtext('texture','').startswith('slate-icons/')]
   self.assertEqual(len(images),1)
   self.assertEqual(images[0].findtext('visible'),'!Skin.HasSetting(SlateHideMainMenuIcons)')
   self.assertEqual(menu.find('control[@type="label"]/font').text,'SlateNav')
  for i in ('801','802','803'):
   c=home.find('.//control[@id="'+i+'"]');self.assertEqual(c.findtext('visible'),'true')
 def test_setting(self):
  c=E.parse(X/'SkinSettings.xml').find('.//control[@id="6243"]')
  self.assertEqual(c.get('type'),'radiobutton')
  self.assertEqual(c.findtext('label'),'Show main menu icons')
  self.assertEqual(c.findtext('selected'),'!Skin.HasSetting(SlateHideMainMenuIcons)')
  self.assertEqual(c.findtext('onclick'),'Skin.ToggleSetting(SlateHideMainMenuIcons)')
 def test_footer_focus(self):
  h=E.parse(X/'Home.xml')
  for i,icon in zip(('801','802','803'),('power','settings','search')):
   c=h.find('.//control[@id="'+i+'"]')
   self.assertEqual(c.find('texturefocus').get('colordiffuse'),'accent_color')
   self.assertEqual(c.findtext('texturefocus'),'slate-icons/'+icon+'.png')
   self.assertEqual(c.findtext('texturenofocus'),'slate-icons/'+icon+'.png')
   a=c.findall('animation');self.assertEqual(len(a),2)
   self.assertEqual([(x.text,x.get('start'),x.get('end')) for x in a],[('Focus','100','115'),('UnFocus','115','100')])
 def test_native_fixture_requires_fresh_evidence_and_real_toggle(self):
  runner=(ROOT/'tools/render_slate_navigation.py').read_text()
  self.assertIn('for stale in out.iterdir():',runner)
  self.assertIn('stale.unlink()',runner)
  self.assertIn('hidden_persisted_after_restart',runner)
  self.assertIn('shown_persisted_after_second_restart',runner)
  self.assertIn('footer_visual_differences',runner)
  self.assertIn('SetFocus(6243)',runner)
if __name__=='__main__':unittest.main()
