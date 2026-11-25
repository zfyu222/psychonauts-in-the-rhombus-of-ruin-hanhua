"""Collect the 114 approved plates plus the 4 prompt plates into one verified set (v119)."""
import json,hashlib,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];W=P.parents[1]
def read(f):return json.loads(Path(f).read_text(encoding='utf8'))
def write(f,r):
    f=Path(f)
    if f.exists():raise FileExistsError(f)
    f.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')

NEW=['pressx','turnhead','adjust','pressselect']
plan=read(P/'ImagePatch/collect-verified-v114.json')
ids={i for item in plan['inputs'] for i in item['ids']}
assert len(ids)==114,ids
for n in NEW:
    d=read(P/f'ImagePatch/draw-prompt-{n}-v118/IMAGE_PATCH_MANIFEST.json')
    assert d['stage']=='final' and d['status']=='awaiting_final_qa',(n,d['status'])
    assert len(d['files'])==1
    key=d['files'][0]['image_id']
    assert key not in ids,'duplicate '+key
    plan['inputs'].append(dict(patch=str(P/f'ImagePatch/draw-prompt-{n}-v118'),qa=f'qa-draw-prompt-{n}-v118',ids=[key]))
    ids.add(key)
assert len(ids)==118,len(ids)
planfile=P/'ImagePatch/collect-verified-v119.json'
write(planfile,plan)
out=P/'ImagePatch/verified-v119-source-r2'
subprocess.run([sys.executable,str(W/'Tools/image_text/collect_verified_patch.py'),'--plan',str(planfile),'--out',str(out)],check=True)
man=read(out/'IMAGE_PATCH_MANIFEST.json')
print({'images':len(man['files']),'regions':len(man['entries']),'inputs':len(plan['inputs']),
       'status':man.get('status'),'visual_review':man.get('visual_review',{}).get('status')})
print('manifest sha256',hashlib.sha256((out/'IMAGE_PATCH_MANIFEST.json').read_bytes()).hexdigest())
