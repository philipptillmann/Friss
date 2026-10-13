"""Preview a single public FDDB German food page, without scripts or login."""
import math
import re
from datetime import datetime,timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException
from . import fooddata_import as common

NAMES={
 'kalorien':('EnergyConsumed','kcal'),'brennwert':('EnergyConsumed','kcal'),
 'protein':('Protein','g'),'eiweiß':('Protein','g'),'kohlenhydrate':('Carbohydrates','g'),
 'davon zucker':('Sugar','g'),'zucker':('Sugar','g'),'fett':('FatTotal','g'),
 'ballaststoffe':('Fiber','g'),'cholesterin':('Cholesterol','mg'),'koffein':('Caffeine','mg'),
 'wassergehalt':('Water','g'),'alkohol':('ethanol','g'),
 'gesättigte fettsäuren':('FatSaturated','g'),'davon gesättigte fettsäuren':('FatSaturated','g'),
 'einfach ungesättigte fettsäuren':('FatMonounsaturated','g'),
 'mehrfach ungesättigte fettsäuren':('FatPolyunsaturated','g'),
 'vitamin a':('VitaminA','mcg'),'vitamin b1':('Thiamin','mg'),
 'vitamin b2':('Riboflavin','mg'),'vitamin b3':('Niacin','mg'),'niacin':('Niacin','mg'),
 'vitamin b5':('PantothenicAcid','mg'),'pantothensäure':('PantothenicAcid','mg'),
 'vitamin b6':('VitaminB6','mg'),'vitamin b7':('Biotin','mcg'),'biotin':('Biotin','mcg'),
 'vitamin b12':('VitaminB12','mcg'),'vitamin c':('VitaminC','mg'),
 'vitamin d':('VitaminD','mcg'),'vitamin e':('VitaminE','mg'),'vitamin k':('VitaminK','mcg'),
 'folsäure':('Folate','mcg'),'folat':('Folate','mcg'),
 'kalzium':('Calcium','mg'),'calcium':('Calcium','mg'),'chlorid':('Chloride','mg'),
 'eisen':('Iron','mg'),'magnesium':('Magnesium','mg'),'phosphor':('Phosphorus','mg'),
 'kalium':('Potassium','mg'),'natrium':('Sodium','mg'),'zink':('Zinc','mg'),
 'chrom':('Chromium','mcg'),'kupfer':('Copper','mg'),'jod':('Iodine','mcg'),
 'mangan':('Manganese','mg'),'molybdän':('Molybdenum','mcg'),'selen':('Selenium','mcg')}

def canonical_url(value):
    try:
        u=urlsplit(value.strip())
        if u.scheme!='https' or u.hostname not in ('fddb.info','www.fddb.info') or u.username or u.password or u.port not in (None,443):raise ValueError()
        if not re.fullmatch(r'/db/de/lebensmittel/[a-z0-9_\-]{1,250}/index\.html',u.path):raise ValueError()
    except ValueError:raise HTTPException(422,'Use an FDDB food link: https://fddb.info/db/de/lebensmittel/…/index.html')
    return 'https://fddb.info'+u.path+'?nomobile=1'

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.rows=[];self.title='';self.active=False;self.basis=False
    def handle_starttag(self,tag,attrs):
        if tag not in ('meta','link','img','br','hr','input','source','area','wbr'):
            self.stack.append({'tag':tag,'attrs':dict(attrs),'text':'','children':[]})
    def handle_data(self,text):
        if self.stack:self.stack[-1]['text']+=text
    def handle_endtag(self,tag):
        if not self.stack or tag not in [n['tag'] for n in self.stack]:return
        while self.stack:
            node=self.stack.pop()
            if self.stack:
                self.stack[-1]['text']+=node['text']
                self.stack[-1]['children'].append(node)
            if node['tag']!=tag:continue
            text=' '.join(node['text'].split())
            if tag=='h1' and node['attrs'].get('id')=='fddb-headline1':self.title=text
            if tag=='h2':
                if re.fullmatch(r'Nährwerte für\s+100\s*g',text,re.I):self.basis=True;self.active=True
                elif text in ('Vitamine','Mineralstoffe'):self.active=self.basis
                else:self.active=False
            if tag=='div' and self.active:
                children=node['children']
                if len(children)==2 and 'sidrow' in children[0]['attrs'].get('class','').split() and children[1]['tag']=='div':
                    self.rows.append((' '.join(children[0]['text'].split()),' '.join(children[1]['text'].split())))
            break

def number(text):
    if not re.fullmatch(r'(?:\d+(?:,\d+)?|\d{1,3}(?:\.\d{3})+(?:,\d+)?)',text):raise ValueError()
    return common.number(text.replace('.','').replace(',','.'))

def parse(html,url):
    page=Page();page.feed(html)
    if not page.basis or not page.title or len(page.title)>200 or not page.rows or len(page.rows)>1000:
        raise HTTPException(422,'No supported FDDB per-100-g nutrient data found')
    nutrients={};original=[];skipped=[];ethanol=None
    # The site rounds kcal and kJ independently: use published kcal first.
    rows=sorted(page.rows,key=lambda r:common.normalized(r[0])=='brennwert')
    for name,text in rows:
        match=re.fullmatch(r'([\d.,]+)\s*([a-zA-Zµμ%]+)',text)
        original.append({'name':name,'value':match[1] if match else text,'unit':match[2] if match else ''})
        mapping=NAMES.get(common.normalized(name))
        if not mapping:skipped.append({'name':name,'reason':'unsupported_nutrient'});continue
        key,target=mapping
        try:
            if not match:raise ValueError()
            value=number(match[1]);unit=common.unit_name(match[2])
            if key=='Water' and match[2]=='%':
                if value>100:raise ValueError()
                unit='g' # percent water by mass: x grams per 100 g
            value=common.convert(value,unit,target,key)
            if not math.isfinite(value) or key=='ethanol' and value>100:raise ValueError()
        except (ValueError,TypeError,OverflowError):
            skipped.append({'name':name,'reason':'unknown_value_or_unit'});continue
        if key=='ethanol':
            if ethanol is not None and not math.isclose(ethanol,value):raise HTTPException(422,'Conflicting FDDB alcohol values')
            ethanol=value;continue
        identifier='dietary'+key
        if identifier in nutrients:
            if common.normalized(name)=='brennwert':continue
            if not math.isclose(nutrients[identifier]['value'],value,rel_tol=1e-6,abs_tol=1e-8):raise HTTPException(422,'Conflicting FDDB nutrient values: '+name)
        nutrients[identifier]={'value':value,'unit':target}
    if not nutrients and ethanol is None:raise HTTPException(422,'No supported FDDB nutrients with known units found')
    warnings=['FDDB values are imported as published per 100 g. Carbohydrates are not reduced by fibre. Review the source values before saving.',
              'Missing or unsupported values remain unknown. Food water stays in grams, not drinking-water volume.']
    return {'name_de':page.title,'name_en':page.title,'notes':'Imported from FDDB\nSource: '+url+'\n'+'\n'.join(warnings),
            'nutrients':nutrients,'ethanol_g_per100':ethanol,'warnings':warnings,'skipped':skipped,
            'source':{'provider':'FDDB','url':url,'imported_at':datetime.now(timezone.utc).isoformat(),'basis_g':100,'values':original,'carbohydrate_conversion':None}}

async def fetch(url):
    try:
        async with httpx.AsyncClient(timeout=15,follow_redirects=False,headers={'User-Agent':'Friss/1.20 (self-hosted nutrition importer)','Accept':'text/html'}) as client:
            async with client.stream('GET',url) as response:
                if response.status_code==404:raise HTTPException(404,'FDDB food page not found')
                if response.status_code!=200:raise HTTPException(502,'FDDB could not be imported (blocked, unavailable or redirected). Try again later.')
                if 'text/html' not in response.headers.get('content-type','').lower():raise HTTPException(422,'Expected an FDDB HTML page')
                content=bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content)>common.MAX_BYTES:raise HTTPException(422,'Source page is too large')
                return bytes(content).decode(response.encoding or 'utf-8',errors='replace')
    except httpx.HTTPError:raise HTTPException(502,'FDDB could not be reached; try again later')
