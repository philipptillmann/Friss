Object.assign(words.de,{originalPhotos:'Originalfotos'});Object.assign(words.en,{originalPhotos:'Original photos'});
Object.assign(words.de,{backRecipe:'Zurück zum Rezept',backDrink:'Zurück zum Getränk',ingredientNutrients:'Nährwerte dieser Zutat im Rezept',detailAmountHint:'Ändert die Menge und berechnet den Beitrag neu. Gespeicherte Rezeptmahlzeiten bleiben unverändert. Bereits exportierte Health-Werte müssen dort separat korrigiert werden.',detailOriginalMessage:'Ursprüngliche Beschreibung'});
Object.assign(words.en,{backRecipe:'Back to recipe',backDrink:'Back to drink',ingredientNutrients:'This ingredient’s contribution to the recipe',detailAmountHint:'Changes the amount and recalculates its contribution. Previously logged recipe meals stay unchanged. Previously exported Health values must be corrected there separately.',detailOriginalMessage:'Original description'});
Object.assign(words.de,{backMeals:'Zurück zu Mahlzeiten',entryNutrients:'Beitrag zu den Tageswerten',captureMethod:'Erfasst über',dataSource:'Datenquelle',healthState:'Apple Health',entryQuantity:'Menge',entryStatus:'Verarbeitung',entryBarcode:'Barcode',entryId:'Eintrags-ID',detailTimeHint:'Die Änderung aktualisiert dein Tagebuch. Bereits exportierte Health-Werte bleiben unverändert; ein betroffener Tagesexport wird als geändert markiert.',entryUnknown:'Unbekannt / noch nicht berechnet',entryDetailsError:'Eintrag konnte nicht geladen werden.',detailManual:'Eigene Zutat',detailRecent:'Zuletzt benutzt',detailFavorite:'Favorit',detailPhoto:'Foto',detailSearch:'Lebensmittelsuche',detailDrink:'Getränke-Eingabe',detailText:'Text',detailRecipe:'Rezept',detailWater:'Getrunkenes Wasser',detailAlcohol:'Reiner Alkohol',detailUnitHint:'Ungeprüfte Quelleinheiten und fehlende Werte sind gekennzeichnet. Die Tabelle zeigt den Beitrag dieser Menge, keine Werte pro 100 g.'});
Object.assign(words.en,{backMeals:'Back to meals',entryNutrients:'Contribution to daily totals',captureMethod:'Captured via',dataSource:'Data source',healthState:'Apple Health',entryQuantity:'Amount',entryStatus:'Processing',entryBarcode:'Barcode',entryId:'Entry ID',detailTimeHint:'This change updates your journal. Previously exported Health values remain unchanged; any affected day export will be marked as changed.',entryUnknown:'Unknown / not calculated yet',entryDetailsError:'Could not load entry.',detailManual:'My ingredient',detailRecent:'Recently used',detailFavorite:'Favorite',detailPhoto:'Photo',detailSearch:'Food search',detailDrink:'Drink input',detailText:'Text',detailRecipe:'Recipe',detailWater:'Drinking water',detailAlcohol:'Pure alcohol',detailUnitHint:'Unverified source units and missing values are marked. This table shows the contribution of this amount, not values per 100 g.'});
Object.assign(words.de,{copyEntry:'Eintrag kopieren',copyEntryTime:'Neuer Zeitpunkt',copyEntryHint:'Erstellt einen neuen Tagebucheintrag mit derselben Menge und denselben Nährwerten. Health-Export beginnt neu.',copyEntryRetry:'Übertragung unklar. Erneut kopieren wiederholt denselben Vorgang ohne doppelte Einträge.',copyEntrySource:'Kopiert von'});
Object.assign(words.en,{copyEntry:'Copy entry',copyEntryTime:'New date and time',copyEntryHint:'Creates a new diary entry with the same amount and nutritional values. Health export starts afresh.',copyEntryRetry:'Transfer uncertain. Copy again to retry the same request without duplicates.',copyEntrySource:'Copied from'});
let detailedEntry=null,detailGeneration=0,detailCopyAttempt=null,detailCopyBusy=false;
function detailEntryId(){return location.hash.startsWith('#entry/')?location.hash.slice(7):null;}
function detailMetadata(label,value){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=t(label);dd.textContent=value;$('detailMetadata').append(dt,dd);}
function renderEntryDetails(setTime=false){
 const e=detailedEntry;if(!e)return;
 $('detailResolve').hidden=e.status==='processed'||e.health_status!=='pending'||e.type==='recipe';
 $('detailName').textContent=e.food?.['name_'+lang]||e.food?.product_name||e.description||e.barcode||t(e.drink||e.type);
 $('detailPhotos').hidden=!e.photos?.length;$('detailPhotoList').replaceChildren();
 for(const [index,photo] of (e.photos||[]).entries()){const link=document.createElement('a');link.href=photo.url;link.target='_blank';link.rel='noopener';const img=document.createElement('img');img.src=photo.url;img.alt=t('originalPhotos')+' '+(index+1);img.loading='lazy';link.append(img);$('detailPhotoList').append(link);}
 $('detailMetadata').replaceChildren();
 const method={manual:'detailManual',item:'detailSearch',picture:'detailPhoto',barcode:'entryBarcode',recipe:'detailRecipe',drink:'detailDrink',text:'detailText'}[e.type];
 detailMetadata('captureMethod',t(e.capture_method==='json_import'?'detailJsonImport':e.capture_method==='recent'?'detailRecent':e.capture_method==='favorite'?'detailFavorite':method||e.type));
 if(e.import_context?.title)detailMetadata('jsonMealTitle',e.import_context.title);
 if(e.import_context?.notes)detailMetadata('jsonItemNotes',e.import_context.notes);
 if(e.finished_at){detailMetadata('drinkFinish',new Date(e.finished_at).toLocaleString(lang));const hours=(Date.parse(e.finished_at)-Date.parse(e.timestamp))/3600000;if(hours>0&&e.ethanol_g>0)detailMetadata('drinkSpeed',formatHome(e.ethanol_g/hours)+' g/h');}
 detailMetadata('time',new Date(e.timestamp).toLocaleString(lang));
 detailMetadata('entryQuantity',e.quantity?formatHome(e.quantity.value)+' '+t(e.quantity.unit==='portion'?'portions':e.quantity.unit==='fraction'?'fraction':e.quantity.unit):'—');
 if(!e.recipe_id)detailMetadata('healthState',t(e.health_status));
 const category=recipeRows.find(r=>r.id===e.recipe_id)?.category;
 $('detailBack').href=e.recipe_id?(category==='drink'?'#alcohol':'#recipes'):'#meals';$('detailBack').textContent=t(e.recipe_id?(category==='drink'?'backDrink':'backRecipe'):'backMeals');
 $('detailBack').removeAttribute('data-i');
 $('detailNutrientsTitle').textContent=t(e.recipe_id?'ingredientNutrients':'entryNutrients');
 if(e.import_context?.original_message)detailMetadata('detailOriginalMessage',e.import_context.original_message);
 detailMetadata('entryStatus',t(e.status));
 if(e.source?.provider)detailMetadata('dataSource',e.source.provider);
 if(e.copied_from)detailMetadata('copyEntrySource',new Date(e.copied_from.timestamp).toLocaleString(lang));
 if(e.barcode)detailMetadata('entryBarcode',e.barcode);
 detailMetadata('entryId',e.id);
 if(setTime){
 const d=new Date(e.timestamp);
 $('detailAmount').value=e.quantity?.value??'';$('detailAmountUnit').replaceChildren();
 for(const unit of e.quantity?[e.quantity.unit]:['g','ml']){const o=document.createElement('option');o.value=unit;o.textContent=t(unit==='portion'?'portions':unit==='fraction'?'fraction':unit);$('detailAmountUnit').append(o);}
 $('detailAmountUnit').value=e.quantity?.unit||'g';$('detailAmount').max=e.quantity?.unit==='fraction'?'1':'';
 $('detailAmountForm').hidden=e.health_status==='claimed';$('detailAmountSave').disabled=e.health_status==='claimed';
 const finish=e.finished_at?new Date(e.finished_at):null;$('detailFinish').value=finish?new Date(finish-finish.getTimezoneOffset()*60000).toISOString().slice(0,19):'';
 $('detailTime').value=localDate(d)+'T'+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')+':'+String(d.getSeconds()).padStart(2,'0');
 }
 $('detailHealthHint').textContent=t('detailTimeHint');
 $('detailNutrients').replaceChildren();
 for(const [key,n] of Object.entries(e.contributions||{}).sort(([a],[b])=>a.localeCompare(b))){
 const text=n.value==null?(n.qualifier==null?t('entryUnknown'):String(n.qualifier)):formatHome(n.value)+' '+(n.unit==='mcg'?'µg':n.unit||t('sourceUnits'));
 tableRow($('detailNutrients'),nutrientLabel(key),text);
 }
 if(e.drinking_water_ml!=null)tableRow($('detailNutrients'),t('detailWater'),formatHome(e.drinking_water_ml)+' ml');
 if(e.ethanol_g!=null)tableRow($('detailNutrients'),t('detailAlcohol'),formatHome(e.ethanol_g)+' g');
 if(!$('detailNutrients').children.length)tableRow($('detailNutrients'),t('entryNutrients'),t('entryUnknown'));
 $('detailWarnings').textContent=[t('detailUnitHint'),e.reason,...(e.warnings||[])].filter(Boolean).join(' ');
}
async function loadEntryDetails(id){
 const generation=++detailGeneration;detailedEntry=null;detailCopyAttempt=null;$('detailCopyForm').hidden=true;$('detailPhotos').hidden=true;$('detailPhotoList').replaceChildren();
 $('detailName').textContent='…';$('detailMetadata').replaceChildren();$('detailNutrients').replaceChildren();$('detailWarnings').textContent='';$('detailTimeSave').disabled=true;$('detailDelete').disabled=true;$('detailTimeForm').hidden=true;$('detailAmountForm').hidden=true;$('detailResolve').hidden=true;
 try{
 const entry=await api('/entries/'+encodeURIComponent(id)+'/details');
 if(generation!==detailGeneration||currentPage!=='entry'||$('dashboard').hidden)return;
 detailedEntry=entry;if(entry.recipe_id)activeRecipe=entry.recipe_id;$('detailCopyForm').hidden=!!entry.recipe_id;$('detailCopyTime').disabled=false;$('detailCopySave').disabled=false;const now=new Date();$('detailCopyTime').value=localDate(now)+'T'+String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0')+':'+String(now.getSeconds()).padStart(2,'0');$('detailTimeForm').hidden=false;renderEntryDetails(true);$('detailTimeSave').disabled=false;$('detailDelete').disabled=false;
 }catch(e){if(generation===detailGeneration){$('detailName').textContent=t('entryDetailsError');message(e.message,true);}}
}
$('detailResolve').onclick=()=>{if(!detailedEntry)return;const e=detailedEntry,back=$('detailBack').getAttribute('href').slice(1);location.hash=back;showPage(back);resumeEntry(e);};
$('detailAmountForm').onsubmit=async event=>{
 event.preventDefault();if(!detailedEntry)return;
 const id=detailedEntry.id,button=$('detailAmountSave');button.disabled=true;
 try{await api('/entries/'+id+'/amount',{method:'PATCH',body:JSON.stringify({quantity:{value:Number($('detailAmount').value),unit:$('detailAmountUnit').value},revision:detailedEntry.revision})});await refresh();if(currentPage==='entry'&&detailEntryId()===id)await loadEntryDetails(id);message(t('saved'));}
 catch(e){message(e.message,true);}finally{button.disabled=!detailedEntry;}
};
$('detailTimeForm').onsubmit=async event=>{
 event.preventDefault();if(!detailedEntry)return;
 const id=detailedEntry.id,value=$('detailTime').value,button=$('detailTimeSave');button.disabled=true;
 try{
 const timestamp=new Date(value).toISOString();
 await api('/entries/'+id+'/time',{method:'PATCH',body:JSON.stringify({timestamp,finished_at:$('detailFinish').value?new Date($('detailFinish').value).toISOString():null})});
 $('day').value=localDate(new Date(timestamp));
 await refresh();if(currentPage==='entry'&&detailEntryId()===id)await loadEntryDetails(id);message(t('saved'));
 }catch(e){message(e.message,true);}finally{button.disabled=!detailedEntry;}
};
$('detailCopyForm').onsubmit=async event=>{
 event.preventDefault();if(!detailedEntry||detailCopyBusy)return;
 if(!detailCopyAttempt)detailCopyAttempt={source:detailedEntry.id,id:uuid(),timestamp:new Date($('detailCopyTime').value).toISOString()};
 const attempt=detailCopyAttempt,generation=detailGeneration;detailCopyBusy=true;$('detailCopySave').disabled=true;$('detailCopyTime').disabled=true;
 try{
 const result=await api('/entries/'+attempt.source+'/copy',{method:'POST',body:JSON.stringify({id:attempt.id,timestamp:attempt.timestamp})});
 if(generation!==detailGeneration||$('dashboard').hidden)return;
 detailCopyAttempt=null;$('day').value=localDate(new Date(attempt.timestamp));location.hash='entry/'+result.id;await refresh();message(t('saved'));
 }catch(e){if(generation===detailGeneration){if([400,404,409,422].includes(e.status)){detailCopyAttempt=null;$('detailCopyTime').disabled=false;message(e.message,true);}else message(t('copyEntryRetry')+' '+e.message,true);}}
 finally{detailCopyBusy=false;if(generation===detailGeneration)$('detailCopySave').disabled=false;}
};
$('detailDelete').onclick=async()=>{
 if(!detailedEntry)return;
 if(!confirm(t('confirmDeleteEntry')+(detailedEntry.health_status!=='pending'?'\n\n'+t('deleteHealthHint'):'')))return;
 const id=detailedEntry.id,back=$('detailBack').getAttribute('href');$('detailDelete').disabled=true;
 try{const result=await api('/entries/'+id,{method:'DELETE'});detailGeneration++;detailedEntry=null;location.hash=back;await refresh();message(t(result.health_correction_required?'deleteHealthNotice':'deleted'));}
 catch(e){message(e.message,true);$('detailDelete').disabled=false;}
};
window.addEventListener('friss-logout',()=>{detailGeneration++;detailCopyAttempt=null;detailedEntry=null;$('detailPhotos').hidden=true;$('detailPhotoList').replaceChildren();$('detailCopyForm').hidden=true;$('detailCopyForm').reset();$('detailName').textContent='';$('detailMetadata').replaceChildren();$('detailNutrients').replaceChildren();$('detailWarnings').textContent='';$('detailTimeForm').reset();$('detailAmountForm').reset();$('detailAmountForm').hidden=true;});
window.addEventListener('friss-data-updated',()=>{if(currentPage==='entry'&&detailEntryId()&&!detailedEntry)loadEntryDetails(detailEntryId());});
new MutationObserver(()=>renderEntryDetails(false)).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});
translate();
if(currentPage==='entry'&&!$('dashboard').hidden)loadEntryDetails(detailEntryId());

