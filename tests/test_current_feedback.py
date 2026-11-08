"""Regression coverage for the approved widget, menu and catalog corrections."""
from pathlib import Path
from unittest.mock import patch
import json
import unittest
import xml.etree.ElementTree as E
from PIL import Image
import test_release as kodi
from modules.catalog_color import resolved, peek
from modules.vod import CatalogArtworkMonitor

ROOT=Path(__file__).resolve().parents[1]
SKIN=ROOT.parent/'skin.foundry-nimbus'


class Feedback(unittest.TestCase):
    def test_all_system_icon_references_exist_and_keep_their_chrome_colors(self):
        folder=SKIN/'media/foundry-icons'
        catalog=json.loads((folder/'CATALOG.json').read_text())
        self.assertEqual(len(catalog['icons']),52)
        for name in catalog['icons']:
            with Image.open(folder/(name+'.png')) as icon:
                self.assertEqual(icon.size,(256,256))
                self.assertEqual(icon.getpixel((0,0))[3],0)
            for state in ('normal','focus'):
                with Image.open(folder/'rows'/(name+'-'+state+'.png')) as row:
                    self.assertEqual(row.size,(320,70))
        for path in (SKIN/'xml').glob('*.xml'):
            for texture in E.parse(path).iter('texture'):
                if texture.text and texture.text.startswith('foundry-icons/'):
                    self.assertTrue((SKIN/'media'/texture.text).is_file(),texture.text)
                    self.assertIn(texture.get('colordiffuse'),(None,'FFFFFFFF'))
        buttons=E.parse(SKIN/'xml/Includes_Buttons.xml')
        for name in ('DefaultSettingButton','DefaultSystemSettingsButton','DefaultAddonSettingsButton','DialogSettingButton'):
            definition=buttons.find("include[@name='%s']/definition"%name)
            self.assertEqual(definition.findtext('textoffsetx'),'$PARAM[textoffsetx]')
            for state in ('texturefocus','texturenofocus'):
                texture=definition.find(state)
                self.assertEqual(texture.get('border'),'72,0,8,0')
                self.assertIn(texture.get('colordiffuse'),(None,'FFFFFFFF'))

    def test_original_home_icons_remain_in_place(self):
        home=E.parse(SKIN/'xml/Home.xml')
        icons=[p.get('value') for p in home.findall('.//param[@name="icon"]')]
        for name in ('power','settings','search','updates','fullscreen'):
            self.assertIn('icons/submenu/'+name+'.png',icons)

    def test_widget_details_use_the_shared_library_bindings_above_the_row(self):
        view=E.parse(SKIN/'xml/Includes_WidgetMetadata.xml')
        group=view.find("include[@name='FoundryWidgetMetadata']/control")
        self.assertIn('ControlGroup(2000).HasFocus',group.findtext('visible'))
        for field in ('Title','Plot','StudioLogo','Clearlogo'):
            self.assertIn('$VAR[FoundryVOD'+field+']',E.tostring(group,encoding='unicode'))
        studio=next(c for c in group.findall('control') if c.findtext('texture')=='$VAR[FoundryVODStudioLogo]')
        self.assertEqual(studio.findtext('left'),'92')
        self.assertLessEqual(int(studio.findtext('top'))+int(studio.findtext('height')),600)

    def test_persisted_glow_is_reused_without_rpc_or_image_decode_and_invalidates_when_art_changes(self):
        source=kodi.PROFILE/'persistent-color.png'
        Image.new('RGB',(30,30),'#3562A9').save(source)
        result=resolved(str(source))
        self.assertIsNotNone(result)
        with patch('modules.catalog_color.cached_paths',side_effect=AssertionError('unexpected RPC')),patch('modules.catalog_color.Image.open',side_effect=AssertionError('unexpected decode')):
            self.assertEqual(peek(str(source)),result)
            self.assertEqual(resolved(str(source)),result)
        source.write_bytes(source.read_bytes()+b'changed')
        self.assertIsNone(peek(str(source)))

    def test_native_focus_has_no_white_glow_while_uncached_artwork_is_prepared(self):
        kodi.Window.values.clear()
        labels={'ListItem.Art(fanart)':'fixture://uncached','ListItem.Label':'A film'}
        monitor=CatalogArtworkMonitor(clock=lambda:1)
        with patch.object(kodi.xbmc,'getCondVisibility',return_value=True),patch.object(kodi.xbmc,'getInfoLabel',side_effect=lambda key:labels.get(key,'')),patch('modules.catalog_color.peek',return_value=None):
            monitor.process_current_item()
        self.assertEqual(kodi.Window().getProperty('foundry.vod.glow'),'streampilot/glow-pending.svg')
        self.assertEqual(kodi.Window().getProperty('foundry.vod.accent'),'00FFFFFF')

    def test_cached_native_focus_restores_the_matched_color_immediately(self):
        kodi.Window.values.clear()
        labels={'ListItem.Art(fanart)':'fixture://cached','ListItem.Label':'A film'}
        monitor=CatalogArtworkMonitor(clock=lambda:1)
        with patch.object(kodi.xbmc,'getCondVisibility',return_value=True),patch.object(kodi.xbmc,'getInfoLabel',side_effect=lambda key:labels.get(key,'')),patch('modules.catalog_color.peek',return_value=('FF123456','known-glow.png')):
            monitor.process_current_item()
        self.assertEqual(kodi.Window().getProperty('foundry.vod.glow'),'known-glow.png')
        self.assertEqual(kodi.Window().getProperty('foundry.vod.accent'),'FF123456')


if __name__=='__main__':unittest.main()

