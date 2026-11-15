"""Remove only shadowed Slate default entries from XBTF2 index; never alter frame payloads.
Format verified against official Kodi Omega XBTFReader.cpp, XBTF.h.
"""
from pathlib import Path
import struct,json,hashlib,argparse

def parse(data):
 assert data[:5]==b'XBTF2','Only audited XBTF2 supported'
 count=struct.unpack_from('<I',data,5)[0];pos=9;entries={}
 for _ in range(count):
  start=pos;name=data[pos:pos+256].split(b'\0')[0].decode();pos+=256
  loop,n=struct.unpack_from('<II',data,pos);pos+=8;frames=[]
  for i in range(n):
   w,h,fmt,packed,raw,duration,offset=struct.unpack_from('<IIIQQIQ',data,pos);pos+=40
   assert offset+packed<=len(data),(name,'invalid payload')
   frames.append((offset,packed,hashlib.sha256(data[offset:offset+packed]).hexdigest()))
  assert name not in entries;entries[name]={'index':data[start:pos],'frames':frames}
 return entries,pos

def patch(source,manifest,media,resource,dest,receipt):
 raw=source.read_bytes();old,header=parse(raw)
 names={n.casefold() for n in json.loads(manifest.read_text())['texture_aliases'] if '/' not in n and n.startswith(('Default','Overlay'))}
 removed=[];kept=[]
 for name,e in old.items():
  if name.casefold() in names:
   alias=next(n for n in json.loads(manifest.read_text())['texture_aliases'] if n.casefold()==name.casefold())
   assert (media/alias).read_bytes()==(resource/alias).read_bytes(),('Missing/mismatched loose replacement',alias)
   removed.append(name)
  else:kept.append(e['index'])
 assert removed,'No shadow collisions found'
 newhead=b'XBTF2'+struct.pack('<I',len(kept))+b''.join(kept)
 result=newhead+bytes(header-len(newhead))+raw[header:]
 new,newheader=parse(result)
 assert set(new)==set(old)-set(removed)
 assert result[header:]==raw[header:],'Payload must stay byte-identical'
 for name,e in new.items():assert e==old[name],('Retained texture changed',name)
 dest.write_bytes(result)
 evidence={'source_sha256':hashlib.sha256(raw).hexdigest(),'result_sha256':hashlib.sha256(result).hexdigest(),'removed':removed,'retained':len(new),'original_header_bytes':header,'new_header_bytes':newheader,'payload_identical':True,'retained_index_and_frames_identical':True,'source_bytes':len(raw),'output_bytes':len(result),'format_source':'https://github.com/xbmc/xbmc/blob/Omega/xbmc/guilib/XBTFReader.cpp','priority_source':'https://github.com/xbmc/xbmc/blob/Omega/xbmc/guilib/TextureManager.cpp'}
 receipt.write_text(json.dumps(evidence,indent=2));return evidence
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 skin=a.repo/'src/skin.foundry.slate';res=a.repo/'src/resource.images.foundry.slate.icons/resources'
 print(json.dumps(patch(skin/'media/Textures.xbt',res/'manifest.json',skin/'media',res/'aliases',a.output,a.output.with_suffix('.receipt.json')),indent=2))
