"""Foundry's native vector menu icons and stretch-safe setting row textures."""
from pathlib import Path
import json
import re
import argparse
import subprocess
import tempfile
import xml.etree.ElementTree as E
from PIL import Image, ImageDraw

SKIN = Path(__file__).resolve().parents[2] / 'skin.foundry-nimbus'
PATHS = {
 'settings':'M10 3h4l1 3 3 1 3 3v4l-3 1-1 3-3 3h-4l-1-3-3-1-3-3v-4l3-1 1-3z M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
 'skin':'M12 3 3 7l9 4 9-4z M3 12l9 4 9-4 M3 17l9 4 9-4',
 'folder':'M3 7h7l2 2h9v11H3z M3 7V4h7l2 3',
 'addons':'M9 2h6v7h7v6h-7v7H9v-7H2V9h7z M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M12 10v4 M10 12h4',
 'info':'M12 10v7 M12 6v1 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
 'player':'M4 4h16v16H4z M10 8l6 4-6 4z',
 'media':'M3 5h18v15H3z M3 9h18 M7 5v4 M12 5v4 M17 5v4 M10 12l5 3-5 3z',
 'tv':'M3 5h18v14H3z M8 22h8 M12 19v3 M10 8l6 4-6 4z',
 'network':'M3 8a15 15 0 0 1 18 0 M6 12a10 10 0 0 1 12 0 M9 16a5 5 0 0 1 6 0 M12 20h.01',
 'games':'M7 7h10l4 4v7h-4l-3-3h-4l-3 3H3v-7z M6 10v5 M4 12.5h4 M16 11h.01 M18 14h.01',
 'interface':'M3 4h18v16H3z M3 9h18 M9 9v11',
 'profiles':'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-3a8 6 0 0 1 16 0v3',
 'system':'M3 4h18v13H3z M8 21h8 M12 17v4',
 'power':'M12 2v9 M6 5a9 9 0 1 0 12 0',
 'reload':'M20 7v6h-6 M20 13a8 8 0 1 1-2-7',
 'clock':'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 6v6l4 3',
 'sleep':'M18 3a9 9 0 1 0 3 15A9 9 0 0 1 18 3',
 'debug':'M8 7h8v12H8z M10 3h4v4 M4 9h4 M4 14h4 M4 19h4 M16 9h4 M16 14h4 M16 19h4 M12 7v12',
 'search':'M16 10a6 6 0 1 1-12 0 6 6 0 0 1 12 0 M14.5 14.5 21 21',
 'add':'M12 4v16 M4 12h16',
 'remove':'M4 12h16',
 'edit':'m4 15 12-12 5 5L9 20H4z M13 6l5 5',
 'delete':'M3 6h18 M6 6l1 15h10l1-15 M9 6V3h6v3 M10 10v7 M14 10v7',
 'check':'m4 12 5 5L20 5',
 'back':'m14 4-8 8 8 8 M6 12h15',
 'next':'m10 4 8 8-8 8 M3 12h15',
 'sort':'M4 6h16 M4 12h11 M4 18h6 M18 12v9 M15 18l3 3 3-3',
 'subtitles':'M3 5h18v14H3z M6 11h4 M14 11h4 M6 15h7 M16 15h2',
 'audio':'M3 9h4l5-5v16l-5-5H3z M16 8a6 6 0 0 1 0 8 M19 5a10 10 0 0 1 0 14',
 'display':'M3 4h18v14H3z M8 22h8 M12 18v4 M7 8h10 M7 12h6',
 'lock':'M5 10h14v11H5z M8 10V6a4 4 0 0 1 8 0v4 M12 14v3',
 'language':'M3 4h12 M9 2v3 M5 5c1 6 5 9 9 10 M13 5c-1 6-5 9-10 10 M13 21l4-11 4 11 M15 17h4',
 'calendar':'M3 5h18v16H3z M3 10h18 M7 2v6 M17 2v6 M7 14h3 M14 14h3 M7 18h3',
 'remote':'M7 2h10v20H7z M9 6h6 M9 11h6 M12 8v6 M10 18h4',
 'keyboard':'M2 6h20v12H2z M5 9h.01 M9 9h.01 M13 9h.01 M17 9h.01 M5 12h.01 M9 12h.01 M13 12h.01 M17 12h.01 M7 15h10',
 'disc':'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M14 12a2 2 0 1 1-4 0 2 2 0 0 1 4 0 M6 10a6 6 0 0 1 4-4 M14 18a6 6 0 0 0 4-4',
 'weather':'M8 8a5 5 0 1 1 9 4 M6 20h12a4 4 0 0 0 0-8h-2a6 6 0 0 0-11 3 3 3 0 0 0 1 5',
 'music':'M9 18V5l11-2v13 M9 7l11-2 M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0 M20 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
 'pictures':'M3 3h18v18H3z M3 17l6-7 5 6 3-3 4 5 M17 7h.01',
 'library':'M3 4h4v17H3z M10 4h4v17h-4z M17 5l4-1 3 16-4 1z',
 'favorite':'m12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z',
 'download':'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5',
 'upload':'M12 15V3 M7 8l5-5 5 5 M4 16v5h16v-5',
 'home':'m2 11 10-9 10 9 M5 9v12h14V9 M10 21v-7h4v7',
 'help':'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M9 8a3 3 0 1 1 4 3c-1 1-1 2-1 3 M12 18h.01',
 'sliders':'M3 6h18 M3 12h18 M3 18h18 M7 3v6 M17 9v6 M10 15v6',
 'toggle':'M7 6h10a6 6 0 0 1 0 12H7A6 6 0 0 1 7 6 M10 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
 'list':'M8 5h13 M8 12h13 M8 19h13 M3 5h.01 M3 12h.01 M3 19h.01',
 'storage':'M3 4h18v6H3z M3 14h18v6H3z M17 7h.01 M17 17h.01',
 'share':'M8 12l9-7 M8 12l9 7 M8 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0 M22 4a3 3 0 1 1-6 0 3 3 0 0 1 6 0 M22 20a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
 'accessibility':'M14 4a2 2 0 1 1-4 0 2 2 0 0 1 4 0 M3 8l9 2 9-2 M12 10v5 M7 22l5-7 5 7',
 'fullscreen':'M3 9V3h6 M15 3h6v6 M21 15v6h-6 M9 21H3v-6',
}


def drawing(name, color=None):
    path = PATHS[name]
    # Small native symbols share the chrome face, dark bevel, blue edge and
    # white specular highlight of the approved wallpaper artwork.
    layers = [('3.7','#0575b8','0.24'),('2.9','#72dbff','0.70'),
              ('2.35','#091722','1'),('1.85','url(#chrome)','1'),
              ('0.34','#effaff','0.85')]
    return ''.join('<path d="%s" fill="none" stroke="%s" stroke-opacity="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round"/>' % (path,stroke,opacity,width) for width,stroke,opacity in layers)


DEFS = '<defs><linearGradient id="chrome" x1="0" y1="0" x2="0.8" y2="1"><stop stop-color="#f7fcff"/><stop offset=".22" stop-color="#94abc2"/><stop offset=".43" stop-color="#edf5ff"/><stop offset=".49" stop-color="#faffff"/><stop offset=".53" stop-color="#60758c"/><stop offset=".76" stop-color="#b8ccdf"/><stop offset="1" stop-color="#effaff"/></linearGradient></defs>'


def choose(text, kind='button'):
    text = text.lower()
    rules = [('debug','debug'),('shutdown|powerdown|quit|exit','power'),('reload|reset|restart|reboot','reload'),('sleep|suspend|hibernate','sleep'),('alarm|timer|time|clock','clock'),('subtitle|caption','subtitles'),('sound|audio|volume','audio'),('video|movie|trailer','media'),('tv|pvr|epg|guide','tv'),('music|song|album','music'),('picture|image|photo|fanart|artwork','pictures'),('profile|account|user','profiles'),('file|folder|path|source','folder'),('network|internet|service|web|proxy','network'),('addon|plug-in|plugin|scraper|omdb|tmdb','addons'),('game|controller','games'),('interface|layout|menu|widget','interface'),('skin|theme|colour|color','skin'),('display|screen|resolution|monitor','display'),('lock|password|security','lock'),('language|region|locale','language'),('keyboard|input','keyboard'),('remote|cec','remote'),('database|cache|storage|disc','storage'),('sort|order','sort'),('search|find','search'),('delete|remove|clear','delete'),('add|new|create','add'),('edit|rename|custom','edit'),('favorite|favourite','favorite'),('download|install|update','download'),('help|support','help'),('info|about|version|systeminfo','info'),('weather','weather'),('calibrat','sliders')]
    for pattern, icon in rules:
        if re.search(pattern, text): return icon
    return {'radiobutton':'toggle','spincontrolex':'list','sliderex':'sliders','edit':'edit','colorbutton':'skin'}.get(kind, 'settings')


def main():
    import cairosvg
    parser=argparse.ArgumentParser()
    parser.add_argument('--artwork',type=Path,help='Optional directory containing the seven approved transparent chrome icons')
    args=parser.parse_args()
    destination = SKIN / 'media/foundry-icons'
    (destination / 'rows').mkdir(parents=True, exist_ok=True)
    primary={'settings','power','folder','info','system','profiles','skin'}
    for name in PATHS:
        source=(args.artwork or destination)/(name+'.png')
        if name in primary and source.exists():
            with Image.open(source) as original:
                icon=original.convert('RGBA')
                icon.thumbnail((256,256),Image.Resampling.LANCZOS)
            icon.save(destination/(name+'.png'))
        else:
            svg='<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="-2 -2 28 28">'+DEFS+drawing(name)+'</svg>\n'
            cairosvg.svg2png(bytestring=svg.encode(),write_to=str(destination/(name+'.png')))
            with Image.open(destination/(name+'.png')) as rendered:icon=rendered.convert('RGBA')
        (destination/(name+'.svg')).unlink(missing_ok=True)
        for state in ('focus','normal'):
            row=Image.new('RGBA',(320,70))
            if state=='focus':ImageDraw.Draw(row).rounded_rectangle((0,0,319,69),radius=12,fill='white')
            small=icon.resize((44,44),Image.Resampling.LANCZOS)
            row.alpha_composite(small,(14,13))
            row.save(destination/'rows'/(name+'-'+state+'.png'))
            (destination/'rows'/(name+'-'+state+'.svg')).unlink(missing_ok=True)
    (destination / 'CATALOG.json').write_text(json.dumps({'style':'Foundry metallic chrome with blue illuminated bevels','icons':sorted(PATHS),'primary_artwork':sorted(primary),'texture_size':[256,256],'row_size':[320,70],'home_menu_icons':'unchanged'},indent=2)+'\n')
    print('Created %d icons and %d native setting-row textures' % (len(PATHS),len(PATHS)*2))


if __name__ == '__main__': main()
