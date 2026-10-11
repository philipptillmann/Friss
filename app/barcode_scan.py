"""Decode photographed retail barcodes locally, without an external image service."""
import io
import warnings
from fastapi import Depends, HTTPException, Request
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

def valid_gtin(code):
    return code.isascii() and code.isdigit() and len(code) in (8,12,13) and sum(int(c)*(3 if i%2==0 else 1) for i,c in enumerate(reversed(code[:-1])))%10 == (-int(code[-1]))%10

def decode(data):
    import zxingcpp
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in ('JPEG','PNG','WEBP'):
                    raise HTTPException(422,'Unsupported image format')
                if source.width*source.height>16000000:
                    raise HTTPException(422,'Image exceeds 16 megapixels')
                image=ImageOps.exif_transpose(source).convert('RGB')
                results=zxingcpp.read_barcodes(image,formats=zxingcpp.BarcodeFormat.EAN13|zxingcpp.BarcodeFormat.EAN8|zxingcpp.BarcodeFormat.UPCA,try_rotate=True,try_downscale=True)
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        raise HTTPException(422,'Invalid image')
    codes=list(dict.fromkeys(r.text for r in results if valid_gtin(r.text)))
    if not codes: raise HTTPException(422,'No retail barcode found')
    return {'barcodes':codes}

def install(app,auth):
    @app.post('/barcode-scan',dependencies=[Depends(auth)])
    async def scan(request:Request):
        content=bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content)>10*1024*1024: raise HTTPException(413,'Image exceeds 10 MiB')
        return await run_in_threadpool(decode,bytes(content))
