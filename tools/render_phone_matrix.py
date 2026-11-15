"""Run normal/restricted phone entry in both original and Slate, fail closed."""
import argparse,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--original-skin',type=Path)
p.add_argument('--original-helper',type=Path)
a=p.parse_args();r=a.root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
(out/'phone-matrix-verification.json').write_text(json.dumps({'passed':False,'status':'running or incomplete'}))
rows=[]
for name,skin,helper in [('original',a.original_skin or r.parent/'skin.foundry-nimbus',a.original_helper or r.parent/'script.foundry.helper'),('slate',r/'src/skin.foundry.slate',r/'src/script.foundry.slate.helper')]:
 for restricted in (False,True):
  target=out/(name+('-restricted' if restricted else '-normal'))
  command=[sys.executable,str(Path(__file__).with_name('native_phone_qa.py')),'--root',str(r),'--skin',str(skin),'--helper',str(helper),'--output',str(target)]
  if restricted:command.append('--restricted-enumeration')
  command.append('--native-debugger')
  try:subprocess.run(command,check=True)
  except subprocess.CalledProcessError:
   (out/'phone-matrix-verification.json').write_text(json.dumps({'passed':False,'completed_cases':rows,'failed_case':target.name,'failure_report':str(target/'phone-verification.json')},indent=2))
   raise
  result=json.loads((target/'phone-verification.json').read_text())
  assert result['passed'] is True and result['restricted_enumeration_real_ioctl']==restricted
  assert result['source_sha256'] and result['image_sha256'].get('actual-qr.png')
  rows.append(result)
assert len(rows)==4
(out/'phone-matrix-verification.json').write_text(json.dumps({'passed':True,'cases':rows,'qr_decode_verified':False,'physical_phone_verified':False},indent=2)+'\n')
