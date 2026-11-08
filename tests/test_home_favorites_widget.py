"""Review-candidate Home Favorites contracts; no live provider or saved favorites writes."""
from pathlib import Path
import hashlib,json,re,sys,unittest
import xml.etree.ElementTree as E
import zipfile
import test_release as kodi
from home_contracts import restore_home_feature_additions

SKIN=kodi.SKIN
BASELINE=kodi.ROOT/'skin.foundry/skin.foundry-1.3.9.zip'
def xml(name):return E.parse(SKIN/'xml'/name)
def original(name):
    with zipfile.ZipFile(BASELINE) as bundle:return E.fromstring(bundle.read('skin.foundry/xml/'+name))
def normalized(node):return (node.tag,node.attrib,(node.text or '').strip(),[normalized(c) for c in node])

def evaluate(text,labels,expressions,flags=None):
    """Evaluate the bounded subset of Kodi skin conditions used by these guards."""
    flags=flags or {};text=text.strip()
    def split(source,separator):
        depth=0;parts=[];start=0
        for i,char in enumerate(source):
            if char in '([':depth+=1
            elif char in ')]':depth-=1
            elif char==separator and depth==0:parts.append(source[start:i]);start=i+1
        return parts+[source[start:]]
    for delimiter,operation in [('|',any),('+',all)]:
        parts=split(text,delimiter)
        if len(parts)>1:return operation(evaluate(p,labels,expressions,flags) for p in parts)
    if text.startswith('!'):return not evaluate(text[1:],labels,expressions,flags)
    if text.startswith('$EXP['):return evaluate(expressions[text[5:-1]],labels,expressions,flags)
    if text.startswith('[') and text.endswith(']'):return evaluate(text[1:-1],labels,expressions,flags)
    if text in flags:return flags[text]
    if text in ('true','false'):return text=='true'
    def value(token):
        token=token.strip()
        return labels.get(token,'') if token.startswith(('ListItem.','Window(')) else token
    if text.startswith('String.'):
        name,args=text.split('(',1);args=[value(p) for p in split(args[:-1],',')]
        if name=='String.IsEqual':return args[0]==args[1]
        if name=='String.IsEmpty':return not args[0]
        if name=='String.StartsWith':return args[0].startswith(args[1])
    raise AssertionError('Unsupported guard: '+text)

class FavoritesWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expressions={n.get('name'):n.text for name in ['Includes_WidgetMetadata.xml'] for n in xml(name).findall('expression')}
        cls.expressions.update({n.get('name'):n.text for n in original('Includes_Metadata.xml').findall('expression')})
        cls.visibility=xml('Includes_WidgetMetadata.xml').findtext("include[@name='FoundryWidgetMetadata']/control/visible")
    def favorite_labels(self,kind='movie'):
        path='favourites://PlayMedia%28%22fixture%3A%2F%2Ffilm%22%29/'
        return {'ListItem.Label':'My saved alias','ListItem.FileNameAndPath':path,
                'Window(Home).Property(foundry.metadata.owner_label)':'My saved alias',
                'Window(Home).Property(foundry.metadata.owner_path)':path,
                'Window(Home).Property(foundry.metadata.media_type)':kind,
                'Window(Home).Property(foundry.metadata.poster)':'resolved-poster.png'}
    def visible(self,labels,home=True,focus=True):
        return evaluate(self.visibility,labels,self.expressions,{'Window.IsActive(Home)':home,'ControlGroup(2000).HasFocus':focus})
    def test_changed_skin_xml_files_parse(self):
        for name in ['Home.xml','Includes_Home.xml','Includes_HomeLayouts.xml','Includes_WidgetMetadata.xml']:xml(name)
    def test_favorites_reuses_the_regular_poster_widget(self):
        group=xml('Home.xml').find(".//control[@id='14000']")
        viewport=group.find("control[@id='14001']")
        self.assertEqual(viewport.findtext('include'),'HomeWidgetGroupListCommon')
        row=viewport.find("include[@content='WidgetListPoster']")
        self.assertIsNotNone(row)
        params={p.get('name'):p.get('value') for p in row.findall('param')}
        self.assertEqual(params['list_id'],'14100');self.assertEqual(params['content_path'],'favourites://')
        self.assertIsNone(group.find(".//control[@type='panel']"))
    def test_native_favorite_order_actions_and_context_menu_remain_kodi_owned(self):
        group=xml('Home.xml').find(".//control[@id='14000']")
        params={p.get('name'):p.get('value') for p in group.findall(".//include[@content='WidgetListPoster']/param")}
        for name in ['widget_target','sortby','sortorder','limit']:self.assertEqual(params[name],'')
        self.assertEqual(group.findall('.//onclick'),[])
        self.assertEqual(group.findall('.//onfocus'),[])
        common=xml('Includes_Home.xml').find("include[@name='WidgetListPoster']")
        self.assertEqual(common.find("param[@name='onclick_condition']").text,'false')
    def test_regular_widget_geometry_and_focus_navigation_are_unchanged(self):
        before=original('Includes_Home.xml')
        after=xml('Includes_Home.xml')
        for name in ['WidgetListPoster','WidgetListCommon','HomeWidgetGroupListCommon']:
            left=before.find("include[@name='%s']"%name);right=after.find("include[@name='%s']"%name)
            for node in right.iter('visible'):
                if node.text:node.text=node.text.replace(' | Integer.IsEqual($PARAM[list_id],14100)','')
            self.assertEqual(normalized(left),normalized(right),name)
        common=after.find("include[@name='WidgetListCommon']")
        back=next(n for n in common.findall('onback') if n.get('condition')=='Window.IsActive(Home)')
        self.assertEqual(back.text,'9000')
        self.assertFalse(any('SetFocus' in (n.text or '') for n in common.findall('onfocus')))
    def test_favorites_row_and_label_are_included_in_home_visibility_masks(self):
        text=(SKIN/'xml/Includes_Home.xml').read_text()
        self.assertEqual(text.count(' | Integer.IsEqual($PARAM[list_id],14100) | '),13)
        poster=xml('Includes_Home.xml').find("include[@name='WidgetListPoster']")
        for group in poster.findall('.//itemlayout/control')+poster.findall('.//focusedlayout/control'):
            self.assertIn('Integer.IsEqual($PARAM[list_id],14100)',group.findtext('visible'))
    def test_resolved_movie_tv_season_and_episode_favorites_show_metadata_without_dbtype(self):
        for kind in ['movie','tvshow','season','episode']:
            with self.subTest(kind=kind):self.assertTrue(self.visible(self.favorite_labels(kind)))
    def test_unresolved_or_nonmedia_favorites_do_not_show_invented_details(self):
        labels=self.favorite_labels();labels.pop('Window(Home).Property(foundry.metadata.owner_label)')
        self.assertFalse(self.visible(labels))
        for kind in ['', 'favorite','file','addon']:
            self.assertFalse(self.visible(self.favorite_labels(kind)))
    def test_focus_changes_alias_changes_and_wrong_targets_reject_stale_details(self):
        for field,new_value in [('ListItem.Label','Different alias'),('ListItem.FileNameAndPath','favourites://different/'),('ListItem.DBTYPE','episode')]:
            labels=self.favorite_labels();labels[field]=new_value
            self.assertFalse(evaluate('$EXP[FoundryWidgetResolvedFavorite]',labels,self.expressions),field)
            if field!='ListItem.DBTYPE':self.assertFalse(self.visible(labels),field)
    def test_resolved_metadata_cannot_leak_to_nonfavorite_actions(self):
        labels=self.favorite_labels();labels['ListItem.FileNameAndPath']='plugin://settings'
        labels['Window(Home).Property(foundry.metadata.owner_path)']='plugin://settings'
        self.assertFalse(self.visible(labels))
    def test_menu_focus_and_other_windows_hide_widget_metadata(self):
        labels=self.favorite_labels()
        self.assertFalse(self.visible(labels,home=False));self.assertFalse(self.visible(labels,focus=False))
    def test_regular_native_media_still_shows_existing_metadata_panel(self):
        for kind in ['movie','tvshow','season','episode','video']:
            self.assertTrue(self.visible({'ListItem.DBTYPE':kind}))
    def test_resolved_favorite_poster_uses_the_normal_poster_layout(self):
        labels=self.favorite_labels()
        self.assertTrue(evaluate('$EXP[FoundryWidgetHasPoster]',labels,self.expressions))
        labels['ListItem.FileNameAndPath']='favourites://other/'
        self.assertFalse(evaluate('$EXP[FoundryWidgetHasPoster]',labels,self.expressions))
        layout=xml('Includes_HomeLayouts.xml').find("include[@name='FlixWidgetMovieLayout']")
        self.assertEqual(layout.findtext('definition/control/visible'),'!$EXP[FoundryWidgetHasPoster]')
        self.assertEqual(layout.findall('definition/control')[1].findtext('visible'),'$EXP[FoundryWidgetHasPoster]')
    def test_existing_artwork_keeps_its_original_poster_eligibility(self):
        for field in ['ListItem.Art(poster)','ListItem.Art(fanart)']:
            self.assertTrue(evaluate('$EXP[FoundryWidgetHasPoster]',{field:'source-art.png'},self.expressions))
    def test_shared_details_ratings_clearlogo_and_studio_logo_are_not_reimplemented(self):
        before=original('Includes_WidgetMetadata.xml').find("include[@name='FoundryWidgetMetadata']")
        after=xml('Includes_WidgetMetadata.xml').find("include[@name='FoundryWidgetMetadata']")
        before.find('control/visible').text=after.findtext('control/visible')
        self.assertEqual(normalized(before),normalized(after))
    def test_all_other_home_categories_wallpaper_header_and_actions_are_unchanged(self):
        before=original('Home.xml');after=restore_home_feature_additions(xml('Home.xml').getroot())
        for root in [before,after]:
            parent=root.find(".//control[@id='2000']");parent.remove(parent.find("control[@id='14000']"))
        self.assertEqual(normalized(before),normalized(after))

if __name__=='__main__':unittest.main(verbosity=2)
