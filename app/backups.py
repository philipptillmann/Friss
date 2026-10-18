"""Portable JSON/ZIP backups. Credentials are never part of the archive."""
import asyncio
import base64
from contextlib import asynccontextmanager
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import PurePosixPath
import shutil
import sqlite3
import stat
import tempfile
from uuid import uuid4
import zipfile
from fastapi import Depends,HTTPException,Request,Response
from fastapi.responses import JSONResponse

TABLES=('foods','search_selections','food_search_selections','preferences','button_images','manual_ingredients','favorites','recipes','health_days','entries','json_import_batches')
ROOTS=('originals','bls')
MAX_ZIP=128*1024*1024
MAX_EXPANDED=512*1024*1024
MAX_FILES=30000
SCHEMA='friss-backup-v1'

class Gate:
    def __init__(self):
        self.condition=asyncio.Condition();self.active=0;self.closed=False

    @asynccontextmanager
    async def exclusive(self):
        async with self.condition:
            if self.closed:raise HTTPException(409,'Another backup or restore is running')
            self.closed=True
            try:await asyncio.wait_for(self.condition.wait_for(lambda:self.active<=1),30)
            except BaseException as exc:
                self.closed=False;self.condition.notify_all()
                if isinstance(exc,TimeoutError):raise HTTPException(503,'Requests are still active; retry backup later')
                raise
        try:yield
        finally:
            async with self.condition:self.closed=False;self.condition.notify_all()

def columns(c,table):return [r['name'] for r in c.execute('PRAGMA table_info('+table+')')]
def digest(data):return hashlib.sha256(data).hexdigest()

def build(db,data,version):
    tables={};files={};blobs={}
    with db() as c:
        c.execute('BEGIN')
        for table in TABLES:
            tables[table]=[]
            for r in c.execute('SELECT * FROM '+table):
                row=dict(r)
                if table=='button_images':row['content']={'base64':base64.b64encode(row['content']).decode()}
                tables[table].append(row)
    size=0
    for root in ROOTS:
        directory=data/root
        if directory.is_symlink():raise HTTPException(409,'Cannot back up symlinked data directories')
        for p in sorted(directory.rglob('*')) if directory.exists() else []:
            if p.is_symlink():raise HTTPException(409,'Cannot back up symlinked data files')
            if not p.is_file():continue
            size+=p.stat().st_size
            if size>MAX_EXPANDED or len(files)>=MAX_FILES:raise HTTPException(413,'Backup exceeds size or file limit')
            name='files/'+root+'/'+p.relative_to(directory).as_posix();content=p.read_bytes()
            blobs[name]=content;files[name]={'size':len(content),'sha256':digest(content)}
    doc={'schema':SCHEMA,'app_version':version,'created_at':datetime.now(timezone.utc).isoformat(),'tables':tables,'files':files}
    raw=json.dumps(doc,ensure_ascii=False,allow_nan=False).encode()
    if len(raw)+size>MAX_EXPANDED:raise HTTPException(413,'Backup exceeds expanded size limit')
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('backup.json',raw)
        for name,content in blobs.items():z.writestr(name,content)
    archive=out.getvalue()
    if len(archive)>MAX_ZIP:raise HTTPException(413,'Backup exceeds ZIP size limit')
    return archive

def unpack(content,db):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            infos=z.infolist();names=[i.filename for i in infos]
            if len(names)!=len(set(names)) or len(names)>MAX_FILES+1:raise ValueError('Duplicate ZIP names or too many files')
            if sum(i.file_size for i in infos)>MAX_EXPANDED:raise ValueError('Expanded ZIP exceeds limit')
            for i in infos:
                p=PurePosixPath(i.filename)
                if i.filename!=p.as_posix() or i.is_dir() or i.flag_bits&1 or stat.S_ISLNK(i.external_attr>>16) or '\\' in i.filename or p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe ZIP path or member')
                if i.filename!='backup.json' and (len(p.parts)<3 or p.parts[0]!='files' or p.parts[1] not in ROOTS):raise ValueError('Unexpected ZIP file')
            def pairs(items):
                out={}
                for k,v in items:
                    if k in out:raise ValueError('Duplicate JSON key')
                    out[k]=v
                return out
            doc=json.loads(z.read('backup.json'),object_pairs_hook=pairs,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Non-finite JSON number')))
            if not isinstance(doc,dict) or doc.get('schema')!=SCHEMA:raise ValueError('Unsupported backup format')
            if not isinstance(doc.get('tables'),dict) or set(doc['tables'])!=set(TABLES):raise ValueError('Missing or unknown data tables')
            files=doc.get('files')
            if not isinstance(files,dict) or set(names)!={'backup.json',*files}:raise ValueError('Attachment manifest mismatch')
            blobs={}
            for name,meta in files.items():
                blob=z.read(name)
                if not isinstance(meta,dict) or meta.get('size')!=len(blob) or meta.get('sha256')!=digest(blob):raise ValueError('Attachment checksum mismatch')
                blobs[name]=blob
        with db() as c:
            for table,rows in doc['tables'].items():
                if not isinstance(rows,list):raise ValueError('Invalid table rows')
                expected=set(columns(c,table))
                for row in rows:
                    if not isinstance(row,dict) or set(row)!=expected:raise ValueError('Incompatible columns: '+table)
                    if table=='button_images':
                        value=row['content']
                        if not isinstance(value,dict) or set(value)!={'base64'}:raise ValueError('Invalid image')
                        row['content']=base64.b64decode(value['base64'],validate=True)
                    for key,value in row.items():
                        if value is not None and not isinstance(value,(str,int,float,bytes)):raise ValueError('Invalid table value')
                        if key=='payload':
                            payload=json.loads(value)
                            if not isinstance(payload,dict):raise ValueError('Invalid record payload')
                            if table in ('entries','recipes','manual_ingredients','favorites','health_days','json_import_batches') and 'id' in payload and str(payload['id'])!=str(row['id'] if 'id' in row else row['code']):raise ValueError('Record ID mismatch')
                            if table=='entries' and not {'id','type','timestamp','status','health_status','revision'}<=set(payload):raise ValueError('Invalid diary entry')
        return doc,blobs
    except (ValueError,KeyError,TypeError,RecursionError,zipfile.BadZipFile,NotImplementedError,RuntimeError) as exc:
        raise HTTPException(422,'Invalid Friss backup: '+str(exc)[:200])

def summary(doc):
    return {'schema':doc['schema'],'created_at':doc.get('created_at'),'app_version':doc.get('app_version'),'counts':{t:len(rows) for t,rows in doc['tables'].items()},'files':len(doc['files'])}

def restore(doc,blobs,db,data,version):
    # Keep the previous state outside the replaced folders for manual recovery.
    recovery=data/'recovery';recovery.mkdir(exist_ok=True)
    name='before-restore-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+str(uuid4())+'.zip'
    archive=build(db,data,version)
    with (recovery/name).open('xb') as f:f.write(archive)
    with tempfile.TemporaryDirectory(prefix='.restore-',dir=data) as tmp:
        from pathlib import Path
        stage=Path(tmp);moved=[];installed=[]
        for root in ROOTS:(stage/root).mkdir()
        for name_in_zip,blob in blobs.items():
            target=stage/PurePosixPath(name_in_zip).relative_to('files');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(blob)
        try:
            with db() as c:
                c.execute('BEGIN IMMEDIATE')
                for table in TABLES:
                    c.execute('DELETE FROM '+table)
                    cols=columns(c,table)
                    for row in doc['tables'][table]:c.execute('INSERT INTO '+table+' ('+','.join(cols)+') VALUES ('+','.join('?' for _ in cols)+')',[row[k] for k in cols])
                for root in ROOTS:
                    if (data/root).exists():(data/root).rename(stage/('old-'+root));moved.append(root)
                    (stage/root).rename(data/root);installed.append(root)
        except BaseException:
            for root in reversed(installed):shutil.rmtree(data/root)
            for root in reversed(moved):(stage/('old-'+root)).rename(data/root)
            raise
    return name

def install(app,db,auth,data_dir):
    @app.middleware('http')
    async def maintenance(request,call_next):
        gate=app.state.backup_gate
        async with gate.condition:
            if gate.closed:return JSONResponse({'detail':'Backup or restore in progress; retry shortly'},503,headers={'Retry-After':'5'})
            gate.active+=1
        try:return await call_next(request)
        finally:
            async with gate.condition:gate.active-=1;gate.condition.notify_all()

    async def upload(request):
        content=bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content)>MAX_ZIP:raise HTTPException(413,'ZIP exceeds 128 MiB')
        return unpack(content,db)

    @app.get('/backups/export',dependencies=[Depends(auth)])
    async def export():
        async with app.state.backup_gate.exclusive():archive=build(db,data_dir(),app.version)
        name='friss-backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.zip'
        return Response(archive,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="'+name+'"','Cache-Control':'no-store'})

    @app.post('/backups/inspect',dependencies=[Depends(auth)])
    async def inspect(request:Request):
        doc,_=await upload(request)
        return JSONResponse(summary(doc),headers={'Cache-Control':'no-store'})

    @app.post('/backups/restore',dependencies=[Depends(auth)])
    async def recover(request:Request):
        if request.headers.get('X-Friss-Restore')!='replace':raise HTTPException(422,'Explicit replacement confirmation required')
        doc,blobs=await upload(request)
        async with app.state.backup_gate.exclusive():
            try:name=restore(doc,blobs,db,data_dir(),app.version)
            except (sqlite3.Error,OSError) as exc:raise HTTPException(422,'Restore failed; previous state retained: '+type(exc).__name__)
        return {'restored':True,**summary(doc),'recovery_backup':'recovery/'+name}
