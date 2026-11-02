"""Regression of lower-row menu returns and feathered playback backdrop.

The scroll model follows Kodi Omega GUIControlGroupList.cpp's FOCUSED,
SETFOCUS and IsControlOnScreen rules. It is not a substitute for device QA.
"""
import copy
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import zipfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT.parent / 'skin.foundry-nimbus'

class NativeScroll:
    def __init__(self, sizes, gap, viewport):
        self.sizes = sizes
        self.gap = gap
        self.viewport = viewport
        self.offset = 0
        self.index = 0
        self.selected = {}
    def focus(self, index, item):
        start = sum(s + self.gap for s in self.sizes[:index])
        total = sum(s + self.gap for s in self.sizes) - self.gap
        if index == 1:  # first focusable row (labels are not focusable)
            self.offset = 0
        elif index == len(self.sizes)-1:
            self.offset = max(0, total-self.viewport)
        elif start < self.offset:
            self.offset = start
        elif start + self.sizes[index] > self.offset + self.viewport:
            self.offset = start + self.sizes[index] - self.viewport
        self.index = index
        self.selected[index] = item
    def snapshot(self):
        return self.index, self.offset, dict(self.selected), self.viewport
    def enter(self):
        start = sum(s + self.gap for s in self.sizes[:self.index])
        assert start >= self.offset and start+self.sizes[self.index] <= self.offset+self.viewport
        return self.snapshot()

class DeviceFeedback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = ET.parse(SKIN/'xml/Home.xml')
        cls.shared = ET.parse(SKIN/'xml/Includes_Home.xml')
        cls.common = cls.shared.find("include[@name='HomeWidgetGroupListCommon']")
        cls.animations = ET.parse(SKIN/'xml/Includes_Animations.xml')
    def test_all_home_categories_are_clipped_and_manual_offsets_are_removed(self):
        groups = [c for c in self.home.iter('control') if c.get('type')=='grouplist' and c.get('id','').endswith('001')]
        self.assertEqual(len(groups), 15)
        for c in groups:
            self.assertEqual(c.findtext('include'), 'HomeWidgetGroupListCommon')
            self.assertFalse(c.findall("include[@content='Animation_Widget_Poster_Slide']"))
        self.assertEqual(int(self.common.findtext('height')), 570)
        self.assertFalse(self.common.findall('animation'))
        self.assertEqual(self.common.find('defaultcontrol').get('always'), 'false')
        self.assertEqual(self.common.findtext('defaultcontrol'), '0')
    def test_lower_rows_keep_offset_and_item_on_repeated_menu_returns(self):
        label = self.shared.find("include[@name='CategoryLabel']/definition/control")
        poster = self.shared.find("include[@name='WidgetListPoster']/definition/control[@type='fixedlist']")
        sizes = [int(label.findtext('top'))+int(label.findtext('height')), int(poster.findtext('top'))+int(poster.findtext('height'))]*20
        gap = int(self.common.findtext('itemgap'))
        for lower_row in (1, 2, 5, 10, 19):
            for item in (0, 1, 19, 49, 99):
                state = NativeScroll(sizes, gap, int(self.common.findtext('height')))
                for row in range(lower_row+1): state.focus(row*2+1, item)
                before = state.snapshot()
                self.assertGreater(state.offset, 0)
                for _ in range(20):
                    # Main-menu focus performs no resize, scroll reset or item select.
                    self.assertEqual(state.enter(), before)
                    self.assertEqual(state.viewport, 570)
    def test_category_switches_keep_each_native_scroll_state(self):
        categories = {c: NativeScroll([120,448]*10, -100,570) for c in ('movies','tvshows','custom1','musicvideos')}
        snapshots = {}
        for i,(name,state) in enumerate(categories.items()):
            state.focus((i+2)*2+1, i*17);snapshots[name] = state.snapshot()
        for _ in range(12):
            for name in reversed(categories): self.assertEqual(categories[name].enter(), snapshots[name])
    def test_menu_cannot_clear_row_marker_or_resize_viewport(self):
        menu = self.home.find(".//control[@id='9000']")
        actions = [c.text or '' for c in menu if c.tag in ('onfocus','onunfocus','onright')]
        self.assertNotIn('ClearProperty(nimbus_saved_list_id,home)',actions)
        self.assertFalse(any('SetFocus(' in a and ',0,absolute' in a for a in actions))
        fades = self.animations.find("include[@name='WidgetVisibilityAnimations']").findall('animation')
        self.assertEqual(self.animations.find("include[@name='WidgetVisibilityAnimations']/include").get('condition'),'!Window.IsActive(Home)')
        self.assertEqual(len(self.animations.find("include[@name='LegacyWidgetVisibilityAnimations']").findall('animation')),2)
        visual_gates=[v.text for v in self.shared.findall('.//itemlayout/control/visible') if 'foundry.home.row.' in (v.text or '')]
        self.assertEqual(len(visual_gates),4)
        self.assertTrue(all('Window(Home).Property(foundry.home.row.addons)' in gate for gate in visual_gates))
        self.assertTrue(all('Integer.IsLessOrEqual(Window(Home).Property(' in gate for gate in visual_gates))
    def test_search_retains_its_legacy_scroll_and_fades(self):
        search = ET.parse(SKIN/'xml/Custom_1121_SearchResults.xml')
        self.assertTrue(search.findall(".//include[@content='Animation_Widget_Poster_Slide']"))
        self.assertEqual(self.shared.findtext("include[@name='WidgetGroupListCommon']/height"),'33000')
    def test_media_center_lettering_preserves_original_graphic_source_and_geometry(self):
        from PIL import ImageChops
        import base64,hashlib
        old=Image.open(SKIN/'media/foundry-logo.png').convert('RGBA')
        new=Image.open(SKIN/'media/foundry-logo-traced.png').convert('RGBA')
        self.assertEqual(new.size,(3040,920))
        # The approved SVG export uses a different raster sampler than the old
        # Pillow upscale. Verify the actual unchanged embedded graphic bytes
        # and original FOUNDRY path, rather than demand identical antialiasing.
        svg=ET.parse(SKIN/'resources/foundry-header-media-center.svg').getroot()
        icon=next(n for n in svg.iter() if n.tag.endswith('image'))
        href=next(v for k,v in icon.attrib.items() if k.endswith('href'))
        self.assertEqual(base64.b64decode(href.split(',')[1]),(SKIN/'media/foundry-logo.png').read_bytes())
        main=next(n for n in svg.iter() if n.get('id')=='main')
        self.assertEqual(hashlib.sha256(main.get('d').encode()).hexdigest(),'4ecf6ad751a3076d9c6810b040c6095efdf176ca3560599684d4358c49cbdac2')
        expected=old.resize(new.size,Image.Resampling.LANCZOS)
        self.assertIsNotNone(ImageChops.difference(expected.crop((1140,0,3040,920)),new.crop((1140,0,3040,920))).getbbox())
    def test_osd_keeps_all_foreground_controls_and_actions(self):
        with zipfile.ZipFile(ROOT/'skin.foundry/skin.foundry-1.1.7.zip') as z:
            before = ET.fromstring(z.read('skin.foundry/xml/Includes_StreamPilotOSD.xml'))
        after = ET.parse(SKIN/'xml/Includes_StreamPilotOSD.xml')
        def normalized(n): return n.tag,n.attrib,(n.text or '').strip(),[normalized(c) for c in n]
        for name in ('StreamPilotVODCard','StreamPilotLiveCard'):
            old=before.find("include[@name='%s']/control"%name)
            new=after.find("include[@name='%s']/control"%name)
            old_controls=old.findall('control'); new_controls=new.findall('control')
            self.assertEqual([normalized(c) for c in old_controls[3:]],[normalized(c) for c in new_controls[1:]])
            self.assertEqual(old.findtext('left'),new.findtext('left'))
            self.assertEqual(old.findtext('bottom'),new.findtext('bottom'))
            self.assertEqual(old.findtext('height'),new.findtext('height'))
            self.assertFalse(new_controls[0].find('texture').get('border'))
            self.assertEqual(new_controls[0].findtext('texture'),'streampilot/osd-feather.png')
    def test_osd_fade_is_transparent_at_every_outer_edge(self):
        im=Image.open(SKIN/'media/streampilot/osd-feather.png'); a=im.getchannel('A');w,h=im.size
        self.assertEqual(a.crop((0,0,w,1)).getextrema(),(0,0))
        self.assertEqual(a.crop((0,h-1,w,h)).getextrema(),(0,0))
        self.assertEqual(a.crop((0,0,1,h)).getextrema(),(0,0))
        self.assertEqual(a.crop((w-1,0,w,h)).getextrema(),(0,0))
        self.assertGreaterEqual(a.getpixel((w//2,h//2)),220)
        ramp=[a.getpixel((w//2,y)) for y in range(51)]
        self.assertEqual(ramp,sorted(ramp))
        self.assertLess(max(b-a for a,b in zip(ramp,ramp[1:])),8)

if __name__=='__main__':unittest.main()
