"""Source-scoped Movies submenu routing through real helper navigation."""
from unittest.mock import Mock, patch
import unittest
import test_release as kodi
import test_catalog_handoff as handoff
from modules import catalog_window
from modules.catalog_source import DirectorySource
from modules.movie_submenu import LABELS, canonical_label, movie_context


class MovieSubmenuContext(unittest.TestCase):
    def tearDown(self):
        kodi.Window.values.clear()

    def window(self):
        w=handoff.CatalogHandoff().window({'items':handoff.CatalogHandoff().items()})
        w.stack=[]
        w.clearProperty=lambda name:w.setProperty(name,'')
        w.source.movie_submenu_label='Trending'
        w.section='Movies'
        with patch.object(catalog_window,'listitem',side_effect=lambda item,*_:item):
            w.onInit()
        return w

    def test_only_exact_approved_label_or_terminal_breadcrumb_matches(self):
        for label in LABELS:
            self.assertEqual(canonical_label('  VOD / Movies / '+label+'  '),label)
            self.assertEqual(canonical_label(label.lower()),label)
        for value in ('Popular People','Trending Now','Movies / Trending / More','Trending / TV Shows',
                      'plugin://provider/Trending','TrendingRecent','Upcoming','Top 10 Box Office Hits',None):
            self.assertEqual(canonical_label(value),'',value)
        self.assertEqual(canonical_label('Provider','VOD > Movies > Popular Today'),'Popular Today')

    def test_movie_classification_is_required_and_mixed_actions_clear(self):
        movie={'type':'movie'}
        self.assertEqual(movie_context('Movies',[movie],'','Trending'),'Trending')
        for items in ([{'type':'tvshow'}],[movie,{'type':'episode'}],[movie,{'type':'unknown'}],[{}]):
            self.assertEqual(movie_context('Movies',items,'movies','Trending',True),'')
        self.assertEqual(movie_context('TV Shows',[movie],'movies','Trending',True),'')
        self.assertEqual(movie_context('Videos',[movie],'movies','Trending',True),'')
        self.assertEqual(movie_context('Movies',[],'','Trending'),'')
        self.assertEqual(movie_context('Movies',[],'movies','Trending'),'Trending')

    def test_initial_movie_page_publishes_canonical_window_property(self):
        w=self.window()
        self.assertEqual(w.getProperty('foundry.movie_submenu_label'),'Trending')
        self.assertTrue(w.source.movie_submenu_verified)

    def test_server_paging_retains_context_and_back_restores_owned_source(self):
        w=self.window();parent=w.source
        w.state.next_path='plugin://fixture/next?opaque=a%26b'
        w.turn_page('next')
        self.assertNotEqual(w.source,parent)
        self.assertEqual(w.source.path,'plugin://fixture/next?opaque=a%26b')
        self.assertEqual(w.source.movie_submenu_label,'Trending')
        self.assertEqual(w.getProperty('foundry.movie_submenu_label'),'Trending')
        with patch.object(catalog_window,'listitem',side_effect=lambda item,*_:item):w.back()
        self.assertIs(w.source,parent)
        self.assertEqual(w.getProperty('foundry.movie_submenu_label'),'Trending')

    def test_unrelated_child_clears_context_and_back_restores_it(self):
        w=self.window();parent=w.source
        w.rail=[{'type':'tvshow','filetype':'directory','file':'plugin://fixture/other?opaque=a%26b'}]
        w.index=0
        w.onClick(50)
        self.assertEqual(w.source.path,'plugin://fixture/other?opaque=a%26b')
        self.assertEqual(w.getProperty('foundry.movie_submenu_label'),'')
        self.assertEqual(w.source.movie_submenu_label,'')
        with patch.object(catalog_window,'listitem',side_effect=lambda item,*_:item):w.back()
        self.assertIs(w.source,parent)
        self.assertEqual(w.getProperty('foundry.movie_submenu_label'),'Trending')

    def test_rehydration_after_native_playback_preserves_submenu_and_selection(self):
        w=self.window();w.native.clear()
        with patch.object(catalog_window,'listitem',side_effect=lambda item,*_:item):w.onInit()
        self.assertEqual(w.getProperty('foundry.movie_submenu_label'),'Trending')
        self.assertEqual(len(w.native),1)
        self.assertEqual(w.hero['file'],handoff.CatalogHandoff().items()[0]['file'])
        w.source.load.assert_not_called()

    def test_mixed_result_and_nonmedia_handoff_clear_submenu(self):
        w=self.window();w.state.items=[{'type':'movie'},{'type':'tvshow'}]
        w.update_movie_submenu_context()
        self.assertEqual(w.getProperty('foundry.movie_submenu_label'),'')
        self.assertFalse(w.source.movie_submenu_verified)
        w.setProperty('foundry.movie_submenu_label','Trending')
        w.open_native=Mock(side_effect=lambda _:self.assertEqual(w.getProperty('foundry.movie_submenu_label'),''))
        self.assertFalse(w.apply_page({'catalog_eligible':False}))
        w.open_native.assert_called_once()

    def test_context_does_not_replace_source_art_or_playback_url(self):
        w=self.window();original=handoff.CatalogHandoff().items()[0]
        self.assertEqual(w.hero['art'],original['art'])
        self.assertEqual(w.hero['file'],original['file'])

    def test_search_classification_clears_and_restoring_library_recovers_context(self):
        w=self.window();w.library_state=w.state;w.edit_value='';w.history=[]
        native_control=w.getControl
        search_control=Mock()
        w.getControl=lambda cid:search_control if cid==51 else native_control(cid)
        with patch.object(catalog_window,'listitem',side_effect=lambda item,*_:item):
            w.search_results([{'type':'tvshow','title':'Different media','file':'plugin://fixture/tv'}])
        self.assertEqual(w.getProperty('foundry.movie_submenu_label'),'')
        w.leave_search()
        self.assertEqual(w.getProperty('foundry.movie_submenu_label'),'Trending')
        self.assertEqual(w.state.items[0]['file'],handoff.CatalogHandoff().items()[0]['file'])
