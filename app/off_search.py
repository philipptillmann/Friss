"""Authenticated, bounded Open Food Facts text search with short-lived cache."""
import time
from collections import OrderedDict,deque
import httpx
from fastapi import Depends,HTTPException,Query

URL='https://search.openfoodfacts.org/search'
LEGACY_URL='https://world.openfoodfacts.org/cgi/search.pl'
MAX_BYTES=2*1024*1024
cache=OrderedDict()
requests=deque()

def products(data,lang):
    if not isinstance(data,dict):raise HTTPException(502,'Invalid Open Food Facts search response')
    rows=data.get('hits',data.get('products'))
    if not isinstance(rows,list):raise HTTPException(502,'Invalid Open Food Facts search response')
    found=[];seen=set()
    for p in rows:
        if not isinstance(p,dict):continue
        code=str(p.get('code',''))
        if not code.isascii() or not code.isdigit() or not 8<=len(code)<=14 or code in seen:continue
        name=p.get('product_name_'+lang) or p.get('product_name') or p.get('product_name_en') or code
        if not isinstance(name,str):continue
        brands=p.get('brands') or ''
        if isinstance(brands,list):brands=', '.join(str(b) for b in brands)
        seen.add(code)
        found.append({'barcode':code,'display_name':name[:300],'brand':str(brands)[:200],'package_quantity':str(p.get('quantity') or '')[:100]})
    return found

async def search(q,lang,limit):
    key=(q.casefold(),lang,limit);now=time.monotonic()
    saved=cache.get(key)
    if saved and saved[0]>now:
        cache.move_to_end(key);return saved[1]
    while requests and requests[0]<=now-60:requests.popleft()
    if len(requests)>=8:raise HTTPException(429,'Open Food Facts search limit reached. Please wait one minute.',headers={'Retry-After':'60'})
    requests.append(now)
    params={'q':q,'page_size':limit,'page':1,'langs':lang}
    legacy={'search_terms':q,'search_simple':1,'action':'process','json':1,'page_size':limit,'page':1,'lc':lang,'fields':'code,product_name,product_name_de,product_name_en,brands,quantity'}
    async def fetch(client,url,params):
        async with client.stream('GET',url,params=params) as response:
            if response.status_code==429:raise HTTPException(429,'Open Food Facts search is rate limited. Please wait one minute.',headers={'Retry-After':'60'})
            response.raise_for_status()
            content=bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content)>MAX_BYTES:raise HTTPException(502,'Open Food Facts search response is too large')
            import json
            return products(json.loads(content),lang)[:limit]
    try:
        async with httpx.AsyncClient(timeout=12,follow_redirects=False,headers={'User-Agent':'Friss/1.31 (self-hosted; https://github.com/philipptillmann/Friss)','Accept':'application/json'}) as client:
            try:result=await fetch(client,URL,params)
            except (httpx.HTTPError,ValueError,TypeError):result=await fetch(client,LEGACY_URL,legacy)
    except (httpx.HTTPError,ValueError,TypeError):raise HTTPException(502,'Open Food Facts search is unavailable. Try again later.')
    cache[key]=(time.monotonic()+300,result);cache.move_to_end(key)
    while len(cache)>128:cache.popitem(last=False)
    return result

def install(app,auth):
    @app.get('/products/search',dependencies=[Depends(auth)])
    async def endpoint(q:str=Query(min_length=2,max_length=80),lang:str=Query(default='de',pattern='^(de|en)$'),limit:int=Query(default=15,ge=1,le=20)):
        q=' '.join(q.split())
        if len(q)<2:raise HTTPException(422,'Enter at least two characters')
        return await search(q,lang,limit)
