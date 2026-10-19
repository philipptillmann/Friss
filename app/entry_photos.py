"""Immutable original input images, attached independently of meal nutrients."""
import hashlib
import io
import os
import re
import tempfile
import warnings
from uuid import UUID
from fastapi import Depends,HTTPException,Request,Response
from PIL import Image,UnidentifiedImageError

MAX_BYTES=15*1024*1024
MAX_PIXELS=40_000_000
MAX_PHOTOS=20
FORMATS={'JPEG':('jpeg','image/jpeg'),'PNG':('png','image/png'),'WEBP':('webp','image/webp')}

def stored(data,id):
    return sorted(p for p in (data/'originals').glob(str(id)+'-photo-*') if re.fullmatch(re.escape(str(id))+r'-photo-[a-f0-9]{64}\.(jpeg|png|webp)',p.name) and p.is_file() and not p.is_symlink())

def metadata(path,id):
    photo_id=path.name.split('-photo-',1)[1].split('.')[0]
    return {'id':photo_id,'url':f'/entries/{id}/photos/{photo_id}','size':path.stat().st_size,'content_type':{'jpeg':'image/jpeg','png':'image/png','webp':'image/webp'}[path.suffix[1:]]}

def listing(data,id):return [metadata(p,id) for p in stored(data,id)]

def immutable(path,content):
    # Publish only fully-written originals; failed/retried requests never replace one.
    with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.photo-',delete=False) as f:
        temp=f.name
        try:
            f.write(content);f.flush();os.fsync(f.fileno())
            try:os.link(temp,path)
            except FileExistsError:
                if path.read_bytes()!=content:raise HTTPException(409,'Original image conflicts with stored file')
        finally:os.unlink(temp)

def copy(data,source,target):
    for photo in stored(data,source):
        destination=photo.with_name(str(target)+photo.name[len(str(source)):])
        immutable(destination,photo.read_bytes())

def install(app,db,auth,load_entry,data_dir):
    @app.put('/entries/{id}/photos',dependencies=[Depends(auth)])
    async def upload(id:UUID,request:Request):
        load_entry(id)
        content=bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content)>MAX_BYTES:raise HTTPException(413,'Photo exceeds 15 MiB')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as image:
                    if image.format not in FORMATS or getattr(image,'n_frames',1)!=1:raise ValueError('Unsupported image format')
                    if image.width*image.height>MAX_PIXELS:raise ValueError('Image exceeds 40 megapixels')
                    extension,_=FORMATS[image.format];image.load()
        except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombWarning,Image.DecompressionBombError):
            raise HTTPException(422,'A valid static JPEG, PNG or WebP image up to 40 megapixels is required; convert HEIC to JPEG in Shortcuts')
        photo_id=hashlib.sha256(content).hexdigest()
        path=data_dir()/'originals'/f'{id}-photo-{photo_id}.{extension}'
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not c.execute('SELECT id FROM entries WHERE id=?',(str(id),)).fetchone():raise HTTPException(404,'Entry not found')
            if not path.exists() and len(stored(data_dir(),id))>=MAX_PHOTOS:raise HTTPException(422,'Maximum 20 photos per entry')
            immutable(path,content)
        return metadata(path,id)

    @app.get('/entries/{id}/photos',dependencies=[Depends(auth)])
    async def photos(id:UUID):
        load_entry(id)
        return listing(data_dir(),id)

    @app.get('/entries/{id}/photos/{photo_id}',dependencies=[Depends(auth)])
    async def original(id:UUID,photo_id:str):
        load_entry(id)
        if not re.fullmatch(r'[a-f0-9]{64}',photo_id):raise HTTPException(404,'Photo not found')
        path=next((p for p in stored(data_dir(),id) if metadata(p,id)['id']==photo_id),None)
        if path is None:raise HTTPException(404,'Photo not found')
        return Response(path.read_bytes(),media_type=metadata(path,id)['content_type'],headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Disposition':'inline; filename="'+photo_id+path.suffix+'"'})
