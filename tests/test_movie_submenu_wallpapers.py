"""Approved Movies submenu bytes, routing, fallback priority and preserved Home."""
from pathlib import Path
import hashlib,json,re,unittest,zipfile
import xml.etree.ElementTree as E
from home_contracts import normalized,restore_home_feature_additions

ROOT=Path(__file__).resolve().parents[1]
SKIN=ROOT.parent/'skin.foundry-nimbus'
APPROVED={
 'Trending':('trending','6928e49789f98ebd39ea1c3ff58a6f10345742161a23e2bc4d1619636deaea4a'),
 'Trending Recent':('trending-recent','988405977d861693d8e5ad0c65a44024a09bd227e7ba662cdfde8acc90f5cc71'),
 'Popular':('popular','a9f54cd64f1bd5bb0573294e6416163b45f8729dde7817f4a3a91e3beb2430c7'),
 'Popular Today':('popular-today','b583c971a4cee760773ff63247675a5f8d22dc2e6fcf870fb2fe2c89cc69c924'),
 'Premieres':('premieres','099d321d4d5ef84a6d3bcd5e59641dbb50f46eb1488861ac1c816c38b93fe221'),
 'Latest Releases':('latest-releases','5b2f00878909400094b2dc275bc037d04fd2d3c58a7c4b18aa12c99094b94260'),
 'Most Watched':('most-watched','60cfa20ec05ec7d8e0a98bf25830a8649ea1613a0577fd4920dfeffa068df5bb'),
 'Most Favorited':('most-favorited','6f2501b34ca42055ba36e0d34c317c7d7e9181037d3ebd17d35a96a532a31253'),
 'Top 10 Box Office':('top-10-box-office','0b585ff023a885b447a89ab711bfe1ddba5779e003fbd47ede1852f3adebe89a'),
 'Blockbusters':('blockbusters','bca0e25af74ba4760dae905513a08696a69f9e3632384a455ff79c8cfee83606'),
 'In Theaters':('in-theaters','fbedbfb72d6b2b3d05559204d1daa4421d4dd3573ba2829e8bd5ab16e2a61b3c'),
 'Up Coming':('up-coming','b93dc18a0cbc5ae7ca5373dcd3ea93a7339a095f728b503278548faa6aebe8f0'),
 'Oscar Winners':('oscar-winners','f82d322381b6d5952648e80b4ece8343235be293899cc693a74cf5e1af0f399d')}


def split(text,delimiter):
    depth=0;parts=[];start=0
    for index,char in enumerate(text):
        if char in '([':depth+=1
        elif char in ')]':depth-=1
        elif char==delimiter and not depth:parts.append(text[start:index]);start=index+1
    return parts+[text[start:]]


class SkinConditions:
    """Evaluate actual XML using the documented Kodi boolean/label subset."""
    def __init__(self,labels=None,flags=None):
        root=E.parse(SKIN/'xml/Includes_FoundryMovieSubmenus.xml')
        self.expressions={n.get('name'):n.text for n in root.findall('expression')}
        self.variables={n.get('name'):n for n in root.findall('variable')}
        self.labels=labels or {};self.flags=flags or {}
    def value(self,token):
        token=token.strip()
        if token.startswith(('ListItem.','Container.','Window.','Window(','Skin.')):return self.labels.get(token,'')
        return token
    def condition(self,text):
        text=text.strip()
        for delimiter,operation in [('|',any),('+',all)]:
            parts=split(text,delimiter)
            if len(parts)>1:return operation(self.condition(p) for p in parts)
        if text.startswith('!'):return not self.condition(text[1:])
        if text.startswith('$EXP['):return self.condition(self.expressions[text[5:-1]])
        if text.startswith('[') and text.endswith(']'):return self.condition(text[1:-1])
        if text.startswith('String.'):
            name,args=text.split('(',1);args=[self.value(p) for p in split(args[:-1],',')]
            if name=='String.IsEqual':return args[0].casefold()==args[1].casefold()
            if name=='String.IsEmpty':return not args[0]
        if text.startswith(('Window.IsActive(','Container.Content(','Control.IsVisible(','ListItem.Is','Player.')):return self.flags.get(text,False)
        raise AssertionError('Unsupported Kodi condition: '+text)
    def variable(self,name):
        for node in self.variables[name].findall('value'):
            if not node.get('condition') or self.condition(node.get('condition')):
                text=node.text or ''
                text=re.sub(r'\$VAR\[([^]]+)\]',lambda match:self.variable(match[1]),text)
                return re.sub(r'\$INFO\[([^]]+)\]',lambda match:self.value(match[1]),text)
        return ''


def native(label='',folder='Movies',content='videos',category='movies',is_folder=True,window='videos',extra=None):
    labels={'ListItem.Label':label,'Container.FolderName':folder,'Container.Content':content,'Window(Home).Property(foundry.navigation.category)':category}
    labels.update(extra or {})
    return SkinConditions(labels,{'Window.IsActive('+window+')':True,'Container.Content('+content+')':True,'ListItem.IsFolder':is_folder})


class MoviesSubmenuWallpapers(unittest.TestCase):
    def test_all_thirteen_bytes_and_manifest_match_independent_approved_hashes(self):
        manifest=json.loads((SKIN/'media/foundry-movie-submenus/SOURCE-trending-fixed-20261111.json').read_text())
        approved=json.loads((ROOT/'tests/fixtures/approved-wallpapers-trending-fixed-20261111.json').read_text())
        self.assertEqual(manifest['dimensions'],[1672,941]);self.assertEqual(len(manifest['files']),13)
        self.assertEqual({i['label'] for i in manifest['files']},set(APPROVED))
        for item in manifest['files']:
            slug,_=APPROVED[item['label']];digest=approved['categories/'+slug+'.png']['sha256'];relative='media/foundry-movie-submenus/'+slug+'.png'
            self.assertEqual(item['filename'],slug+'.png');self.assertEqual(item['sha256'],digest)
            data=(SKIN/relative).read_bytes();self.assertEqual(hashlib.sha256(data).hexdigest(),digest);self.assertEqual(len(data),item['bytes'])
            self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n');self.assertEqual((int.from_bytes(data[16:20],'big'),int.from_bytes(data[20:24],'big')),(1672,941))
    def test_native_folder_focus_and_opened_results_use_each_exact_label(self):
        for label,(slug,_) in APPROVED.items():
            expected='special://skin/media/foundry-movie-submenus/'+slug+'.png'
            with self.subTest(label=label):
                self.assertEqual(native(label).variable('FoundryMovieSubmenuWallpaper'),expected)
                self.assertEqual(native('A film title',label,'movies',is_folder=False).variable('FoundryMovieSubmenuWallpaper'),expected)
    def test_focused_known_child_wins_over_approved_parent_folder(self):
        self.assertTrue(native('Popular','Trending').variable('FoundryMovieSubmenuWallpaper').endswith('/popular.png'))
    def test_movies_unknown_root_and_similar_labels_use_existing_fallback(self):
        for label in ['Movies','Trending Now','Popular Today Extra','Upcoming','Oscar Winner','Settings','']:
            self.assertEqual(native(label).variable('FoundryMovieSubmenuBase'),'streampilot/catalog-base.png')
        self.assertEqual(native('Trending',is_folder=False).variable('FoundryMovieSubmenuWallpaper'),'')
    def test_tv_addon_and_other_home_sections_reject_movies_art(self):
        for content in ['tvshows','seasons','episodes','addons','games','songs','pictures']:
            self.assertEqual(native('Trending','Popular',content).variable('FoundryMovieSubmenuWallpaper'),'')
        for category in ['tvshows','settings','music','addons','games','video','']:
            self.assertEqual(native('Trending',category=category).variable('FoundryMovieSubmenuWallpaper'),'')
        for window in ['home','games','settings','pictures']:
            self.assertEqual(native('Trending',window=window).variable('FoundryMovieSubmenuWallpaper'),'')
    def test_explicit_untyped_tv_folder_or_plugin_category_rejects_stale_home_movies(self):
        for label in ['TV Shows','TV','Television']:
            for content in ['videos','files','']:
                with self.subTest(label=label,content=content):
                    self.assertEqual(native('Trending',label,content).variable('FoundryMovieSubmenuWallpaper'),'')
                    self.assertEqual(native('Trending','Movies',content,extra={'Container.PluginCategory':label}).variable('FoundryMovieSubmenuWallpaper'),'')
    def test_parent_folder_uses_back_plate_or_current_directory_art(self):
        context=native('Trending');context.flags['ListItem.IsParentFolder']=True
        self.assertTrue(context.variable('FoundryMovieSubmenuWallpaper').endswith('/movies-back.png'))
        context.labels['Container.FolderName']='Trending'
        self.assertTrue(context.variable('FoundryMovieSubmenuWallpaper').endswith('/trending.png'))
    def test_catalog_requires_verified_movies_property_not_selected_title(self):
        for label,(slug,_) in APPROVED.items():
            context=SkinConditions({'Window.Property(catalog.section)':'Movies','Window.Property(foundry.movie_submenu_label)':label,'ListItem.Label':'Unrelated film'})
            self.assertTrue(context.variable('FoundryMovieSubmenuWallpaper').endswith('/'+slug+'.png'))
        for section,label in [('TV Shows','Trending'),('Videos','Popular'),('Movies',''),('Movies','Not approved')]:
            context=SkinConditions({'Window.Property(catalog.section)':section,'Window.Property(foundry.movie_submenu_label)':label})
            self.assertEqual(context.variable('FoundryMovieSubmenuWallpaper'),'')
    def test_custom_backgrounds_retain_priority(self):
        context=native('Trending',extra={'Skin.String(HomeFanart.path)':'/custom/','Skin.String(HomeFanart.ext)':'.jpg','Skin.String(NimbusCustomBackground)':'other.jpg'})
        self.assertEqual(context.variable('FoundryMovieSubmenuBase'),'/custom/movies.jpg')
        del context.labels['Skin.String(HomeFanart.path)'];self.assertEqual(context.variable('FoundryMovieSubmenuBase'),'other.jpg')
        visible=E.parse(SKIN/'xml/Includes_FoundryMovieSubmenus.xml').findtext("include[@name='FoundryMovieSubmenuBackdrop']/control/visible")
        self.assertFalse(context.condition(visible))
    def test_loading_backdrop_retains_movies_wallpaper_when_provider_clears_labels(self):
        context=native('',folder='',content='')
        self.assertEqual(context.variable('FoundryNativeLoadingBackdrop'),'resource://resource.images.foundry.wallpapers/movies.png')
        context.labels['Skin.String(NimbusCustomBackground)']='custom.jpg'
        self.assertEqual(context.variable('FoundryNativeLoadingBackdrop'),'custom.jpg')
        context.labels.update({'Skin.String(HomeFanart.path)':'/custom/','Skin.String(HomeFanart.ext)':'.png'})
        self.assertEqual(context.variable('FoundryNativeLoadingBackdrop'),'/custom/movies.png')
    def test_native_movie_fanart_priority_and_folder_art_surface(self):
        visible=E.parse(SKIN/'xml/Includes_FoundryMovieSubmenus.xml').findtext("include[@name='FoundryMovieSubmenuBackdrop']/control/visible")
        context=native('Film','Trending','movies',is_folder=False,extra={'ListItem.Art(fanart)':'film.jpg'})
        self.assertFalse(context.condition(visible));del context.labels['ListItem.Art(fanart)'];self.assertTrue(context.condition(visible))
        context=native('Trending',extra={'ListItem.Art(fanart)':'generic-provider.jpg'});self.assertTrue(context.condition(visible))
    def test_catalog_fallback_is_beneath_unchanged_selected_title_fanart(self):
        with zipfile.ZipFile(ROOT/'skin.foundry/skin.foundry-1.4.0.zip') as bundle:
            for filename in ['script-foundry-vod.xml','View_57_StreamPilot.xml']:
                before=E.fromstring(bundle.read('skin.foundry/xml/'+filename));after=E.parse(SKIN/'xml'/filename).getroot()
                expected='$VAR[FoundryCatalogFirstPaintBackdrop]' if filename=='script-foundry-vod.xml' else '$VAR[FoundryMovieSubmenuBase]'
                old=[n for n in before.iter('control') if n.findtext('texture')=='streampilot/catalog-base.png'];new=[n for n in after.iter('control') if n.findtext('texture')==expected]
                self.assertEqual(len(old),1);self.assertEqual(len(new),1)
                new[0].find('texture').text='streampilot/catalog-base.png';new[0].find('texture').attrib.clear()
                if filename=='View_57_StreamPilot.xml':
                    # Studio-logo resolution is independently covered by test_studio_art.
                    # Preserve the strict comparison for all artwork/layout controls.
                    for tree in (before,after):
                        tree.remove(tree.find("variable[@name='FoundryVODStudioLogo']"))
                self.assertEqual(normalized(before),normalized(after))
    def test_first_catalog_frame_uses_loading_backdrop_only_before_section_ready(self):
        context=SkinConditions({'Window(Home).Property(foundry.navigation.category)':'movies'})
        self.assertEqual(context.variable('FoundryCatalogFirstPaintBackdrop'),'resource://resource.images.foundry.wallpapers/movies.png')
        context.labels['Window.Property(catalog.section)']='TV Shows'
        self.assertEqual(context.variable('FoundryCatalogFirstPaintBackdrop'),'streampilot/catalog-base.png')
        context.labels.update({'Window.Property(catalog.section)':'Movies','Window.Property(foundry.movie_submenu_label)':'Popular Today'})
        self.assertTrue(context.variable('FoundryCatalogFirstPaintBackdrop').endswith('/popular-today.png'))
    def test_legacy_fullscreen_provider_art_cannot_cover_approved_category(self):
        root=E.parse(SKIN/'xml/View_50_List.xml')
        overlays=[n for n in root.iter('control') if n.find('texture') is not None and n.find('texture').get('diffuse')=='overlays/fanart-diffuse.png']
        self.assertEqual(len(overlays),1)
        self.assertTrue(overlays[0].findtext('visible').strip().startswith('!$EXP[FoundryMovieSubmenuBackdropVisible] +'))
        for label in APPROVED:
            self.assertTrue(native(label,extra={'ListItem.Art(fanart)':'provider-gears.jpg'}).condition('$EXP[FoundryMovieSubmenuBackdropVisible]'))
        for context in [native('Unknown'),native('Popular Today',category='tvshows'),native('Film','Popular Today','movies',is_folder=False,extra={'ListItem.Art(fanart)':'film.jpg'}),native('Popular Today',extra={'Skin.String(NimbusCustomBackground)':'custom.jpg'})]:
            self.assertFalse(context.condition('$EXP[FoundryMovieSubmenuBackdropVisible]'))
        context=native('Popular Today');context.flags['Player.HasVideo']=True
        self.assertFalse(context.condition('$EXP[FoundryMovieSubmenuBackdropVisible]'))
    def test_home_geometry_focus_and_all_unrelated_artwork_remain(self):
        with zipfile.ZipFile(ROOT/'skin.foundry/skin.foundry-1.4.0.zip') as bundle:
            before=E.fromstring(bundle.read('skin.foundry/xml/Home.xml'));after=E.parse(SKIN/'xml/Home.xml').getroot()
            for parent in after.iter():
                for child in list(parent):
                    if child.tag=='include' and child.get('content')=='WidgetListPoster' and any((p.get('value') or '').startswith('plugin://plugin.games.foundry/') for p in child.findall('param')):parent.remove(child)
            after=restore_home_feature_additions(after);before=restore_home_feature_additions(before)
            for node in after.iter('texture'):
                if node.get('fallback')=='special://skin/media/foundry-widget-base.png':node.set('fallback','special://skin/media/foundry-widget-base.svg')
            self.assertEqual(normalized(before.find('controls')),normalized(after.find('controls')))
            for name in bundle.namelist():
                relative=name.removeprefix('skin.foundry/')
                if name.startswith('skin.foundry/media/') or name.startswith('skin.foundry/resources/'):
                    if relative not in {'media/foundry-home-backdrop.png','resources/foundry-fanart.png','media/streampilot/catalog-base.png'} and not relative.startswith('media/foundry-widget-wallpapers/'):
                        self.assertEqual((SKIN/relative).read_bytes(),bundle.read(name),relative)
    def test_conditions_use_raw_info_labels_and_registered_expression(self):
        root=E.parse(SKIN/'xml/Includes_FoundryMovieSubmenus.xml')
        for node in root.iter():
            for condition in [node.get('condition',''),node.text if node.tag in ['expression','visible'] else '']:
                self.assertNotIn('$VAR[',condition or '');self.assertNotIn('$INFO[',condition or '')
        includes=E.parse(SKIN/'xml/Includes.xml')
        self.assertEqual(len(includes.findall("include[@file='Includes_FoundryMovieSubmenus.xml']")),1)
        self.assertEqual(E.parse(SKIN/'addon.xml').getroot().get('version'),'1.5.3')
        self.assertEqual(E.parse(SKIN/'addon.xml').find("requires/import[@addon='script.foundry.helper']").get('version'),'1.3.4')

if __name__=='__main__':unittest.main()
