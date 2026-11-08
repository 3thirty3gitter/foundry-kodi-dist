"""Owner-requested widget, paging, menu artwork and first-frame regressions."""
from concurrent.futures import Future
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import xml.etree.ElementTree as E
import zipfile
from PIL import Image
import test_release as kodi
from modules.catalog_model import CatalogState
from modules import catalog_color

ROOT=kodi.ROOT;SKIN=kodi.SKIN;HELPER=kodi.HELPER


class InterfaceFeedback(unittest.TestCase):
    def test_complete_themed_icon_catalog_has_transparent_full_color_artwork(self):
        folder=SKIN/'media/foundry-icons';catalog=json.loads((folder/'CATALOG.json').read_text())
        self.assertEqual(len(catalog['icons']),52)
        self.assertIn('wallpaper',catalog['style'].lower())
        for name in catalog['icons']:
            with Image.open(folder/(name+'.png')) as image:
                self.assertEqual(image.size,(256,256));self.assertEqual(image.mode,'RGBA')
                low,high=image.getchannel('A').getextrema()
                self.assertEqual(low,0);self.assertGreaterEqual(high,250)
                self.assertGreater(len(image.convert('RGB').getcolors(65536) or []),30)

    def test_native_row_artwork_preserves_the_icon_colors_and_empty_background(self):
        folder=SKIN/'media/foundry-icons'
        for name in json.loads((folder/'CATALOG.json').read_text())['icons']:
            with Image.open(folder/'rows'/(name+'-normal.png')) as image:
                self.assertEqual(image.size,(320,70))
                self.assertEqual(image.convert('RGBA').getpixel((200,35))[3],0)
            with Image.open(folder/'rows'/(name+'-focus.png')) as image:self.assertEqual(image.size,(320,70))

    def test_every_settings_root_item_has_a_packaged_themed_icon(self):
        items=E.parse(SKIN/'xml/Settings.xml').findall('.//item')
        self.assertGreaterEqual(len(items),13)
        for item in items:
            name=item.findtext('icon');self.assertTrue(name.startswith('foundry-icons/'))
            self.assertTrue((SKIN/'media'/name).is_file(),name)

    def test_settings_templates_reserve_an_icon_for_each_native_option_type(self):
        root=E.parse(SKIN/'xml/SettingsCategory.xml')
        for cid in ['7','8','9','13','15']:
            control=root.find(".//control[@id='%s']"%cid)
            include=control.find("include[@content='DefaultSettingButton']")
            icon=include.find("param[@name='system_icon']").get('value')
            self.assertTrue((SKIN/'media/foundry-icons'/(icon+'.png')).is_file())
        coverage=json.loads((SKIN/'media/foundry-icons/COVERAGE.json').read_text())['static_entries_and_templates']
        self.assertGreaterEqual(len(coverage),190)

    def test_home_menu_icons_and_foundry_header_are_preserved(self):
        with zipfile.ZipFile(ROOT/'skin.foundry/skin.foundry-1.3.7.zip') as bundle:
            before=E.fromstring(bundle.read('skin.foundry/xml/Home.xml'))
        after=E.parse(SKIN/'xml/Home.xml').getroot()
        def icons(root):return [(node.tag,(node.text or '').strip(),node.attrib) for node in root.iter() if node.tag in ('icon','texture')]
        self.assertEqual(icons(before),icons(after))
        for root in [before,after]:
            logo=next(n for n in root.iter('control') if n.findtext('texture')=='foundry-logo-traced.png')
            self.assertEqual([logo.findtext(x) for x in ('left','top','width','height')],['60','40','380','115'])

    def test_widget_uses_shared_library_metadata_and_identity_guards(self):
        text=(SKIN/'xml/Includes_WidgetMetadata.xml').read_text()
        for field in ['FoundryVODTitle','FoundryVODClearlogo','FoundryVODReleased','FoundryVODCertification','FoundryVODDetails','FoundryVODPlot','FoundryVODStudioLogo']:
            self.assertIn('$VAR['+field+']',text)
        self.assertIn('ControlGroup(2000).HasFocus',text)
        self.assertIn('<include>FoundryWidgetMetadata</include>',(SKIN/'xml/Home.xml').read_text())

    def test_widget_studio_sits_on_left_above_the_row_without_moving_widgets(self):
        root=E.parse(SKIN/'xml/Includes_WidgetMetadata.xml')
        logo=next(n for n in root.iter('control') if n.findtext('texture')=='$VAR[FoundryVODStudioLogo]')
        self.assertEqual(logo.findtext('left'),'92')
        self.assertLess(int(logo.findtext('top'))+int(logo.findtext('height')),612)
        home=E.parse(SKIN/'xml/Home.xml');self.assertEqual(home.find(".//control[@id='2000']/top").text,'510')

    def test_settings_hover_widget_wallpaper_has_priority_over_full_frame(self):
        root=E.parse(SKIN/'xml/Variables_Artwork.xml')
        first=root.find("variable[@name='FoundryHomeWallpaper']/value")
        self.assertIn('Control.HasFocus(802)',first.get('condition'))
        self.assertIn('FoundryHomeWidgetsPresent',first.get('condition'))
        self.assertEqual(first.text,'special://skin/media/foundry-widget-wallpapers/settings.png')
        present=E.parse(SKIN/'xml/Expressions.xml').find("expression[@name='FoundryHomeWidgetsPresent']").text
        self.assertNotIn('!ControlGroup(700).HasFocus',present)
        self.assertIn('Container(19011).NumItems',present)

    def test_page_number_is_clear_with_known_or_unknown_server_totals(self):
        state=CatalogState();self.assertEqual(state.page_label(),'Page 1')
        state.next_path='plugin://opaque/next';state.server_page=3
        self.assertEqual(state.page_label(),'Page 3')
        state.server_total_pages=999;self.assertEqual(state.page_label(),'Page 3')

    def test_loading_overlays_are_removed_but_source_errors_remain(self):
        for filename in ['View_57_StreamPilot.xml','script-foundry-vod.xml']:
            text=(SKIN/'xml'/filename).read_text()
            self.assertNotIn('<label>LOADING</label>',text)
            self.assertNotIn('<label>Preparing page</label>',text)
        self.assertIn('This source could not be loaded',(HELPER/'resources/lib/modules/catalog_window.py').read_text())

    def test_previous_complete_page_remains_visible_while_next_page_loads(self):
        root=E.parse(SKIN/'xml/script-foundry-vod.xml')
        hero=next(n for n in root.iter('control') if (n.findtext('description') or '').startswith('StreamPilot VodHero'))
        self.assertNotIn('catalog.loading',hero.findtext('visible'))

    def test_enrichment_does_not_reset_a_known_glow_or_rebuild_the_rail(self):
        from test_library_partial_load import PartialLoad
        module=importlib.import_module('modules.catalog_window')
        item={'title':'Retained','label':'Retained','type':'movie','file':'fixture://retained','plot':'Source plot'}
        window=PartialLoad().window([item])
        with patch.object(module,'listitem',side_effect=lambda i,*args:i):window.tick()
        window.p('accent','FF2255CC');window.clearList=Mock()
        window.set_hero(dict(window.hero,ratings={'tmdb':{'rating':8}}))
        self.assertEqual(window.getProperty('catalog.accent'),'FF2255CC');window.clearList.assert_not_called()

    def test_initial_page_selects_the_hero_once(self):
        from test_library_partial_load import PartialLoad
        module=importlib.import_module('modules.catalog_window')
        window=PartialLoad().window([{'title':'Film','type':'movie','file':'fixture://film'}])
        original=window.set_hero;window.set_hero=Mock(wraps=original)
        with patch.object(module,'listitem',side_effect=lambda i,*args:i):window.tick()
        window.set_hero.assert_called_once()

    def test_cached_artwork_color_is_ready_without_a_texture_rpc_or_decode(self):
        with tempfile.TemporaryDirectory() as temporary:
            source=Path(temporary)/'poster.png';Image.new('RGB',(80,120),'#2255CC').save(source)
            artwork='https://fixture.invalid/poster?opaque=DO_NOT_STORE'
            with patch.object(catalog_color,'cached_paths',return_value=[str(source)]):result=catalog_color.resolved(artwork)
            self.assertIsNotNone(result)
            with patch.object(catalog_color,'cached_paths',side_effect=AssertionError('No cache RPC should run')):
                self.assertEqual(catalog_color.resolved(artwork),result)
            self.assertNotIn('DO_NOT_STORE',catalog_color._index_path(artwork).read_text())

    def test_changed_source_invalidates_a_saved_color(self):
        with tempfile.TemporaryDirectory() as temporary:
            source=Path(temporary)/'poster.png';Image.new('RGB',(80,120),'#2255CC').save(source)
            artwork='fixture://changed-source'
            with patch.object(catalog_color,'cached_paths',return_value=[str(source)]):catalog_color.resolved(artwork)
            Image.new('RGB',(81,121),'#AACC22').save(source)
            self.assertIsNone(catalog_color.peek(artwork))

    def test_color_sampling_does_not_queue_behind_metadata_requests(self):
        module=importlib.import_module('modules.catalog_window');window=object.__new__(module.CatalogWindow)
        window.hero={'art':{'poster':'fixture://poster'}};window.color_job=None;window.color_cache={};window.color_retry=0;window.color_attempts=0
        window.color_executor=Mock();window.enrichment_executor=Mock();window.color_executor.submit.return_value=Future()
        window.tick_color(10)
        window.color_executor.submit.assert_called_once();window.enrichment_executor.submit.assert_not_called()

    def test_no_white_placeholder_can_appear_while_color_is_pending(self):
        root=E.parse(SKIN/'xml/View_57_StreamPilot.xml')
        glow=next(node for node in root.iter('control') if node.findtext('texture')=='$VAR[FoundryVODGlow]')
        self.assertEqual(root.findall("variable[@name='FoundryVODGlow']/value")[-1].text,'streampilot/glow-pending.svg')
        self.assertIn('FoundryVODGlowCurrentItem',glow.findtext('visible'))
        source=(HELPER/'resources/lib/modules/catalog_window.py').read_text()
        self.assertNotIn("'metacritic':'','accent':'FFFFFFFF'",source)

    def test_aborted_native_handoff_clears_its_visibility_guard(self):
        from modules import vod
        kodi.Window.values.clear();home=kodi.Window();home.setProperty('foundry.catalog.routing','true')
        with patch.object(kodi.xbmc,'getCondVisibility',return_value=False):self.assertFalse(vod.activate_catalog())
        self.assertEqual(home.getProperty('foundry.catalog.routing'),'')
