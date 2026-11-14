from pathlib import Path
import ast,unittest
class ViewContract(unittest.TestCase):
 def test_placeholder_claim_uses_available_native_view(self):
  f=Path(__file__).resolve().parents[1]/'tools/render_slate_icons.py'
  if not f.exists():f=Path(__file__).with_name('render_slate_icons.v4.py')
  text=f.read_text();tree=ast.parse(text)
  n=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='payload' for t in n.targets))
  payload=ast.literal_eval(n.value)
  self.assertIn('Container.SetViewMode(52)',payload)
  self.assertIn("Control.IsVisible(52)",payload)
  self.assertNotIn("'view':57",payload)
  self.assertIn("'view':52",payload)
  self.assertIn('icons-wall-default-folder',payload)
  self.assertIn('icons-wall-default-file',payload)
  self.assertIn("icon.startswith('Default')",payload)
  self.assertIn('myvideos.extractthumb',text)
if __name__=='__main__':unittest.main()
