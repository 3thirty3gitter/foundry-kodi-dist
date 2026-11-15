from native_qa_assertions import harden_qa_source
from pathlib import Path
import os,json,shutil,subprocess,time,urllib.request,xml.etree.ElementTree as E
import argparse,tempfile,hashlib,sys
from PIL import ImageGrab
parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();ROOT=args.root.resolve();base=Path(tempfile.mkdtemp(prefix='slate-navigation-'));out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);home=base/'kodi';shutil.copytree('/usr/share/kodi',home,ignore_dangling_symlinks=True)
# Evidence may be copied from an earlier published release. Never accept stale reports.
for stale in out.iterdir():
 if stale.is_file() and (stale.suffix == '.png' or stale.name in ('native-report.json',)):
  stale.unlink()
profile=home/'portable_data';userdata=profile/'userdata';userdata.mkdir(parents=True);addons=profile/'addons';addons.mkdir()
for source in [ROOT/'src/skin.foundry.slate',ROOT/'src/script.foundry.slate.helper',ROOT.parent/'skin.foundry-nimbus',ROOT.parent/'script.foundry.helper']+[ROOT/'src'/x for x in ('resource.images.foundry.wallpapers','resource.images.foundry.osd','resource.uisounds.foundry.pulse','resource.images.foundry.slate.icons','resource.images.foundry.media.puremarks')]:
 aid=E.parse(source/'addon.xml').getroot().get('id');shutil.copytree(source,addons/aid,ignore=shutil.ignore_patterns('.git'))
for helper in addons.glob('script.*helper'):
 t=E.parse(helper/'addon.xml');r=t.getroot()
 for n in list(r.findall("extension[@point='xbmc.service']")):r.remove(n)
 for n in list(r.find('requires')):
  if n.get('addon')!='xbmc.python':r.find('requires').remove(n)
 t.write(helper/'addon.xml') # Keep actual helper entry/router for skin-control QA
 # Isolate picker UI from first-run menu rebuild/repository bootstrap. These
 # unrelated Home callbacks can ReloadSkin while Keep skin? is still open.
 entry=helper/'resources/lib/default.py'
 original=entry.read_text()
 guard='import sys as _qa_sys\nfrom urllib.parse import parse_qsl as _qa_parse\n_qa_mode=dict(_qa_parse(_qa_sys.argv[1] if len(_qa_sys.argv)>1 else "")).get("mode", "")\nif _qa_mode not in ("choose_search_provider", "toggle_search_provider", "open_selected_video_provider", "open_search_window", "search_input"):\n raise SystemExit\n'
 entry.write_text(guard+original)

for p in (home/'addons').glob('*/addon.xml'):
 t=E.parse(p)
 for e in t.getroot().findall("extension[@point='xbmc.service']"):t.getroot().remove(e)
 t.write(p)
for aid in ('skin.foundry','skin.foundry.slate'):
 d=userdata/'addon_data'/aid;d.mkdir(parents=True);(d/'settings.xml').write_text('<settings><setting id="firsttimerun" type="bool">true</setting></settings>')
(userdata/'guisettings.xml').write_text('<settings version="2"><setting id="lookandfeel.skin">skin.estuary</setting><setting id="addons.updatemode">2</setting><setting id="services.webserver">true</setting><setting id="services.webserverport">18991</setting><setting id="services.webserverauthentication">false</setting><resolutions/><viewstates/><skinsettings/></settings>')
LEGACY_IDS=['plugin.video.fen', 'plugin.video.fenlight', 'plugin.video.umbrella', 'plugin.video.pov', 'plugin.video.seren']
LEGACY_ROUTES={'skin.foundry': {'SearchProviderMoviesVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=build_movie_list&action=tmdb_movies_search&query=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=build_movie_list&action=tmdb_movies_search&query=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.umbrella) + System.AddonIsEnabled(plugin.video.umbrella) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),2)', 'plugin://plugin.video.umbrella/?action=movieSearchterm&name=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=build_movie_list&action=tmdb_movies_search&query=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.seren) + System.AddonIsEnabled(plugin.video.seren) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),4)', 'plugin://plugin.video.seren/?action=moviesSearchResults&actionArgs=$INFO[Window(home).Property(nimbus.search.input.encoded)]')], 'SearchProviderTVShowsVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=build_tvshow_list&action=tmdb_tv_search&query=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=build_tvshow_list&action=tmdb_tv_search&query=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.umbrella) + System.AddonIsEnabled(plugin.video.umbrella) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),2)', 'plugin://plugin.video.umbrella/?action=tvSearchterm&name=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=build_tvshow_list&action=tmdb_tv_search&query=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.seren) + System.AddonIsEnabled(plugin.video.seren) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),4)', 'plugin://plugin.video.seren/?action=showsSearchResults&actionArgs=$INFO[Window(home).Property(nimbus.search.input.encoded)]')], 'SearchProviderAnimeVar': [('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=build_tvshow_list&action=tmdb_anime_search&query=$INFO[Window(home).Property(nimbus.search.input.encoded)]')], 'SearchProviderCollectionsVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=build_movie_list&action=tmdb_movies_search_sets&query=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=build_movie_list&action=tmdb_movies_search_collections&query=$INFO[Window(home).Property(nimbus.search.input.encoded)]')], 'SearchProviderPeopleVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=person_direct.search&query=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=person_direct.search&key_id=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=get_search_term&search_type=people&query=$INFO[Window(home).Property(nimbus.search.input.encoded)]')], 'SearchProviderActors/ActressesMoviesVar': [('System.HasAddon(plugin.video.umbrella) + System.AddonIsEnabled(plugin.video.umbrella) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),2)', 'plugin://plugin.video.umbrella/?action=actorSearchMovies&name=$INFO[Window(home).Property(nimbus.search.input.encoded)]')], 'SearchProviderActors/ActressesTVShowsVar': [('System.HasAddon(plugin.video.umbrella) + System.AddonIsEnabled(plugin.video.umbrella) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),2)', 'plugin://plugin.video.umbrella/?action=actorSearchTV&name=$INFO[Window(home).Property(nimbus.search.input.encoded)]')], 'SearchProviderKeywordMoviesVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=build_movie_list&action=imdb_keywords_list_contents&list_id=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=build_movie_list&action=tmdb_movie_keyword_results_direct&key_id=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=imdb_build_keyword_results&media_type=movie&query=$INFO[Window(home).Property(nimbus.search.input.encoded)]')], 'SearchProviderKeywordTVShowsVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=build_tvshow_list&action=imdb_keywords_list_contents&list_id=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=build_tvshow_list&action=tmdb_tv_keyword_results_direct&key_id=$INFO[Window(home).Property(nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=imdb_build_keyword_results&media_type=tvshow&query=$INFO[Window(home).Property(nimbus.search.input.encoded)]')], 'SearchProviderTRAKTListsVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(nimbus.search.input.trakt.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=trakt.list.search_trakt_lists&query=$INFO[Window(home).Property(nimbus.search.input.trakt.encoded)]'), ('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(nimbus.search.input.trakt.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=trakt.list.search_trakt_lists&query=$INFO[Window(home).Property(nimbus.search.input.trakt.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(nimbus.search.input.trakt.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=build_trakt_list.search_trakt_lists&search_title=$INFO[Window(home).Property(nimbus.search.input.trakt.encoded)]')], 'SearchProviderTRAKTListsMoviesVar': [('System.HasAddon(plugin.video.umbrella) + System.AddonIsEnabled(plugin.video.umbrella) + !String.IsEmpty(Window(home).Property(nimbus.search.input.trakt.encoded)) + String.IsEqual(Skin.String(current_search_provider),2)', 'plugin://plugin.video.umbrella/?action=trakt_search_lists&media_type=movies&name=$INFO[Window(home).Property(nimbus.search.input.trakt.encoded)]')], 'SearchProviderTRAKTListsTVShowsVar': [('System.HasAddon(plugin.video.umbrella) + System.AddonIsEnabled(plugin.video.umbrella) + !String.IsEmpty(Window(home).Property(nimbus.search.input.trakt.encoded)) + String.IsEqual(Skin.String(current_search_provider),2)', 'plugin://plugin.video.umbrella/?action=trakt_search_lists&media_type=tvshows&name=$INFO[Window(home).Property(nimbus.search.input.trakt.encoded)]')]}, 'skin.foundry.slate': {'SearchProviderMoviesVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=build_movie_list&action=tmdb_movies_search&query=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=build_movie_list&action=tmdb_movies_search&query=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.umbrella) + System.AddonIsEnabled(plugin.video.umbrella) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),2)', 'plugin://plugin.video.umbrella/?action=movieSearchterm&name=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=build_movie_list&action=tmdb_movies_search&query=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.seren) + System.AddonIsEnabled(plugin.video.seren) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),4)', 'plugin://plugin.video.seren/?action=moviesSearchResults&actionArgs=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]')], 'SearchProviderTVShowsVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=build_tvshow_list&action=tmdb_tv_search&query=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=build_tvshow_list&action=tmdb_tv_search&query=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.umbrella) + System.AddonIsEnabled(plugin.video.umbrella) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),2)', 'plugin://plugin.video.umbrella/?action=tvSearchterm&name=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=build_tvshow_list&action=tmdb_tv_search&query=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.seren) + System.AddonIsEnabled(plugin.video.seren) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),4)', 'plugin://plugin.video.seren/?action=showsSearchResults&actionArgs=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]')], 'SearchProviderAnimeVar': [('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=build_tvshow_list&action=tmdb_anime_search&query=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]')], 'SearchProviderCollectionsVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=build_movie_list&action=tmdb_movies_search_sets&query=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=build_movie_list&action=tmdb_movies_search_collections&query=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]')], 'SearchProviderPeopleVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=person_direct.search&query=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=person_direct.search&key_id=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=get_search_term&search_type=people&query=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]')], 'SearchProviderActors/ActressesMoviesVar': [('System.HasAddon(plugin.video.umbrella) + System.AddonIsEnabled(plugin.video.umbrella) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),2)', 'plugin://plugin.video.umbrella/?action=actorSearchMovies&name=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]')], 'SearchProviderActors/ActressesTVShowsVar': [('System.HasAddon(plugin.video.umbrella) + System.AddonIsEnabled(plugin.video.umbrella) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),2)', 'plugin://plugin.video.umbrella/?action=actorSearchTV&name=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]')], 'SearchProviderKeywordMoviesVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=build_movie_list&action=imdb_keywords_list_contents&list_id=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=build_movie_list&action=tmdb_movie_keyword_results_direct&key_id=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=imdb_build_keyword_results&media_type=movie&query=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]')], 'SearchProviderKeywordTVShowsVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=build_tvshow_list&action=imdb_keywords_list_contents&list_id=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=build_tvshow_list&action=tmdb_tv_keyword_results_direct&key_id=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=imdb_build_keyword_results&media_type=tvshow&query=$INFO[Window(home).Property(slate.nimbus.search.input.encoded)]')], 'SearchProviderTRAKTListsVar': [('System.HasAddon(plugin.video.fen) + System.AddonIsEnabled(plugin.video.fen) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.trakt.encoded)) + String.IsEqual(Skin.String(current_search_provider),0)', 'plugin://plugin.video.fen/?mode=trakt.list.search_trakt_lists&query=$INFO[Window(home).Property(slate.nimbus.search.input.trakt.encoded)]'), ('System.HasAddon(plugin.video.fenlight) + System.AddonIsEnabled(plugin.video.fenlight) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.trakt.encoded)) + String.IsEqual(Skin.String(current_search_provider),1)', 'plugin://plugin.video.fenlight/?mode=trakt.list.search_trakt_lists&query=$INFO[Window(home).Property(slate.nimbus.search.input.trakt.encoded)]'), ('System.HasAddon(plugin.video.pov) + System.AddonIsEnabled(plugin.video.pov) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.trakt.encoded)) + String.IsEqual(Skin.String(current_search_provider),3)', 'plugin://plugin.video.pov/?mode=build_trakt_list.search_trakt_lists&search_title=$INFO[Window(home).Property(slate.nimbus.search.input.trakt.encoded)]')], 'SearchProviderTRAKTListsMoviesVar': [('System.HasAddon(plugin.video.umbrella) + System.AddonIsEnabled(plugin.video.umbrella) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.trakt.encoded)) + String.IsEqual(Skin.String(current_search_provider),2)', 'plugin://plugin.video.umbrella/?action=trakt_search_lists&media_type=movies&name=$INFO[Window(home).Property(slate.nimbus.search.input.trakt.encoded)]')], 'SearchProviderTRAKTListsTVShowsVar': [('System.HasAddon(plugin.video.umbrella) + System.AddonIsEnabled(plugin.video.umbrella) + !String.IsEmpty(Window(home).Property(slate.nimbus.search.input.trakt.encoded)) + String.IsEqual(Skin.String(current_search_provider),2)', 'plugin://plugin.video.umbrella/?action=trakt_search_lists&media_type=tvshows&name=$INFO[Window(home).Property(slate.nimbus.search.input.trakt.encoded)]')]}}
# Only disposable portable profile receives fixtures. No user addons modified.
for aid,name,content in [('plugin.qa.video','QA Video','video'),('plugin.qa.disabled','QA Disabled','video'),('plugin.qa.audio','QA Audio','audio')]+[(aid,'QA Legacy '+str(i),'video') for i,aid in enumerate(LEGACY_IDS)]:
 d=addons/aid;d.mkdir()
 (d/'addon.xml').write_text('<addon id="'+aid+'" version="1.0.0" name="'+name+'" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.pluginsource" library="default.py"><provides>'+content+'</provides></extension></addon>')
 (d/'default.py').write_text('import sys,xbmcplugin\nfrom pathlib import Path\nPath('+repr(str(out/'root-opened.json'))+').write_text("true")\nxbmcplugin.endOfDirectory(int(sys.argv[1]))\n')
qa=addons/'script.foundry.searchqa';qa.mkdir()
(qa/'addon.xml').write_text('<addon id="script.foundry.searchqa" version="1.0.0" name="Search QA" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/></addon>')
driver=addons/'script.foundry.searchdriver';driver.mkdir()
(driver/'addon.xml').write_text('<addon id="script.foundry.searchdriver" version="1.0.0" name="Search driver QA" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/></addon>')
env=dict(os.environ,HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'home/.config'),XDG_CACHE_HOME=str(base/'home/.cache'),DISPLAY=':98',KODI_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='1',AE_SINK='NULL');(base/'home').mkdir()
log=(out/'native-console.log').open('w');x=subprocess.Popen(['Xvfb',':98','-screen','0','1920x1080x24','-ac','-nolisten','tcp'],stdout=log,stderr=log);time.sleep(1)
def launch():return subprocess.Popen(['kodi','-p','-fs','--windowing=x11','--debug'],env=env,stdout=log,stderr=log)
k=launch()
def rpc(method,params=None):
 data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}}).encode();r=json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18991/jsonrpc',data=data,headers={'Content-Type':'application/json'}),timeout=5))
 if 'error' in r:raise RuntimeError((method,params,r['error']))
 return r['result']
def wait(fn,t=45):
 end=time.monotonic()+t
 while time.monotonic()<end:
  try:
   if fn():return
  except Exception:pass
  time.sleep(.25)
 raise AssertionError('timeout')
def cond(c):return rpc('XBMC.GetInfoBooleans',{'booleans':[c]})[c]
def act(a):rpc('Input.ExecuteAction',{'action':a});time.sleep(.3)
def drive(body):
 # Wait for both a result receipt and the same native interpreter teardown.
 import re
 receipt=out/('driver-'+str(time.time_ns())+'.json')
 logpath=profile/'temp/kodi.log'
 offset=logpath.stat().st_size if logpath.exists() else 0
 source='import xbmc,xbmcgui,json,traceback\nfrom pathlib import Path\nresult={"ok":False}\ntry:\n'
 source+='\n'.join(' '+line for line in body.splitlines())
 source+='\n result["ok"]=True\nexcept Exception:\n result["error"]=traceback.format_exc()\nfinally:\n Path('+repr(str(receipt))+').write_text(json.dumps(result))\n'
 (driver/'default.py').write_text(source)
 rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.searchdriver','wait':False})
 wait(receipt.exists)
 def stopped():
  with logpath.open('rb') as f:f.seek(offset);tail=f.read().decode('utf-8',errors='replace')
  match=re.search(r'T:(\d+)\s+.*CPythonInvoker.*script\.foundry\.searchdriver/default\.py.*script successfully run',tail)
  return bool(match and re.search(r'T:'+match.group(1)+r'\s+.*Python interpreter stopped',tail[match.end():]))
 wait(stopped)
 result=json.loads(receipt.read_text())
 assert result['ok'], result.get('error')
def focus_yes(expected):
 state=out/'dialog-focus.json'
 def observe():
  drive('w=xbmcgui.Window(xbmcgui.getCurrentWindowDialogId())\nPath('+repr(str(state))+').write_text(json.dumps({"id":w.getFocusId(),"yes":xbmc.getInfoLabel("Control.GetLabel(11)")}))')
  return json.loads(state.read_text())
 current=observe()
 assert current['yes']==expected, current
 for _ in range(2):
  if current['id']==11:return
  act('left');current=observe()
 assert current['id']==11, current
def snap(n):
 dest=out/(n+'.png')
 if dest.exists():dest.unlink()
 drive('xbmc.executebuiltin('+repr('TakeScreenshot('+str(dest)+')')+',True)\nxbmc.sleep(700)')
 wait(dest.exists)
def accept_disclosure():
 wait(lambda:cond('Window.IsVisible(yesnodialog)'))
 # Assert the actual yes control, rather than assuming a left press means Yes.
 focus_yes('Use add-on')
 snap(skin+'-disclosure-accept')
 act('select')
 wait(lambda:not cond('Window.IsVisible(yesnodialog)'))
def selected():
 return rpc('XBMC.GetInfoLabels',{'labels':['Skin.String(current_search_provider)']})['Skin.String(current_search_provider)']
report={'passed':False,'scope':'Disposable native Kodi real picker and video metadata; unrelated Home startup helper callbacks suppressed in fixture entry only; actual search router/module and SkinSettings unchanged; unknown providers are open-only, no integrated search claim.','skins':{}}
try:
 wait(lambda:rpc('JSONRPC.Ping')=='pong')
 # Startup asks about every new disposable addon; require a quiet interval.
 quiet=None;deadline=time.monotonic()+90
 while time.monotonic()<deadline:
  if cond('System.HasActiveModalDialog'):
   act('back');quiet=None
  elif quiet is None:quiet=time.monotonic()
  elif time.monotonic()-quiet>2:break
  time.sleep(.2)
 else:raise AssertionError('Startup dialogs did not settle')
 for aid in ['resource.images.foundry.wallpapers','resource.images.foundry.osd','resource.uisounds.foundry.pulse','resource.images.foundry.slate.icons','resource.images.foundry.media.puremarks','script.foundry.helper','script.foundry.slate.helper','skin.foundry','skin.foundry.slate','script.foundry.searchqa','script.foundry.searchdriver','plugin.qa.video','plugin.qa.disabled','plugin.qa.audio']+LEGACY_IDS:
  rpc('Addons.SetAddonEnabled',{'addonid':aid,'enabled':True})
 rpc('Addons.SetAddonEnabled',{'addonid':'plugin.qa.disabled','enabled':False})
 for skin,helper in [('skin.foundry','script.foundry.helper'),('skin.foundry.slate','script.foundry.slate.helper')]:
  # Drain any addon-enabled prompts before issuing the skin switch.
  for _ in range(30):
   if not cond('System.HasActiveModalDialog'):
    time.sleep(.7)
    if not cond('System.HasActiveModalDialog'):break
   act('back')
  assert not cond('System.HasActiveModalDialog'), 'Outstanding pre-switch modal'
  assert rpc('Settings.SetSettingValue',{'setting':'lookandfeel.skin','value':skin})
  wait(lambda:cond('Window.IsVisible(yesnodialog)'))
  snap(skin+'-switch-confirmation')
  focus_yes('Yes')
  act('select');wait(lambda:not cond('System.HasActiveModalDialog'));time.sleep(2)
  actual=out/(skin+'-active-skin.json')
  drive('Path('+repr(str(actual))+').write_text(json.dumps({"active":xbmc.getSkinDir()}))')
  observed=json.loads(actual.read_text())['active']
  assert observed==skin, ('Configured setting is not actual rendered skin',skin,observed)
  assert rpc('Settings.GetSettingValue',{'setting':'lookandfeel.skin'})['value']==skin
  entry=addons/helper/'resources/lib';marker=out/(skin+'-probe.json')
  probe_offset=[None]
  def wait_probe_completed():
   import re
   wait(marker.exists)
   def stopped():
    with (profile/'temp/kodi.log').open('rb') as f:f.seek(probe_offset[0]);tail=f.read().decode('utf-8',errors='replace')
    match=re.search(r'T:(\d+)\s+.*CPythonInvoker.*script\.foundry\.searchqa/default\.py.*script successfully run',tail)
    return bool(match and re.search(r'T:'+match.group(1)+r'\s+.*Python interpreter stopped',tail[match.end():]))
   wait(stopped)
  def run(body):
   if probe_offset[0] is not None:wait_probe_completed()
   probe_offset[0]=(profile/'temp/kodi.log').stat().st_size
   if marker.exists():marker.unlink()
   (qa/'default.py').write_text(harden_qa_source('import sys,json,xbmc\nfrom pathlib import Path\nsys.path.insert(0,'+repr(str(entry))+')\nfrom modules import search_provider as p\nassert xbmc.getSkinDir()=='+repr(skin)+', (\"Wrong actual skin\",xbmc.getSkinDir())\n'+body+'\nxbmc.sleep(350)\nPath('+repr(str(marker))+').write_text(json.dumps({"selection":xbmc.getInfoLabel("Skin.String(current_search_provider)")}))\n'))
   rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.searchqa','wait':False})
  run('rows=p.installed_video_providers()\nassert "plugin.qa.audio" not in [r["id"] for r in rows]\nassert any(r["id"]=="plugin.qa.disabled" and not r["enabled"] for r in rows)\nPath('+repr(str(out/(skin+'-inventory.json')))+').write_text(json.dumps(rows))')
  wait_probe_completed();rows=json.loads((out/(skin+'-inventory.json')).read_text());report['skins'][skin]={'inventory':rows,'active_skin_verified':observed}
  # Navigate shipped SkinSettings with real remote actions and click its control.
  # This is separate from direct picker cases, preserving the actual entry point.
  run('xbmc.executebuiltin("Skin.Reset(current_search_provider)",True)\nxbmc.executebuiltin("ActivateWindow(skinsettings)",False)\nxbmc.sleep(1000)')
  wait_probe_completed()
  wait(lambda:cond('Control.HasFocus(9000)'))
  snap(skin+'-settings-start')
  for _ in range(20):
   if cond('Container(9000).HasFocus(3)'):break
   act('down')
  assert cond('Container(9000).HasFocus(3)'), 'Search options category unreachable'
  # Container selection changes before the conditional group has finished
  # layout/animation. Wait for real visible/enabled target, not a fixed 300ms.
  wait(lambda:cond('Control.IsVisible(64700)') and cond('Control.IsEnabled(64700)'))
  time.sleep(.7)
  snap(skin+'-settings-category-ready')
  act('right')
  try:wait(lambda:cond('Control.HasFocus(64700)'),t=5)
  except Exception:
   snap(skin+'-settings-navigation-failure')
   drive('Path('+repr(str(out/(skin+'-focus-failure.json')))+').write_text(json.dumps({"window":xbmcgui.getCurrentWindowId(),"modal":xbmcgui.getCurrentWindowDialogId(),"focus":xbmcgui.Window(xbmcgui.getCurrentWindowId()).getFocusId(),"label":xbmc.getInfoLabel("System.CurrentControl"),"category":xbmc.getInfoLabel("Container(9000).ListItem.Label")}))')
   raise AssertionError('Set Search Provider button unreachable after group readiness; inspect focus evidence')
  snap(skin+'-settings-search-control')
  act('select');wait(lambda:cond('Window.IsVisible(selectdialog)'));snap(skin+'-settings-picker')
  act('back');wait(lambda:not cond('System.HasActiveModalDialog'))
  assert cond('Control.HasFocus(64700)'), 'Picker cancel lost settings control focus'
  report['skins'][skin]['actual_settings_control_picker_cancel']=True
  def choose(aid=None):
   run('xbmc.executebuiltin("Skin.Reset(current_search_provider)",True)\nxbmc.sleep(250)\np.choose_search_provider()')
   wait(lambda:cond('Window.IsVisible(selectdialog)'));snap(skin+'-picker')
   if aid is None:act('back');return
   idx=next(i for i,r in enumerate(rows) if r['id']==aid)
   act('firstpage')
   for _ in range(idx):act('down')
   act('select')
  choose();wait_probe_completed();assert json.loads(marker.read_text())['selection']==''
  choose('plugin.qa.disabled');wait(lambda:cond('Window.IsVisible(okdialog)'));snap(skin+'-disabled');act('select');wait_probe_completed();assert json.loads(marker.read_text())['selection']==''
  choose('plugin.qa.video');wait(lambda:cond('Window.IsVisible(yesnodialog)'));snap(skin+'-disclosure');act('back');wait_probe_completed();assert json.loads(marker.read_text())['selection']==''
  choose('plugin.qa.video');accept_disclosure();wait_probe_completed();wait(lambda:selected()=='plugin.qa.video')
  # Legacy numeric selections and existing XML routes remain unchanged.
  report['skins'][skin]['legacy_selections']=[]
  for i,aid in enumerate(LEGACY_IDS):
   choose(aid);wait(marker.exists)
   assert json.loads(marker.read_text())['selection']==str(i)
   report['skins'][skin]['legacy_selections'].append({'addon':aid,'slot':str(i)})
  r=E.parse(addons/skin/'xml/Variables_Search.xml')
  routes={v.get('name'):[(n.get('condition'),n.text) for n in v.findall('value')] for v in r.getroot().findall('variable') if v.get('name','').startswith('SearchProvider')}
  assert routes==LEGACY_ROUTES[skin], 'Legacy search route contract changed'
  report['skins'][skin]['legacy_xml_routes_unchanged']=True
  # Restore open-only source for restart test, with the same explicit disclosure.
  choose('plugin.qa.video');accept_disclosure();wait_probe_completed();wait(lambda:selected()=='plugin.qa.video')
  # Native skin string is persisted on graceful shutdown, then reopened.
  rpc('Application.Quit');k.wait(timeout=30)
  settings=userdata/'addon_data'/skin/'settings.xml';t=E.parse(settings)
  assert any(n.get('id')=='current_search_provider' and n.text=='plugin.qa.video' for n in t.getroot().findall('setting'))
  shutil.copy2(settings,out/(skin+'-settings.xml'));probe_offset[0]=None;k=launch();wait(lambda:rpc('JSONRPC.Ping')=='pong');time.sleep(3)
  run('assert xbmc.getInfoLabel("Skin.String(current_search_provider)")=="plugin.qa.video"\np.use_external_video_provider()')
  wait_probe_completed();wait(lambda:(out/'root-opened.json').exists());snap(skin+'-addon-root');(out/'root-opened.json').unlink()
  report['skins'][skin]['passed']=True
 report['passed']=True
finally:
 for f in (profile/'temp').glob('kodi*.log'):
  shutil.copy2(f,out/f.name)
 (out/'native-report.json').write_text(json.dumps(report,indent=2))
 try:rpc('Application.Quit');k.wait(timeout=15)
 except Exception:k.terminate()
 x.terminate();log.close()
print(json.dumps(report,indent=2))
