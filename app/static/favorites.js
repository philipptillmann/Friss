Object.assign(words.de,{favorites:'Favoriten',recentIngredients:'Zuletzt benutzt',filterIngredients:'Lebensmittel filtern',reuseHint:'Auswählen, Menge und Zeitpunkt prüfen, dann speichern. Die letzten 100 unterschiedlichen Lebensmittel aus Tagebuch und Rezeptzutaten.',manageFavorites:'Favoriten verwalten',favoriteHint:'Vorlagen mit Vorschlagsmengen verwalten. Ändern oder Löschen verändert keine bereits gebuchten Mahlzeiten.',newFavorite:'Neuer Favorit',editFavorite:'Favorit bearbeiten',fromRecent:'Aus zuletzt benutzten übernehmen',noRecent:'Noch keine wiederverwendbaren Lebensmittel.',noFavorites:'Noch keine Favoriten. Auf der Favoritenseite hinzufügen.',useIngredient:'Verwenden',edit:'Bearbeiten',confirmDeleteFavorite:'Diesen Favoriten wirklich löschen? Bereits gebuchte Einträge bleiben erhalten.',reusePending:'Bitte den ausstehenden Eintrag zuerst speichern oder abbrechen.',recipeIngredient:'Rezeptzutat',dailyIngredient:'Tagebuch',favoriteChosen:'Übernommen. Menge und Zeitpunkt prüfen und speichern.',reusableLoadError:'Zuletzt benutzt / Favoriten konnten nicht geladen werden.'});
Object.assign(words.en,{favorites:'Favorites',recentIngredients:'Recently used',filterIngredients:'Filter foods',reuseHint:'Select, check the amount and time, then save. The last 100 distinct foods from the journal and recipe ingredients.',manageFavorites:'Manage favorites',favoriteHint:'Manage templates with suggested amounts. Editing or deleting does not change logged meals.',newFavorite:'New favorite',editFavorite:'Edit favorite',fromRecent:'Use a recently used ingredient',noRecent:'No reusable ingredients yet.',noFavorites:'No favorites yet. Add them on the Favorites page.',useIngredient:'Use',edit:'Edit',confirmDeleteFavorite:'Really delete this favorite? Logged entries will be kept.',reusePending:'Please save or cancel the pending entry first.',recipeIngredient:'Recipe ingredient',dailyIngredient:'Journal',favoriteChosen:'Filled in. Check the amount and time, then save.',reusableLoadError:'Could not load recently used foods / favorites.'});
let recentIngredients=[],favoriteItems=[],reuseMode=null,reuseGeneration=0,favoriteEditing=null,favoriteDraft=null,favoriteSearchGeneration=0;
function reusableName(item){return item.label||item['name_'+lang]||item.entry.description||item.entry.barcode||t(item.entry.drink)||'—';}
function reusableAmount(item){const q=item.entry.quantity;return q?q.value+' '+q.unit:'—';}
async function loadReusable(){
 const generation=++reuseGeneration;
 try{
 const [recent,favorites]=await Promise.all([api('/recent-ingredients'),api('/favorites')]);
 if(generation!==reuseGeneration||$('dashboard').hidden)return;
 recentIngredients=recent;favoriteItems=favorites;renderReusable();
 }catch(e){if(generation===reuseGeneration){recentIngredients=[];favoriteItems=[];renderReusable();message(t('reusableLoadError')+' '+e.message,true);}}
}
function renderReusable(){
 $('reusePanel').hidden=!reuseMode;
 $('recentToggle').setAttribute('aria-expanded',String(reuseMode==='recent'));
 $('favoriteToggle').setAttribute('aria-expanded',String(reuseMode==='favorites'));
 $('reuseList').replaceChildren();
 const source=reuseMode==='favorites'?favoriteItems:recentIngredients;
 const q=$('reuseSearch').value.trim().toLocaleLowerCase();
 for(const item of source.filter(i=>(reusableName(i)+' '+(i.entry.barcode||'')).toLocaleLowerCase().includes(q))){
 const b=document.createElement('button');b.type='button';b.className='reuseChoice';
 const title=document.createElement('strong');title.textContent=reusableName(item);const meta=document.createElement('small');meta.textContent=reusableAmount(item)+(item.last_location?' · '+t(item.last_location==='recipe'?'recipeIngredient':'dailyIngredient'):'');
 b.append(title,meta);b.onclick=()=>useReusable(item);$('reuseList').append(b);
 }
 if(!$('reuseList').children.length)$('reuseList').textContent=t(reuseMode==='favorites'?'noFavorites':'noRecent');
 $('favoriteList').replaceChildren();
 if(!favoriteItems.length)$('favoriteList').textContent=t('noFavorites');
 for(const favorite of favoriteItems){
 const row=document.createElement('div');row.className='favoriteRow';const title=document.createElement('strong');title.textContent=favorite.label+' · '+reusableAmount(favorite);
 const actions=document.createElement('div');actions.className='bacActions';
 for(const [label,handler] of [['useIngredient',()=>useReusable(favorite)],['edit',()=>editFavorite(favorite)],['deleteEntry',()=>deleteFavorite(favorite)]]){
 const b=document.createElement('button');b.type='button';b.textContent=t(label);b.onclick=handler;actions.append(b);
 }
 row.append(title,actions);$('favoriteList').append(row);
 }
 const selectedRecent=$('favoriteRecent').value;$('favoriteRecent').replaceChildren();const blank=document.createElement('option');blank.value='';blank.textContent='—';$('favoriteRecent').append(blank);
 recentIngredients.forEach((r,i)=>{const o=document.createElement('option');o.value=String(i);o.textContent=reusableName(r);$('favoriteRecent').append(o);});$('favoriteRecent').value=selectedRecent;
}
function useReusable(item){
 if(attempt||editing){message(t('reusePending'),true);return;}
 if(currentPage!=='recipes'&&currentPage!=='meals'){location.hash='meals';showPage('meals');}
 const e=item.entry,kind=e.type==='drink'?e.drink:e.type;
 $('kind').value=kind;$('alcoholEntryMode').value=kind==='alcohol'&&e.quantity?.unit==='g'?'g':'ml';kindChange();if(kind==='manual'){ensureManualOption('manualCaptureSelect',e.manual_id,reusableName(item));updateManualCaptureInfo();}reusedVia=item.id?'favorite':'recent';
 if(kind==='item'){selected={bls_code:e.bls_code,display_name:reusableName(item)};$('selected').textContent=reusableName(item);$('search').value=reusableName(item);}
 if(kind==='barcode')$('description').value=e.barcode;
 if(kind==='text')$('description').value=e.description;
 $('amount').value=e.quantity?.value??'';
 if(kind==='coffee')$('caffeineInput').value=e.caffeine_mg??'';
 if(kind==='alcohol')$('abv').value=e.alcohol_abv??'';
 reuseMode=null;renderReusable();$('amount').focus();message(t('favoriteChosen'));
}
$('recentToggle').onclick=()=>{reuseMode=reuseMode==='recent'?null:'recent';renderReusable();if(reuseMode)loadReusable();};
$('favoriteToggle').onclick=()=>{reuseMode=reuseMode==='favorites'?null:'favorites';renderReusable();if(reuseMode)loadReusable();};
$('reuseSearch').oninput=renderReusable;
function favoriteFields(){
 const kind=$('favoriteKind').value,drink=['water','coffee','alcohol'].includes(kind);
 $('favoriteManualGroup').hidden=kind!=='manual';$('favoriteManual').required=kind==='manual';$('favoriteManual').disabled=kind!=='manual';
 $('favoriteFoodGroup').hidden=kind!=='item';$('favoriteCode').required=kind==='item';$('favoriteCode').disabled=kind!=='item';$('favoriteFoodSearch').disabled=kind!=='item';
 $('favoriteDescriptionGroup').hidden=!['barcode','text'].includes(kind);$('favoriteDescription').required=['barcode','text'].includes(kind);$('favoriteDescription').disabled=!['barcode','text'].includes(kind);
 $('favoriteCaffeineGroup').hidden=kind!=='coffee';$('favoriteCaffeine').required=kind==='coffee';$('favoriteCaffeine').disabled=kind!=='coffee';
 $('favoriteAlcoholModeGroup').hidden=kind!=='alcohol';const direct=kind==='alcohol'&&$('favoriteAlcoholMode').value==='g';$('favoriteAlcoholGroup').hidden=kind!=='alcohol'||direct;$('favoriteAlcohol').required=kind==='alcohol'&&!direct;$('favoriteAlcohol').disabled=kind!=='alcohol'||direct;
 $('favoriteAmount').required=drink;$('favoriteAmountLabel').textContent=t(direct?'alcoholGrams':drink?'volume':'amount');
}
function editFavorite(item=null){
 favoriteSearchGeneration++;favoriteEditing=item?.id?item:null;favoriteDraft=null;
 $('favoriteForm').reset();$('favoriteFoodResults').replaceChildren();$('favoriteRecent').value='';
 const entry=item?.entry;$('favoriteEditorTitle').textContent=t(favoriteEditing?'editFavorite':'newFavorite');
 $('favoriteLabel').value=item?reusableName(item):'';
 $('favoriteKind').value=entry?.type==='drink'?entry.drink:entry?.type||'item';
 if(entry?.type==='manual')ensureManualOption('favoriteManual',entry.manual_id,reusableName(item));else $('favoriteManual').value='';$('favoriteCode').value=entry?.bls_code||'';$('favoriteDescription').value=entry?.barcode||entry?.description||'';
 $('favoriteAlcoholMode').value=entry?.drink==='alcohol'&&entry.quantity?.unit==='g'?'g':'ml';$('favoriteAmount').value=entry?.quantity?.value??'';$('favoriteCaffeine').value=entry?.caffeine_mg??'';$('favoriteAlcohol').value=entry?.alcohol_abv??'';
 favoriteFields();$('favoriteLabel').focus();
}
$('newFavorite').onclick=()=>editFavorite();
$('cancelFavorite').onclick=()=>editFavorite();
$('favoriteKind').onchange=()=>{favoriteSearchGeneration++;favoriteFields();};
$('favoriteRecent').onchange=()=>{const r=recentIngredients[Number($('favoriteRecent').value)];if($('favoriteRecent').value&&r)editFavorite(r);};
$('favoriteFoodSearch').oninput=async()=>{
 const generation=++favoriteSearchGeneration;const q=$('favoriteFoodSearch').value.trim(),searchLang=lang;$('favoriteFoodResults').replaceChildren();$('favoriteCode').value='';
 if(!q)return;
 try{
 const foods=await api('/foods?q='+encodeURIComponent(q)+'&lang='+searchLang);
 if(generation!==favoriteSearchGeneration||searchLang!==lang||$('dashboard').hidden||$('favoriteKind').value!=='item')return;
 for(const food of foods){
 const b=document.createElement('button');b.type='button';b.className='result';b.textContent=food.display_name;
 b.onclick=()=>{rememberFoodSelection(q,food.bls_code,searchLang);$('favoriteCode').value=food.bls_code;$('favoriteFoodSearch').value=food.display_name;if(!$('favoriteLabel').value)$('favoriteLabel').value=food.display_name;$('favoriteFoodResults').replaceChildren();};$('favoriteFoodResults').append(b);
 }
 if(!foods.length)$('favoriteFoodResults').textContent=t('none');
 }catch(e){if(generation===favoriteSearchGeneration)message(e.message,true);}
};
$('favoriteForm').onsubmit=async event=>{
 event.preventDefault();const button=event.submitter;button.disabled=true;
 const kind=$('favoriteKind').value,drink=['water','coffee','alcohol'].includes(kind);
 const entry={type:drink?'drink':kind,quantity:$('favoriteAmount').value?{value:Number($('favoriteAmount').value),unit:drink?kind==='alcohol'&&$('favoriteAlcoholMode').value==='g'?'g':'ml':'g'}:null};
 if(kind==='manual')entry.manual_id=$('favoriteManual').value;
 if(kind==='item')entry.bls_code=$('favoriteCode').value.trim();
 if(kind==='barcode')entry.barcode=$('favoriteDescription').value.trim();
 if(kind==='text')entry.description=$('favoriteDescription').value;
 if(drink)entry.drink=kind;
 if(kind==='coffee')entry.caffeine_mg=Number($('favoriteCaffeine').value);
 if(kind==='alcohol'&&$('favoriteAlcoholMode').value!=='g')entry.alcohol_abv=Number($('favoriteAlcohol').value);
 const body={label:$('favoriteLabel').value.trim(),entry,version:favoriteEditing?.version??0};
 try{
 if(favoriteEditing)await api('/favorites/'+favoriteEditing.id,{method:'PUT',body:JSON.stringify(body)});
 else{favoriteDraft??=uuid();await api('/favorites',{method:'POST',body:JSON.stringify({id:favoriteDraft,...body})});}
 editFavorite();await loadReusable();message(t('saved'));
 }catch(e){message(e.message,true);}finally{button.disabled=false;}
};
async function deleteFavorite(favorite){
 if(!confirm(t('confirmDeleteFavorite')))return;
 try{await api('/favorites/'+favorite.id+'?version='+favorite.version,{method:'DELETE'});if(favoriteEditing?.id===favorite.id)editFavorite();await loadReusable();message(t('deleted'));}
 catch(e){message(e.message,true);}
}
window.addEventListener('friss-data-updated',()=>{if(['meals','recipes','favorites'].includes(currentPage))loadReusable();});
window.addEventListener('friss-page',()=>{if(['meals','recipes','favorites'].includes(currentPage)&&!$('dashboard').hidden)loadReusable();});
window.addEventListener('friss-logout',()=>{reuseGeneration++;favoriteSearchGeneration++;recentIngredients=[];favoriteItems=[];reuseMode=null;favoriteEditing=null;favoriteDraft=null;$('reuseSearch').value='';$('favoriteForm').reset();$('favoriteFoodResults').replaceChildren();renderReusable();favoriteFields();});
new MutationObserver(()=>{renderReusable();favoriteFields();$('favoriteEditorTitle').textContent=t(favoriteEditing?'editFavorite':'newFavorite');}).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});
favoriteFields();translate();
if(!$('dashboard').hidden&&['meals','recipes','favorites'].includes(currentPage))loadReusable();

$('favoriteAlcoholMode').onchange=favoriteFields;
