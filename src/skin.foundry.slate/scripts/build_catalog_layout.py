from pathlib import Path
import xml.etree.ElementTree as E
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1]
M=R/'media/streampilot';M.mkdir(exist_ok=True)
for height in (54,62,76,84,96,100):
 size=(height*2,height);im=Image.new('RGBA',(size[0]*4,size[1]*4));ImageDraw.Draw(im).rounded_rectangle((0,0,im.width-1,im.height-1),radius=height*2,fill='white');im.resize(size,Image.Resampling.LANCZOS).save(M/('catalog-pill-%d.png'%height))
for name,size,radius in [('catalog-pill',(256,128),64),('catalog-cert',(160,80),12),('catalog-search-panel',(256,256),32)]:
 im=Image.new('RGBA',(size[0]*4,size[1]*4));ImageDraw.Draw(im).rounded_rectangle((0,0,im.width-1,im.height-1),radius=radius*4,fill='white');im.resize(size,Image.Resampling.LANCZOS).save(M/(name+'.png'))
# PNG equivalents are required by Kodi21; original vector geometry is retained.
for previous in (False,True):
 im=Image.new('RGBA',(208*4,152*4));d=ImageDraw.Draw(im);points=[(5,46),(125,46),(125,5),(203,76),(125,147),(125,106),(5,106)]
 if previous:points=[(208-x,y) for x,y in points]
 points=[(x*4,y*4) for x,y in points];d.polygon(points,fill='#050509');d.line(points+[points[0]],fill='#b8c4ff',width=12,joint='curve');im.resize((208,152),Image.Resampling.LANCZOS).save(M/('catalog-previous.png' if previous else 'catalog-next.png'))
im=Image.new('RGBA',(256,256));d=ImageDraw.Draw(im);d.ellipse((34,28,184,178),outline='white',width=24);d.line((165,159,235,229),fill='white',width=25);im.resize((64,64),Image.Resampling.LANCZOS).save(M/'catalog-search.png')
Image.new('RGBA',(1,1),'white').save(M/'catalog-white.png')
for name,colors in [('catalog-tmdb',((1,180,228),(144,206,161))),('catalog-imdb',((245,197,24),(230,169,0)))]:
 im=Image.new('RGBA',(160,64));p=im.load()
 for y in range(64):
  for x in range(160):p[x,y]=tuple(round(a+(b-a)*x/159) for a,b in zip(*colors))+(255,)
 mask=Image.new('L',im.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,159,63),radius=9,fill=255);im.putalpha(mask);im.save(M/(name+'.png'))
w=E.Element('window');E.SubElement(w,'defaultcontrol',always='true').text='50';E.SubElement(w,'views').text='50';E.SubElement(w,'backgroundcolor').text='FF020710';controls=E.SubElement(w,'controls')
def node(parent,typ,x=0,y=0,width=0,height=0,id=None,visible=None):
 a={'type':typ}
 if id is not None:a['id']=str(id)
 n=E.SubElement(parent,'control',a)
 for tag,value in [('left',x),('top',y),('width',width),('height',height)]:E.SubElement(n,tag).text=str(value)
 if visible:E.SubElement(n,'visible').text=visible
 return n
def tag(n,key,value,**kwargs):E.SubElement(n,key,kwargs).text=str(value)
def prop(key):return '$INFO[Window.Property(catalog.'+key+')]'
def vis(key):return '!String.IsEmpty(Window.Property(catalog.'+key+'))'
def image(parent,x,y,width,height,texture,tint=None,visible=None,border=None,aspect=None):
 n=node(parent,'image',x,y,width,height,visible=visible);a={}
 if tint:a['colordiffuse']=tint
 if border:a['border']=str(border)
 tag(n,'texture',texture,**a)
 if aspect:tag(n,'aspectratio',aspect)
 return n
def label(parent,x,y,width,height,text,font='sp_catalog_meta',color='FFE5E8EF',visible=None,align=None):
 n=node(parent,'label',x,y,width,height,visible=visible);tag(n,'label',text);tag(n,'font',font);tag(n,'textcolor',color)
 if align:tag(n,'align',align)
 tag(n,'aligny','center');return n
def button(parent,id,x,y,width,height,text,up=None,down=None,left=None,right=None,visible=None):
 n=node(parent,'button',x,y,width,height,id,visible);tag(n,'label',text);tag(n,'font','sp_catalog_meta');tag(n,'textcolor','FFFFFFFF');tag(n,'focusedcolor','FFFFFFFF');tag(n,'align','center');tag(n,'aligny','center');tag(n,'texturefocus','streampilot/catalog-pill-%d.png'%height,border=str(height//2),colordiffuse='FF596A93');tag(n,'texturenofocus','streampilot/catalog-pill-%d.png'%height,border=str(height//2),colordiffuse='DD39435E')
 for k,v in [('onup',up),('ondown',down),('onleft',left),('onright',right)]:
  if v is not None:tag(n,k,v)
 return n
main=node(controls,'group',0,0,1920,1080,visible='String.IsEmpty(Window.Property(catalog.search))')
im=image(main,0,0,1920,1080,prop('fanart'),aspect='scale');tag(im,'fadetime',300)
image(main,0,0,1920,1080,'streampilot/catalog-shade.png')
button(main,5701,56,36,150,84,'‹ Back',down=50,right=5702)
label(main,238,28,1300,64,prop('section'),'sp_catalog_header','FFFFFFFF')
label(main,238,94,1300,32,prop('breadcrumb'),'sp_catalog_meta')
button(main,5702,1772,36,100,100,'',left=5701,down=50)
image(main,1797,61,50,50,'streampilot/catalog-search.png')
hero=node(main,'group',0,0,1920,550,visible='String.IsEmpty(Window.Property(catalog.loading)) + '+vis('title'))
image(hero,92,156,520,132,prop('clearlogo'),visible=vis('clearlogo'),aspect='keep')
title=node(hero,'textbox',92,156,1190,132,visible='String.IsEmpty(Window.Property(catalog.clearlogo))');tag(title,'label',prop('title'));tag(title,'font','sp_catalog_title');tag(title,'textcolor','FFFFFFFF')
label(hero,92,308,290,38,prop('released'))
image(hero,380,306,74,40,'streampilot/catalog-cert.png',visible=vis('certification'),border=12)
label(hero,380,306,74,40,prop('certification'),'sp_catalog_badge','FF000000',vis('certification'),'center')
rating=node(hero,'grouplist',92,352,1300,42);tag(rating,'orientation','horizontal');tag(rating,'itemgap',20)
for name,badge,width,badgewidth in [('tmdb','catalog-tmdb',144,80),('imdb','catalog-imdb',166,68),('rt','source-rating_rt_fresh',122,42),('metacritic','source-rating_metacritic',148,42)]:
 g=node(rating,'group',0,0,width,42,visible=vis(name))
 texture=prop('rt_badge') if name=='rt' else 'streampilot/'+badge+'.png'
 image(g,0,3,badgewidth,34,texture,aspect='keep' if name in ('rt','metacritic') else None)
 if name in ('tmdb','imdb'):label(g,0,3,badgewidth,34,'TMDB' if name=='tmdb' else 'IMDb','sp_catalog_badge','FFFFFFFF' if name=='tmdb' else 'FF000000',align='center')
 label(g,badgewidth+10,0,width-badgewidth-10,42,prop(name))
label(hero,92,400,1350,34,prop('details'))
plot=node(hero,'textbox',92,444,1010,110);tag(plot,'font','sp_catalog_body');tag(plot,'textcolor','D6FFFFFF');tag(plot,'label',prop('plot'));tag(plot,'autoscroll','Skin.HasSetting(autoscroll)',delay='4500',time='15000',repeat='3500')
studio=image(hero,1624,370,240,80,prop('studio_logo'),aspect='keep');studio.find('aspectratio').set('align','right');studio.find('aspectratio').set('aligny','center')
rail=node(main,'list',0,434,1920,643,50);tag(rail,'viewtype','icon',label='StreamPilot VOD');tag(rail,'orientation','horizontal');tag(rail,'scrolltime',280);tag(rail,'onup',5701);tag(rail,'ondown',5703);tag(rail,'onleft',50);tag(rail,'onright',50);tag(rail,'preloaditems',3)
for focused in (False,True):
 layout=E.SubElement(rail,'focusedlayout' if focused else 'itemlayout',width='272',height='643')
 if focused:layout.set('infoupdate','100')
 poster=node(layout,'group',64,142,240,360,visible='String.IsEqual(ListItem.Property(catalog.kind),media)')
 if focused:
  a=E.SubElement(poster,'animation',type='Conditional',condition='Control.HasFocus(50)',reversible='true');E.SubElement(a,'effect',type='zoom',start='100',end='119',center='auto',time='170',tween='sine',easing='inout')
  for offset in (73,30,11):
   image(poster,-offset,-offset,240+2*offset,360+2*offset,'$INFO[ListItem.Art(foundry.slate.catalog.glow)]',visible='Control.HasFocus(50)')
 p=image(poster,0,0,240,360,'$INFO[ListItem.Art(poster)]',aspect='scale');p.find('texture').set('diffuse','streampilot/catalog-poster-mask.png');p.find('texture').set('fallback','DefaultMovies.png')
 arrow=node(layout,'group',64,234,208,152,visible='!String.IsEqual(ListItem.Property(catalog.kind),media)')
 if focused:
  a=E.SubElement(arrow,'animation',type='Conditional',condition='Control.HasFocus(50)',reversible='true');E.SubElement(a,'effect',type='zoom',start='100',end='108',center='auto',time='150')
 image(arrow,0,0,208,152,'$INFO[ListItem.Property(catalog.arrow)]');label(arrow,0,0,170,152,'$INFO[ListItem.Label]','sp_catalog_button','FFFFFFFF',align='center')
label(main,110,994,185,40,prop('page'))
button(main,5703,298,984,160,76,prop('sort_label'),up=50,left=50,right=50)
label(main,560,994,1100,40,prop('scope'),'sp_catalog_small','FFAAB3C7')
sort=node(main,'group',298,550,520,416,visible=vis('sortopen'));image(sort,0,0,520,416,'streampilot/catalog-white.png',tint='FF171717')
for i,text in enumerate(['Date · Oldest first','Date · Newest first','Alphabetical · A-Z','Alphabetical · Z-A']):
 b=button(sort,5750+i,12,12+98*i,496,96,text,up=5750+max(0,i-1),down=5750+min(3,i+1));b.find('texturefocus').set('colordiffuse','4DFFFFFF');b.find('texturenofocus').set('colordiffuse','00FFFFFF')
notice=node(main,'group',0,0,1920,1080,visible=vis('loading'));image(notice,700,400,520,160,'streampilot/catalog-cert.png',tint='7A000000',border=44);label(notice,750,422,420,42,'LOADING','sp_catalog_meta','FFFFFFFF',align='center');label(notice,750,474,420,38,prop('preparing'),'sp_catalog_small',align='center')
label(main,310,400,1300,100,prop('message'),'sp_catalog_body',visible=vis('message'),align='center')
search=node(controls,'group',0,0,1920,1080,visible=vis('search'));image(search,0,0,1920,1080,'streampilot/catalog-white.png',tint='FF07101D');image(search,48,48,570,984,'streampilot/catalog-search-panel.png',tint='0AFFFFFF',border=32)
label(search,76,76,500,42,'VOD SEARCH','sp_catalog_meta','FFFFFFFF');label(search,76,118,500,30,prop('search_scope'),'sp_catalog_small')
edit=node(search,'edit',76,174,514,96,5801);tag(edit,'font','sp_catalog_meta');tag(edit,'textcolor','FFFFFFFF');tag(edit,'texturefocus','streampilot/catalog-search-panel.png',border='20',colordiffuse='55FFFFFF');tag(edit,'texturenofocus','streampilot/catalog-search-panel.png',border='20',colordiffuse='18FFFFFF');tag(edit,'onright',51);tag(edit,'ondown',5830)
for i in range(10):button(search,5830+i,76,300+i*58,514,54,prop('history'+str(i)),up=5801 if i==0 else 5829+i,down=5831+i if i<9 else 5802,right=51,visible=vis('history'+str(i)))
button(search,5802,76,928,514,76,'BACK TO LIBRARY',up=5801,right=51)
label(search,678,52,1150,64,prop('results_label'),'sp_catalog_results','FFFFFFFF')
panel=node(search,'panel',662,132,1210,866,51);tag(panel,'viewtype','icon',label='VOD Search');tag(panel,'onleft',5801);tag(panel,'onup',5801);tag(panel,'ondown',5812);tag(panel,'scrolltime',220)
for focused in (False,True):
 layout=E.SubElement(panel,'focusedlayout' if focused else 'itemlayout',width='396',height='579')
 g=node(layout,'group',24,24,354,531)
 if focused:
  a=E.SubElement(g,'animation',type='Conditional',condition='Control.HasFocus(51)',reversible='true');E.SubElement(a,'effect',type='zoom',start='100',end='104',center='auto',time='140')
 im=image(g,0,0,354,531,'$INFO[ListItem.Art(poster)]',aspect='scale');im.find('texture').set('diffuse','streampilot/catalog-poster-mask.png');image(g,0,443,354,88,'streampilot/catalog-white.png',tint='CC000000');label(g,16,447,322,78,'$INFO[ListItem.Label]','sp_catalog_small','FFFFFFFF')
label(search,678,400,1150,100,prop('search_message'),'sp_catalog_meta',visible=vis('search_message'),align='center')
button(search,5811,686,1000,190,62,'PREVIOUS',up=51,right=5812);label(search,900,1000,450,62,prop('page'),'sp_catalog_small',align='center');button(search,5812,1570,1000,190,62,'NEXT',up=51,left=5811)
E.indent(w,space='  ');E.ElementTree(w).write(R/'xml/script-foundry-vod.xml',encoding='UTF-8',xml_declaration=True)
# Dedicated font names leave existing Home/OSD and legacy view typography untouched.
p=R/'xml/Font.xml';doc=E.parse(p)
for fs in doc.getroot():
 arial=fs.get('id')=='Arial'
 for name,size,bold in [('header',58,True),('title',54,True),('meta',26,False),('small',22,False),('badge',20,True),('button',30,True),('body',28,False),('results',38,True)]:
  key='sp_catalog_'+name
  if fs.find("font[name='%s']"%key) is not None:continue
  n=E.SubElement(fs,'font');tag(n,'name',key);tag(n,'filename','arial.ttf' if arial else ('Roboto-Bold.ttf' if bold else 'Roboto-Regular.ttf'));tag(n,'size',size)
  if arial and bold:tag(n,'style','bold')
text=p.read_text();parts=text.split('</fontset>');output=[]
for i,part in enumerate(parts[:-1]):
 fs=doc.getroot()[i]
 additions=[E.tostring(f,encoding='unicode').strip() for f in fs.findall('font') if f.findtext('name','').startswith('sp_catalog_') and ('<name>'+f.findtext('name')+'</name>') not in part]
 output.append(part+('\n    '+'\n    '.join(additions)+'\n  ' if additions else '')+'</fontset>')
p.write_text(''.join(output)+parts[-1],newline='\n')
print('Custom catalog XML, dedicated fonts and native badge/UI textures generated.')
