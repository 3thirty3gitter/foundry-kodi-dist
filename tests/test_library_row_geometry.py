"""The approved modest row shift preserves poster size and footer clearance."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as E
SKIN=Path(__file__).resolve().parents[2]/'skin.foundry-nimbus'
class LibraryRowGeometry(unittest.TestCase):
 def test_both_catalog_rows_keep_the_same_bounded_poster_geometry(self):
  for name,row_id in [('script-foundry-vod.xml','50'),('View_57_StreamPilot.xml','57')]:
   tree=E.parse(SKIN/'xml'/name)
   row=tree.find(".//control[@type='fixedlist'][@id='%s']"%row_id)
   self.assertEqual((row.findtext('top'),row.findtext('height')),('444','600'))
   for mode in ('itemlayout','focusedlayout'):
    self.assertEqual({key:row.find(mode).get(key) for key in ('width','height')},{'width':'256','height':'600'})
   focused_top=444+132-336*.19/2
   focused_bottom=444+132+336+336*.19/2
   self.assertGreaterEqual(focused_top-(426+94),24)
   self.assertGreaterEqual(960-focused_bottom,16)
   self.assertLess(444+132+168+528*1.19/2,1080)
 def test_extra_hero_room_is_assigned_to_plot_without_moving_its_top(self):
  for name in ('script-foundry-vod.xml','View_57_StreamPilot.xml'):
   tree=E.parse(SKIN/'xml'/name)
   plots=[c for c in tree.findall('.//control') if c.findtext('font')=='sp_library_body' and c.findtext('top')=='426']
   self.assertEqual(len(plots),1);self.assertEqual(plots[0].findtext('height'),'94')
if __name__=='__main__':unittest.main()
