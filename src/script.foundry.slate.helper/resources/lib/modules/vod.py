"""Kodi-native catalog paging and cached artwork color for the VOD view."""
import re
import time
from datetime import datetime
from pathlib import Path
from PIL import Image
import xbmc
import xbmcgui
from .osd import _cached_paths, dominant_color
from .catalog_metadata import episode_heading


def catalog_details(info, home):
    def text(value):
        value = str(value or "").strip()
        return "" if value.lower() in {"n/a", "none", "null"} else value
    owner = tuple(home.getProperty("foundry.slate.omdb.owner_" + name) for name in ("label", "year", "type"))
    current = tuple(info(label) for label in ("ListItem.Label", "ListItem.Year", "ListItem.DBTYPE"))
    def fallback(field):
        path=home.getProperty('foundry.slate.omdb.owner_path')
        same_path=not path or path==(info('ListItem.FileNameAndPath') or info('ListItem.Path'))
        return text(home.getProperty("foundry.slate.omdb." + field)) if owner == current and owner[0] and same_path else ""
    genres = text(info("ListItem.Genre")) or fallback("genres")
    genres = " / ".join(re.split(r"\s*/\s*|\s*,\s*", genres)[:3]) if genres else ""
    studio = text(info("ListItem.Studio")) or fallback("studio")
    language = text(info("ListItem.Property(original_language)")) or text(info("ListItem.AudioLanguage")) or fallback("language")
    convert = getattr(xbmc, "convertLanguage", None)
    if language and callable(convert):
        language = convert(language.split(",")[0].strip(), getattr(xbmc, "ISO_639_1", 0)) or language
    language = language.upper() if len(language) <= 3 else language
    is_tv = info("ListItem.DBTYPE").lower() in {"tvshow", "season", "episode"}
    episode=episode_heading({'type':info('ListItem.DBTYPE').lower(),'season':info('ListItem.Season'),
                             'episode':info('ListItem.Episode'),'showtitle':info('ListItem.TVShowTitle'),
                             'title':info('ListItem.Title') or info('ListItem.Label')})
    kind_label={"season":"TV Season","episode":"TV Episode","tvshow":"TV Series"}.get(info("ListItem.DBTYPE").lower(),"Movie")
    details = "  \u2022  ".join(p for p in (episode,kind_label, genres, studio, language) if p)
    released = text(info("ListItem.Premiered")) or fallback("released")
    for pattern in ("%Y-%m-%d", "%d %b %Y", "%d/%m/%Y"):
        try:
            date = datetime.strptime(released, pattern)
            month = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")[date.month - 1]
            released = "%s %d, %d" % (month, date.day, date.year)
            break
        except (ValueError, TypeError):
            continue
    certification = text(info("ListItem.MPAA")) or fallback("certification")
    if certification.startswith(('CA ', 'US ')): certification = certification[3:]
    try: fresh = float(fallback('rotten_tomatoes').rstrip('%')) >= 60
    except ValueError: fresh = True
    return {"genres": genres, "details": details,
            "released_label": (("Aired " if is_tv else "Released ") + released) if released else "",
            "certification": certification,
            "rt_badge": 'streampilot/source-rating_rt_%s.png' % ('fresh' if fresh else 'rotten')}


CATALOG_CONTENT = "Container.Content(movies) | Container.Content(tvshows) | Container.Content(seasons) | Container.Content(episodes) | Container.Content(videos)"

def current_content():
    for content in ('movies','tvshows','seasons','episodes','videos','files'):
        if xbmc.getCondVisibility('Container.Content('+content+')'):return content
    return ''


def activate_catalog():
    monitor = xbmc.Monitor()
    home = xbmcgui.Window(10000)
    if home.getProperty("foundry.slate.catalog.opening"):
        return False
    if home.getProperty("foundry.slate.catalog.active"):
        home.clearProperty("foundry.slate.catalog.routing")
        return False
    home.setProperty("foundry.slate.catalog.opening", "true")
    # This is a routing/loading indicator, not a native-view hiding guard.
    # Keep the completed native page usable while the provider is consulted.
    home.setProperty("foundry.slate.catalog.routing", "true")
    try:
        for _ in range(300):
            if monitor.abortRequested() or not xbmc.getCondVisibility("Window.IsActive(videos)"):
                return False
            path = xbmc.getInfoLabel("Container.FolderPath")
            is_media = xbmc.getCondVisibility(CATALOG_CONTENT)
            source = None
            if xbmc.getCondVisibility('Container.IsUpdating'):
                if monitor.waitForAbort(.05):break
                continue
            if path and (is_media or xbmc.getCondVisibility("Container.Content(files) + !Container.IsUpdating")):
                # The onload route and service monitor share one probe per
                # settled native directory, including non-catalog directories.
                # Otherwise the monitor re-fetches slow action/menu sources.
                home.setProperty('foundry.slate.catalog.handled_path', path)
                from .catalog_source import DirectorySource
                from .movie_submenu import canonical_label
                source = DirectorySource(path,current_content(),movie_submenu_label=canonical_label(
                    xbmc.getInfoLabel('Container.PluginCategory'),xbmc.getInfoLabel('Container.FolderName')))
                try:
                    data = source.load()
                    is_media = data.get('catalog_eligible',False)
                    source.initial = data
                except RuntimeError:
                    return False
                if not is_media:
                    return False  # Source/group-link directories keep their file-browser presentation.
                # A slow provider may finish after Back, Home, playback or a
                # newer folder has taken ownership. Never open over that state.
                if (monitor.abortRequested() or
                        not xbmc.getCondVisibility('Window.IsActive(videos)') or
                        xbmc.getCondVisibility('Container.IsUpdating') or
                        path != xbmc.getInfoLabel('Container.FolderPath')):
                    return False
            if is_media:
                if path:
                    from .catalog_window import open_catalog
                    from .catalog_items import section_for
                    section = "TV Shows" if xbmc.getCondVisibility("Container.Content(tvshows) | Container.Content(seasons) | Container.Content(episodes)") else "Movies"
                    if source:section=section_for(data['items'],section if source.content in ('movies','tvshows','seasons','episodes') else 'Videos')
                    try:
                        return open_catalog(path, section, xbmc.getInfoLabel("Container.PluginCategory"), source=source)
                    except (RuntimeError, OSError):
                        pass
                if not xbmc.getCondVisibility("Control.IsVisible(57)"):
                    xbmc.executebuiltin("Container.SetViewMode(57)")
                return True
            if monitor.waitForAbort(.05):
                break
        return False
    finally:
        home.clearProperty("foundry.slate.catalog.opening")
        home.clearProperty("foundry.slate.catalog.routing")


class CatalogRoutingMonitor:
    """Catches delayed plug-in loads and subsequent folder updates, not just onload."""
    def __init__(self, clock=time.monotonic):
        self.clock, self.last_path, self.retry = clock, "", 0

    def process(self):
        home = xbmcgui.Window(10000)
        if home.getProperty("foundry.slate.catalog.active") or home.getProperty("foundry.slate.catalog.opening"):
            return
        if not xbmc.getCondVisibility("Window.IsActive(videos)"):
            home.clearProperty("foundry.slate.catalog.handled_path")
            self.last_path = ""
            return
        path = xbmc.getInfoLabel("Container.FolderPath")
        if not path or home.getProperty("foundry.slate.catalog.handled_path") == path:
            return
        if path != self.last_path:
            self.last_path, self.retry = path, self.clock() + .25
        if self.clock() < self.retry or xbmc.getCondVisibility("Container.IsUpdating"):
            return
        self.retry = self.clock() + 5
        if xbmc.getCondVisibility(CATALOG_CONTENT + " | Container.Content(files)"):
            home.setProperty("foundry.slate.catalog.handled_path", path)
            home.setProperty("foundry.slate.catalog.routing", "true")
            xbmc.executebuiltin("RunScript(script.foundry.slate.helper,mode=vod_catalog_activate)")


def page_target(current_item, total, direction, page_size=6):
    try:
        count, current = int(total), max(0, int(current_item) - 1)
    except (TypeError, ValueError):
        return None
    if count <= 0 or direction not in {"next", "previous"}:
        return None
    page = min(current, count - 1) // page_size
    target_page = page + (1 if direction == "next" else -1)
    return max(0, min((count - 1) // page_size, target_page)) * page_size


def page(direction):
    if not xbmc.getCondVisibility("Window.IsActive(videos) + Control.IsVisible(57)"):
        return False
    target = page_target(xbmc.getInfoLabel("Container(57).CurrentItem"), xbmc.getInfoLabel("Container(57).NumItems"), direction)
    if target is None:
        return False
    xbmc.executebuiltin("SetFocus(57,%d,absolute)" % target)
    return True


def prepare_artwork():
    """Use thumbnails already cached by Kodi; never fetch remote artwork here."""
    if not xbmc.getCondVisibility("[[Window.IsActive(videos) | Window.IsActive(favouritesbrowser)] + Control.IsVisible(57)] | [Window.IsActive(Home) + ControlGroup(2000).HasFocus]"):
        return
    info = xbmc.getInfoLabel
    artwork = info("ListItem.Art(fanart)") or info("ListItem.Art(poster)") or info("ListItem.Icon")
    home = xbmcgui.Window(10000)
    owner = tuple(info(label) for label in ("ListItem.Label", "ListItem.Year", "ListItem.DBTYPE"))
    owner_path=info('ListItem.FileNameAndPath') or info('ListItem.Path')
    details = catalog_details(info, home)
    if owner != tuple(info(label) for label in ("ListItem.Label", "ListItem.Year", "ListItem.DBTYPE")):
        return
    for name, value in details.items():
        home.setProperty("foundry.slate.vod." + name, value)
    for name, value in zip(("owner_label", "owner_year", "owner_type"), owner):
        home.setProperty("foundry.slate.vod." + name, value)
    home.setProperty('foundry.slate.vod.owner_path',owner_path)
    from .catalog_color import resolved
    from .catalog_presentation import studio_logo
    metadata_owner=tuple(home.getProperty('foundry.slate.metadata.owner_'+name) for name in ('label','year','type'))
    from .studio_art import ART_KEYS, artwork as studio_artwork, resolve as resolve_studio
    logo = studio_artwork({key:info('ListItem.Art('+key+')') for key in ART_KEYS})
    if not logo and metadata_owner==owner and owner[0] and home.getProperty('foundry.slate.metadata.owner_path')==owner_path:
        logo=home.getProperty('foundry.slate.metadata.studiologo')
    if not logo:
        logo=resolve_studio({'studio':info('ListItem.Studio')})
    if logo:
        home.setProperty('foundry.slate.vod.studio_logo', studio_logo(logo) or logo)
    else:
        home.clearProperty('foundry.slate.vod.studio_logo')
    effect = resolved(artwork) if artwork else None
    # The texture cache can become ready after focus moves to another item.
    if artwork != (info('ListItem.Art(fanart)') or info('ListItem.Art(poster)') or info('ListItem.Icon')):
        return
    home.setProperty('foundry.slate.vod.glow', effect[1] if effect else 'streampilot/glow-pending.svg')
    if effect:
        home.setProperty('foundry.slate.vod.accent',effect[0])
        home.setProperty('foundry.slate.vod.artwork',artwork)
        return
    if artwork == home.getProperty("foundry.slate.vod.artwork"):
        return
    color, found = (72, 168, 240), False
    for path in _cached_paths(artwork) if artwork else ():
        try:
            if not Path(path).is_file():
                continue
            with Image.open(path) as image:
                if image.width * image.height > 40_000_000:
                    continue
                color = dominant_color(image)
                found = True
                break
        except (OSError, ValueError, Image.DecompressionBombError):
            continue
    current = info("ListItem.Art(fanart)") or info("ListItem.Art(poster)") or info("ListItem.Icon")
    if current != artwork:
        return
    home.setProperty("foundry.slate.vod.accent", ("FF%02X%02X%02X" % color) if found else "00FFFFFF")
    if found:
        home.setProperty("foundry.slate.vod.artwork", artwork)
    else:
        home.clearProperty("foundry.slate.vod.artwork")


class CatalogArtworkMonitor:
    """Follow item changes within the rail, not only container focus events."""
    def __init__(self, clock=time.monotonic):
        self.clock, self.item, self.changed_at, self.retry = clock, None, 0, 0

    def process_current_item(self):
        if not xbmc.getCondVisibility("[[Window.IsActive(videos) | Window.IsActive(favouritesbrowser)] + Control.IsVisible(57)] | [Window.IsActive(Home) + ControlGroup(2000).HasFocus]"):
            self.item = None
            return
        item = tuple(xbmc.getInfoLabel(label) for label in ("ListItem.Art(fanart)", "ListItem.Art(poster)", "ListItem.Label", "ListItem.Genre", "ListItem.FileNameAndPath"))
        if item != self.item:
            self.item, self.changed_at, self.retry = item, self.clock(), 0
            home = xbmcgui.Window(10000)
            if (item[0] or item[1]) != home.getProperty("foundry.slate.vod.artwork"):
                from .catalog_color import peek
                cached=peek(item[0] or item[1])
                home.setProperty('foundry.slate.vod.glow',cached[1] if cached else 'streampilot/glow-pending.svg')
                home.setProperty('foundry.slate.vod.accent',cached[0] if cached else '00FFFFFF')
        if self.clock() - self.changed_at >= 0 and self.clock() >= self.retry:
            prepare_artwork()
            self.retry = self.clock() + .15
