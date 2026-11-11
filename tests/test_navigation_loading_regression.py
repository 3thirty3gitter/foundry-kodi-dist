"""Slow-provider adoption keeps navigation visible and rejects stale results."""
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import test_release as kodi
from modules import vod, catalog_window
from modules.catalog_source import DirectorySource
from test_movie_submenu_wallpapers import SkinConditions

SKIN = Path(__file__).resolve().parents[2] / "skin.foundry-nimbus"

class NavigationLoading(unittest.TestCase):
    def tearDown(self):
        kodi.Window.values.clear()

    def test_pending_directory_keeps_wallpaper_without_intermediate_library(self):
        root = ET.parse(SKIN / 'xml/MyVideoNav.xml').getroot()
        native = root.find('controls/control[@type="group"]')
        self.assertIn('!$EXP[FoundryCatalogPending]', native.findtext('visible'))
        self.assertIn('foundry.catalog.active', native.findtext('visible'))
        labels = root.findall('controls/control[@type="label"]')
        loading = next(label for label in labels if label.findtext('label') == 'Loading library...')
        self.assertIn('$EXP[FoundryCatalogPending]', loading.findtext('visible'))
        backdrop = root.find('controls/control[@type="image"]/texture')
        self.assertEqual(backdrop.text, '$VAR[FoundryNativeLoadingBackdrop]')
        expression = ET.parse(SKIN / 'xml/Includes_Foundry.xml').findtext("expression[@name='FoundryCatalogPending']")
        self.assertIn('foundry.catalog.routing', expression)
        self.assertIn('Container.IsUpdating', expression)
        self.assertIn('!String.IsEqual(Window(Home).Property(foundry.catalog.handled_path),Container.FolderPath)', expression)
        fonts = {node.text for node in ET.parse(SKIN / 'xml/Font.xml').findall('.//font/name')}
        self.assertIn(loading.findtext('font'), fonts)

    def test_pending_expression_covers_first_frame_probe_and_cancel(self):
        expression = ET.parse(SKIN / 'xml/Includes_Foundry.xml').findtext("expression[@name='FoundryCatalogPending']")
        class Conditions(SkinConditions):
            def condition(self,text):
                if text.strip()=='Container.IsUpdating':return self.flags.get(text.strip(),False)
                return super().condition(text)
        context=Conditions({'Container.FolderPath':'plugin://movies/new','Window(Home).Property(foundry.catalog.handled_path)':'plugin://movies/old'}, {'Container.Content(movies)':True})
        self.assertTrue(context.condition(expression), 'Do not paint the native layout before the monitor tick')
        context.labels['Window(Home).Property(foundry.catalog.handled_path)']='plugin://movies/new'
        context.labels['Window(Home).Property(foundry.catalog.routing)']='true'
        self.assertTrue(context.condition(expression), 'Continue holding during the metadata probe')
        context.labels['Window(Home).Property(foundry.catalog.routing)']=''
        self.assertFalse(context.condition(expression), 'Nonmedia/error/cancel releases the native page')
        context.flags['Container.IsUpdating']=True
        self.assertTrue(context.condition(expression), 'Cover repeated navigation on the same path')
        context.flags['Container.IsUpdating']=False
        context.flags['Container.Content(movies)']=False
        context.labels['Container.FolderPath']=''
        self.assertFalse(context.condition(expression), 'Unrelated empty native directories remain available')
        context.labels['Window(Home).Property(foundry.catalog.routing)']='true'
        self.assertFalse(context.condition(expression), 'Onload probing must not hide an empty-content source menu')

    def test_late_provider_result_cannot_replace_newer_navigation(self):
        for changed in ('home', 'folder', 'updating', 'abort'):
            with self.subTest(changed=changed):
                kodi.Window.values.clear()
                state = {'active': True, 'path': 'plugin://fixture/list', 'updating': False}
                monitor = kodi.Monitor()
                def visible(query):
                    if query == 'Window.IsActive(videos)': return state['active']
                    if query == 'Container.IsUpdating': return state['updating']
                    return query in (vod.CATALOG_CONTENT, 'Container.Content(movies)')
                def load(_):
                    if changed == 'home': state['active'] = False
                    if changed == 'folder': state['path'] = 'plugin://fixture/new'
                    if changed == 'updating': state['updating'] = True
                    if changed == 'abort': monitor.aborted = True
                    return {'catalog_eligible': True, 'items': [{'type': 'movie', 'title': 'Film'}]}
                with patch.object(kodi.xbmc, 'getCondVisibility', side_effect=visible), \
                     patch.object(kodi.xbmc, 'getInfoLabel', side_effect=lambda q: state['path'] if q == 'Container.FolderPath' else ''), \
                     patch.object(kodi.xbmc, 'Monitor', return_value=monitor), \
                     patch.object(DirectorySource, 'load', autospec=True, side_effect=load), \
                     patch.object(catalog_window, 'open_catalog') as opened:
                    self.assertFalse(vod.activate_catalog())
                    opened.assert_not_called()
                self.assertEqual(kodi.Window().getProperty('foundry.catalog.routing'), '')
                self.assertEqual(kodi.Window().getProperty('foundry.catalog.opening'), '')

    def test_nonmedia_onload_probe_is_not_repeated_by_monitor(self):
        path = 'plugin://fixture/settings-menu'
        def visible(query):
            return query in ('Window.IsActive(videos)', vod.CATALOG_CONTENT, 'Container.Content(movies)', vod.CATALOG_CONTENT + ' | Container.Content(files)')
        with patch.object(kodi.xbmc, 'getCondVisibility', side_effect=visible), \
             patch.object(kodi.xbmc, 'getInfoLabel', side_effect=lambda q: path if q == 'Container.FolderPath' else ''), \
             patch.object(DirectorySource, 'load', return_value={'catalog_eligible': False}) as load, \
             patch.object(kodi.xbmc, 'executebuiltin') as launch:
            self.assertFalse(vod.activate_catalog())
            routing = vod.CatalogRoutingMonitor(clock=lambda: 100)
            routing.process()
            routing.process()
        load.assert_called_once()
        launch.assert_not_called()
        self.assertEqual(kodi.Window().getProperty('foundry.catalog.handled_path'), path)

if __name__ == '__main__': unittest.main()
