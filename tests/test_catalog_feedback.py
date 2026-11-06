"""Regressions from native-library testing of the published 1.3.3 build."""
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as E
import test_release as kodi
from modules.catalog_model import split_directory
from modules.monitors.metadata import MetadataMonitor,snapshot

ROOT=Path(__file__).resolve().parents[2]

class CatalogFeedback(unittest.TestCase):
    def test_native_glow_requires_the_focused_layout_and_row_focus(self):
        doc=E.parse(ROOT/'skin.foundry-nimbus/xml/View_57_StreamPilot.xml')
        glow=doc.find(".//control[texture='$VAR[FoundryVODGlow]']")
        self.assertEqual(glow.findtext('visible'),'$PARAM[focused] + Control.HasFocus(57)')

    def test_removed_controls_have_no_remaining_navigation_targets(self):
        for name in ('View_57_StreamPilot.xml','script-foundry-vod.xml'):
            doc=E.parse(ROOT/'skin.foundry-nimbus/xml'/name)
            for control in ('5702','5703','5704','5705'):
                self.assertIsNone(doc.find(".//control[@id='%s']"%control))
            for node in doc.iter():
                if node.tag in ('onup','ondown','onleft','onright'):
                    self.assertNotIn(node.text,('5702','5703','5704','5705'))
            self.assertNotIn('catalog-search.png',E.tostring(doc.getroot(),encoding='unicode'))

    def test_native_provider_page_entries_use_inline_arrows_not_icons(self):
        doc=E.parse(ROOT/'skin.foundry-nimbus/xml/View_57_StreamPilot.xml')
        poster=doc.find("include[@name='FoundryVODPoster']/definition")
        text=E.tostring(poster,encoding='unicode')
        self.assertIn('!$EXP[FoundryVODNextItem] + !$EXP[FoundryVODPreviousItem]',text)
        self.assertIn('catalog-next-focus.png',text)
        self.assertIn('catalog-previous-focus.png',text)
        self.assertIn('ListItem.IsParentFolder',doc.findtext("expression[@name='FoundryVODPreviousItem']"))

    def test_numbered_and_styled_provider_pagination_does_not_become_posters(self):
        urls=['plugin://source/?page=2&token=untouched','plugin://source/?page=1']
        items=[{'label':'Film','title':'Film','filetype':'file','file':'movie'},
               {'label':'[B]Next Page (2 of 3) >>[/B]','filetype':'directory','file':urls[0]},
               {'label':'<< Previous Page 1','filetype':'directory','file':urls[1]}]
        media,nxt,previous=split_directory(items)
        self.assertEqual([i['title'] for i in media],['Film'])
        self.assertEqual((nxt,previous),tuple(urls))

    def test_native_snapshot_preserves_named_ratings_and_studio_art(self):
        labels={'ListItem.DBTYPE':'movie','ListItem.Label':'Film','ListItem.Title':'Film',
                'ListItem.Year':'2020','ListItem.Rating(tmdb)':'7.3','ListItem.Rating(imdb)':'8.1',
                'ListItem.Art(studiologo)':'studio.png','ListItem.DBID':'9'}
        with patch.object(kodi.xbmc,'getInfoLabel',side_effect=lambda key:labels.get(key,'')):
            owner,item=snapshot()
        self.assertEqual(item['ratings']['tmdb']['rating'],7.3)
        self.assertEqual(item['ratings']['imdb']['rating'],8.1)
        self.assertEqual(item['art']['studiologo'],'studio.png')
        self.assertEqual(item['id'],9)

    def test_shared_native_monitor_uses_library_and_tmdbhelper_enrichment(self):
        monitor=object.__new__(MetadataMonitor);monitor.provider=None
        with patch('modules.catalog_enrichment.enrich_with_status',return_value=({},{})) as call:
            monitor.enrich({'id':9,'foundry.native_library':True},'Movies')
        self.assertTrue(call.call_args.kwargs['native_library'])

    def test_native_rating_and_studio_variables_accept_shared_metadata(self):
        doc=E.parse(ROOT/'skin.foundry-nimbus/xml/View_57_StreamPilot.xml')
        for var,field in [('FoundryVODTMDb','tmdb'),('FoundryVODIMDb','imdb'),('FoundryVODStudioLogo','studiologo')]:
            values=E.tostring(doc.find("variable[@name='%s']"%var),encoding='unicode')
            self.assertIn('foundry.metadata.'+field,values)
            self.assertIn('FoundryMetadataCurrentItem',values)

if __name__=='__main__':unittest.main()
