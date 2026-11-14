import ast,unittest
from pathlib import Path
class NativeIconContract(unittest.TestCase):
 def test_runner_contract(self):
  root=Path(__file__).resolve().parents[1]
  p=root/'tools/render_slate_icons.py'
  if not p.exists():p=Path(__file__).with_name('render_slate_icons.py')
  s=p.read_text();ast.parse(s)
  for required in ['resource.images.foundry.slate.icons','Addons.SetAddonEnabled','icons-home','icons-settings','icons-keyboard','icons-default-placeholders','icons-playback-osd','native-icon-report.json','texture_failures','Opaque patch','readBytes']:
   self.assertIn(required,s)
  self.assertIn("report['native']['passed']",s)
  self.assertIn('sys.exit(0 if report[',s)
  self.assertIn('bytes([137,80,78,71,13,10,26,10])',s)
if __name__=='__main__':unittest.main()
