Object.assign(words.de,{unifiedSearch:'Lebensmittel und Rezepte suchen',sourceBLS:'BLS',sourceOFF:'Open Food Facts',sourceManual:'Eigene Zutat',sourceRecipe:'Rezept',sourceDrink:'Getränk',sourceFavorite:'Favorit',unifiedLoading:'Weitere Produkte aus Open Food Facts werden gesucht …',unifiedOffline:'Lokale Treffer sind verfügbar. Open Food Facts: ',searchHome:'Suchen',searchFav:'Favorit'});
Object.assign(words.en,{unifiedSearch:'Search foods and recipes',sourceBLS:'BLS',sourceOFF:'Open Food Facts',sourceManual:'My ingredient',sourceRecipe:'Recipe',sourceDrink:'Drink',sourceFavorite:'Favorite',unifiedLoading:'Searching more products in Open Food Facts …',unifiedOffline:'Local results are available. Open Food Facts: ',searchHome:'Search',searchFav:'Favorite'});
(function(){
 let timer=null,sequence=0,shown=[],highlight=-1;
 const label=r=>t(r.source==='recipe'?(r.category==='drink'?'sourceDrink':'sourceRecipe'):{bls:'sourceBLS',off:'sourceOFF',manual:'sourceManual',favorite:'sourceFavorite'}[r.source]);
 function invalidate(){sequence++;clearTimeout(timer);highlight=-1;shown=[];$('results').replaceChildren();$('unifiedSearchStatus').textContent='';}
 async function learn(query,result,language){try{await api('/search/selections',{method:'POST',body:JSON.stringify({id:uuid(),query,lang:language,token:result.selection_token})});}catch(e){if(!$('dashboard').hidden)message(t('searchLearningError')+' '+e.message,true);}}
 function choose(result,query,language){
  invalidate();learn(query,result,language);reusedVia=null;
  if(result.source==='favorite'){useReusable({entry:result.entry,name_de:result.label,name_en:result.label,id:result.id});$('results').replaceChildren();return;}
  selected=result;$('kind').value='item';
  if(result.source==='bls')selected.bls_code=result.id;
  if(result.source==='recipe'){renderMealRecipeChoices();$('mealRecipe').value=result.id;$('mealRecipeAmount').value=1;$('mealRecipeUnit').value='portion';updateMealRecipeInfo();}
  else if(!$('amount').value&&result.default_quantity?.unit==='g')$('amount').value=result.default_quantity.value;
  kindChange(false);$('selected').textContent=result.label+' · '+label(result);$('results').replaceChildren();
  (result.source==='recipe'?$('mealRecipeAmount'):$('amount')).focus();
 }
 function show(results,query,language){
  if(editing)results=results.filter(r=>r.source==='bls');
  shown=results;highlight=-1;$('results').replaceChildren();
  for(const result of results){const button=document.createElement('button');button.type='button';button.className='result';button.setAttribute('role','option');button.setAttribute('aria-selected','false');
   const source=document.createElement('span');source.className='sourceBadge source-'+(result.source==='recipe'&&result.category==='drink'?'drink':result.source);source.textContent=label(result);
   const name=document.createElement('span');name.className='searchResultName';name.textContent=result.label+[result.brand,result.package_quantity].filter(Boolean).map(s=>' · '+s).join('');button.append(source,name);
   if(result.favorite){const star=document.createElement('span');star.className='searchFavorite';star.textContent='★';star.setAttribute('aria-label',t('searchFav'));button.append(star);}
   button.onclick=()=>choose(result,query,language);$('results').append(button);
  }
  if(!results.length)$('results').textContent=t('none');
 }
 $('search').oninput=()=>{
  invalidate();reusedVia=null;selected=null;kindChange(false);$('selected').textContent='';$('results').replaceChildren();
  const mine=sequence,query=$('search').value.trim(),language=lang;if(!query)return;
  const context='&include_recipes='+(!recipePage()&&!editing);
  let remoteDone=false;
  const valid=()=>mine===sequence&&language===lang&&!$('dashboard').hidden&&$('kind').value==='item';
  api('/search?q='+encodeURIComponent(query)+'&lang='+language+'&remote=false'+context).then(data=>{if(valid()&&!remoteDone)show(data.results,query,language);}).catch(e=>{if(valid()&&!remoteDone)message(e.message,true);});
  if(query.length>=2){$('unifiedSearchStatus').textContent=t('unifiedLoading');timer=setTimeout(async()=>{try{
   const data=await api('/search?q='+encodeURIComponent(query)+'&lang='+language+'&remote=true'+context);if(!valid())return;remoteDone=true;show(data.results,query,language);$('unifiedSearchStatus').textContent=data.warnings.length?t('unifiedOffline')+data.warnings.join(' '):'';
  }catch(e){if(valid())$('unifiedSearchStatus').textContent=t('unifiedOffline')+e.message;}},650);}
 };
 $('search').onkeydown=event=>{
  if(!shown.length)return;
  if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();highlight=(highlight+(event.key==='ArrowDown'?1:-1)+shown.length)%shown.length;Array.from($('results').children).forEach((b,i)=>b.setAttribute('aria-selected',String(i===highlight)));}
  if(event.key==='Enter'&&highlight>=0){event.preventDefault();$('results').children[highlight].click();}
  if(event.key==='Escape'){invalidate();$('results').replaceChildren();}
 };
 function enter(mode){if(attempt||editing){message(t('reusePending'),true);return false;}location.hash='meals';showPage('meals');$('kind').value=mode;kindChange();return true;}
 $('homeSearch').onclick=()=>{if(enter('item')){$('entryPanel').scrollIntoView({behavior:'smooth',block:'start'});$('search').focus();}};
 $('homeBarcode').onclick=()=>{if(enter('barcode'))$('barcodeButton').click();};
 $('kind').addEventListener('change',invalidate);window.addEventListener('friss-page',invalidate);window.addEventListener('friss-logout',invalidate);
 new MutationObserver(()=>{invalidate();$('homeSearch').setAttribute('aria-label',t('searchHome'));$('homeBarcode').setAttribute('aria-label',t('scanBarcode'));}).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});
 translate();
})();

// Direct manual / barcode capture gets the same last-used amount as shared search.
async function suggestLastAmount(source,id,stillSelected){
 if(editing||!id||$('amount').value)return;
 try{const data=await api('/food-amounts?source='+source+'&id='+encodeURIComponent(id));if(!editing&&!attempt&&!$('dashboard').hidden&&stillSelected()&&!$('amount').value&&data.quantity?.unit==='g')$('amount').value=data.quantity.value;}catch(e){/* A suggestion must never prevent capture. */}
}
$('manualCaptureSelect').addEventListener('change',()=>{const id=$('manualCaptureSelect').value;suggestLastAmount('manual',id,()=>$('kind').value==='manual'&&$('manualCaptureSelect').value===id);});
$('description').addEventListener('input',()=>{const code=$('description').value.trim();if($('kind').value==='barcode'&&/^\d{8,14}$/.test(code))suggestLastAmount('off',code,()=>$('kind').value==='barcode'&&$('description').value.trim()===code);});
