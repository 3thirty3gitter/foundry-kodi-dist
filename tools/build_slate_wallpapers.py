"""Deterministic Slate-only wallpaper artwork. No original Foundry assets changed."""
from pathlib import Path
import io,json,hashlib,subprocess,tempfile
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]; SKIN=ROOT/'src/skin.foundry.slate'; MEDIA=SKIN/'media'
BASE=Image.open(MEDIA/'slate-background.png').convert('RGB')
ICONS={
'film':'<rect x="20" y="10" width="60" height="80" rx="5"/><path d="M32 10v80M68 10v80M20 28h12m-12 22h12m-12 22h12M68 28h12M68 50h12M68 72h12M32 37h36M32 64h36"/>',
'screen':'<rect x="10" y="20" width="80" height="54" rx="4"/><path d="M50 74v14M32 88h36"/>',
'music':'<path d="M40 72V25l40-10v47M40 40l40-10"/><ellipse cx="28" cy="77" rx="12" ry="8"/><ellipse cx="68" cy="67" rx="12" ry="8"/>',
'broadcast':'<circle cx="50" cy="45" r="5"/><path d="M50 50v35M35 28a24 24 0 0 0 0 34M65 28a24 24 0 0 1 0 34M24 16a41 41 0 0 0 0 58M76 16a41 41 0 0 1 0 58"/>',
'grid':'<rect x="14" y="14" width="28" height="28" rx="4"/><rect x="58" y="14" width="28" height="28" rx="4"/><rect x="14" y="58" width="28" height="28" rx="4"/><rect x="58" y="58" width="28" height="28" rx="4"/>',
'star':'<path d="m50 10 12 27 30 3-23 20 7 30-26-16-26 16 7-30L8 40l30-3Z"/>',
'play':'<circle cx="50" cy="50" r="38"/><path d="m42 30 26 20-26 20Z"/>',
'heart':'<path d="M50 86 16 53C-8 22 33 1 50 29 67 1 108 22 84 53Z"/>',
'clock':'<circle cx="50" cy="50" r="38"/><path d="M50 25v27l18 12"/>',
'calendar':'<rect x="14" y="20" width="72" height="66" rx="5"/><path d="M14 38h72M32 12v17M68 12v17M30 54h12m16 0h12M30 70h12m16 0h12"/>',
'globe':'<circle cx="50" cy="50" r="38"/><ellipse cx="50" cy="50" rx="17" ry="38"/><path d="M12 50h76M20 28h60M20 72h60"/>',
'check':'<circle cx="50" cy="50" r="38"/><path d="m29 50 15 16 28-34"/>',
'arrow':'<path d="M17 74 44 47l17 13 25-36M65 24h21v21"/>',
'back':'<path d="M85 50H15m25-25L15 50l25 25"/>',
'search':'<circle cx="43" cy="43" r="29"/><path d="m64 64 24 24"/>',
'power':'<path d="M50 10v42M28 22a36 36 0 1 0 44 0"/>',
'home':'<path d="m10 45 40-32 40 32M22 36v50h56V36M42 86V59h16v27"/>',
'picture':'<rect x="10" y="17" width="80" height="66" rx="5"/><circle cx="68" cy="35" r="7"/><path d="m10 73 26-28 20 20 12-11 22 24"/>',
'weather':'<circle cx="33" cy="33" r="16"/><path d="M33 5v7M6 33h7M12 12l6 6M55 12l-6 6M20 76h57c25-2 20-35 1-34-7-31-51-25-52 4-24-3-27 30-6 30Z"/>',
'games':'<path d="M30 30h40c15 0 21 45 12 49-8 3-16-13-21-15H39c-5 2-13 18-21 15-9-4-3-49 12-49ZM25 47h18M34 38v18M65 43h1M76 54h1"/>',
'settings':'<circle cx="50" cy="50" r="15"/><path d="m42 10 16 0 3 13 11 6 13-4 8 14-10 9v12l10 9-8 14-13-4-11 6-3 13H42l-3-13-11-6-13 4-8-14 10-9V48L7 39l8-14 13 4 11-6Z"/>',
}
HOME={'home':('Home','home'),'movies':('Movies','film'),'tvshows':('TV Shows','screen'),'music':('Music','music'),'musicvideos':('Music Videos','music'),'livetv':('Live TV','broadcast'),'radio':('Radio','broadcast'),'games':('Games','games'),'addons':('Add-ons','grid'),'pictures':('Pictures','picture'),'video':('Videos','play'),'favorites':('Favorites','heart'),'weather':('Weather','weather'),'settings':('Settings','settings'),'search':('Search','search'),'shutdown':('Power','power')}
CATEGORY={}
for p in sorted((MEDIA/'foundry-movie-submenus').glob('*.png')):
 key=p.stem; title=key.replace('-',' ').title().replace('Top 10 Box Office','Top 10 Box Office').replace('Because You Watched','Because You Watched…')
 icon='film'
 for tokens,choice in [('trending popular blockbusters','arrow'),('premieres latest-releases up-coming years decades','calendar'),('most-favorited','heart'),('most-watched watched','check'),('recently-watched in-progress','clock'),('top-10-box-office oscar-winners','star'),('genres providers','grid'),('languages','globe'),('certifications','check'),('because-you-watched','play')]:
  if key in tokens.split(): icon=choice
 CATEGORY[key]=(title,icon)

def icon_image(name,size):
 svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 100 100"><g fill="none" stroke="#d7d9da" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</g></svg>'
 with tempfile.TemporaryDirectory() as d:
  a=Path(d)/'icon.svg';b=Path(d)/'icon.png';a.write_text(svg)
  subprocess.run(['inkscape',str(a),'--export-filename='+str(b)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  return Image.open(b).convert('RGBA').copy()
CACHE={}; manifest=[]
def render(rel,title,icon,widget=False):
 im=BASE.copy().convert('RGBA');size=190 if widget else 310
 if (icon,size) not in CACHE: CACHE[icon,size]=icon_image(icon,size)
 motif=CACHE[icon,size].copy();motif.putalpha(motif.getchannel('A').point(lambda a:round(a*.11)))
 x,y=(1645,85) if widget else (1535,155);im.alpha_composite(motif,(x,y))
 draw=ImageDraw.Draw(im);fs=48 if widget else 80
 while True:
  font=ImageFont.truetype(str(SKIN/'fonts/Inter-ExtraLight.ttf'),fs)
  if draw.textlength(title,font=font)<= (625 if widget else 850): break
  fs-=1
 draw.text((1835,310 if widget else 530),title,font=font,fill=(151,154,157,255),anchor='ra')
 out=MEDIA/rel;out.parent.mkdir(parents=True,exist_ok=True);im.convert('RGB').save(out,optimize=True)
 manifest.append({'path':rel,'title':title,'icon':icon,'widget':widget,'size':[1920,1080],'sha256':hashlib.sha256(out.read_bytes()).hexdigest()})
def main():
 for key,(title,icon) in HOME.items():
  render('slate-wallpapers/'+key+'.png',title,icon)
  render('foundry-widget-wallpapers/'+key+'.png',title,icon,True)
 for key,(title,icon) in CATEGORY.items(): render('foundry-movie-submenus/'+key+'.png',title,icon,True)
 for key in ['search','shutdown']:render('foundry-navigation/'+key+'.png',*HOME[key])
 render('foundry-navigation/movies-back.png','Movies','back',True)
 render('foundry-backdrops/foundry-loading-splash.png','Foundry Media Center','home')
 # Neutral surfaces never leak rich original art while changing pages.
 for rel in ['foundry-home-backdrop.png','foundry-widget-base.png','streampilot/catalog-base.png']:BASE.save(MEDIA/rel)
 (MEDIA/'slate-wallpapers/manifest.json').write_text(json.dumps({'base_sha256':hashlib.sha256((MEDIA/'slate-background.png').read_bytes()).hexdigest(),'artwork':manifest},indent=2)+'\n')
if __name__=='__main__':main()
