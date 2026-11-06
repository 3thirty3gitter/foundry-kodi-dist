"""Build deterministic Kodi masks from StreamPilot VodPoster/PageButton geometry."""
from pathlib import Path
import copy,json,xml.etree.ElementTree as E
from PIL import Image,ImageDraw,ImageFilter,ImageChops,ImageOps
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--skin',type=Path,default=Path(__file__).resolve().parents[2]/'skin.foundry-nimbus')
S=parser.parse_args().skin
# Each source shadow is rasterized at its own elevation around the same 224x336
# rounded poster. The previous implementation rescaled a single shadow 3 times.
margin=96;size=(224+margin*2,336+margin*2)
alpha=Image.new('L',size)
for elevation in (68,28,10):
 for blur,offset,opacity in ((elevation*.5,0,.32),(elevation*.5,elevation*.5,.45)):
  layer=Image.new('L',size);ImageDraw.Draw(layer).rounded_rectangle((margin,margin+offset,margin+223,margin+335+offset),radius=24,fill=round(255*opacity))
  layer=layer.filter(ImageFilter.GaussianBlur(blur))
  alpha=ImageChops.screen(alpha,layer)
im=Image.new('RGBA',size,'white');im.putalpha(alpha);im.save(S/'media/streampilot/catalog-glow.png')
# Exact normalized quadratic path from PosterRowNextArrowShape. Rasterize at 4x.
w,h=208,152;t=h*.055;a=h*.29;b=h*.71;c=w*.56
points=[]
def line(x,y):points.append((x,y))
def quad(cx,cy,x,y):
 x0,y0=points[-1]
 for i in range(1,21):
  f=i/20;line((1-f)**2*x0+2*(1-f)*f*cx+f*f*x,(1-f)**2*y0+2*(1-f)*f*cy+f*f*y)
line(t,a);quad(0,a,0,a+t);line(0,b-t);quad(0,b,t,b);line(c,b);line(c,h-t);quad(c,h,c+t,h);line(w-t,h*.56);quad(w,h*.5,w-t,h*.44);line(c+t,0);quad(c,0,c,t);line(c,a)
scale=4
mask=Image.new('L',(w*scale,h*scale));ImageDraw.Draw(mask).polygon([(round(x*scale),round(y*scale)) for x,y in points],fill=255)
for focused in (False,True):
 stroke=(6 if focused else 4)*scale
 interior=mask.filter(ImageFilter.MinFilter(stroke*2+1));border=ImageChops.subtract(mask,interior)
 start=(34,37,43) if focused else (9,10,13)
 image=Image.new('RGBA',mask.size)
 px=image.load()
 for y in range(image.height):
  for x in range(image.width):
   f=(x/image.width+y/image.height)/2;px[x,y]=tuple(round(k*(1-f)) for k in start)+(255,)
 image.putalpha(mask)
 rim=Image.new('RGBA',mask.size,'white');rim.putalpha(border.point(lambda v:round(v*(.88 if focused else .48))))
 image=Image.alpha_composite(image,rim).resize((w,h),Image.Resampling.LANCZOS)
 for previous in (False,True):
  name='previous' if previous else 'next';im=ImageOps.mirror(image) if previous else image
  im.save(S/('media/streampilot/catalog-%s%s.png'%(name,'-focus' if focused else '')))
  glow=Image.new('L',(w+112,h+112));glow.paste(ImageOps.mirror(mask.resize((w,h),Image.Resampling.LANCZOS)) if previous else mask.resize((w,h),Image.Resampling.LANCZOS),(56,56))
  glow=glow.filter(ImageFilter.GaussianBlur(28 if focused else 7)).point(lambda v:round(v*(.7 if focused else .22)))
  im=Image.new('RGBA',glow.size,'white');im.putalpha(glow);im.save(S/('media/streampilot/catalog-%s-glow%s.png'%(name,'-focus' if focused else '')))
# Share the exact arrow path as native SVG too (older fallback consumers).
path='M %.3f %.3f Q 0 %.3f 0 %.3f L 0 %.3f Q 0 %.3f %.3f %.3f L %.3f %.3f L %.3f %.3f Q %.3f %d %.3f %d L %.3f %.3f Q %d %.3f %.3f %.3f L %.3f 0 Q %.3f 0 %.3f %.3f L %.3f %.3f Z'%(t,a,a,a+t,b-t,b,t,b,c,b,c,h-t,c,h,c+t,h,w-t,h*.56,w,h*.5,w-t,h*.44,c+t,c,c,t,c,a)
for name,transform in [('next',''),('previous','translate(208 0) scale(-1 1)')]:
 (S/('media/streampilot/catalog-'+name+'.svg')).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="208" height="152" viewBox="0 0 208 152"><path transform="'+transform+'" d="'+path+'" fill="#090a0d" stroke="#ffffff" stroke-opacity=".48" stroke-width="4"/></svg>\n')
