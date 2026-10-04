"""Import legacy entry JSONs through API, preserve raw bytes separately."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
import httpx

p=argparse.ArgumentParser()
p.add_argument('folder',type=Path)
p.add_argument('--url',default='http://127.0.0.1:8000')
p.add_argument('--archive',type=Path,default=Path('data/legacy'))
a=p.parse_args()
a.archive.mkdir(parents=True,exist_ok=True)
with httpx.Client(base_url=a.url,headers={'Authorization':'Bearer '+os.environ['FRISS_API_KEY']},timeout=60) as client:
    for path in sorted(a.folder.glob('*.json')):
        raw=path.read_bytes(); old=json.loads(raw)
        digest=hashlib.sha256(raw).hexdigest()
        target=a.archive/(digest+'.json')
        if not target.exists(): target.write_bytes(raw)
        if old.get('type') not in ['text','barcode','picture','item']:
            print(path.name, 'archived; result-only JSON requires manual association'); continue
        entry={'id':str(uuid5(NAMESPACE_URL,'friss:legacy:'+digest)), 'timestamp':old['timestamp'], 'type':old['type']}
        amount=old.get('amount')
        if isinstance(amount,(int,float)) and amount>0: entry['quantity']={'value':amount,'unit':'g'}
        if old.get('barcode') is not None: entry['barcode']=str(old['barcode'])
        if old.get('description') or old.get('string'): entry['description']=old.get('description') or old.get('string')
        if old.get('result',{}).get('bls_code'): entry['bls_code']=old['result']['bls_code']
        if old.get('filename'): entry['filename']=old['filename']
        response=client.post('/entries',json=entry); response.raise_for_status()
        if old.get('filename'):
            image=a.folder/Path(old['filename']).name
            if image.exists():
                image_raw=image.read_bytes(); image_digest=hashlib.sha256(image_raw).hexdigest()
                (a.archive/(image_digest+image.suffix)).write_bytes(image_raw)
                client.put('/entries/'+entry['id']+'/photo',content=image_raw,headers={'Content-Type':'image/jpeg'}).raise_for_status()
            else: print(path.name,'photo missing; copy original JPEG under filename before retry')
        print(path.name,response.json()['status'])
