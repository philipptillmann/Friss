Object.assign(words.de,{backMeals:'Zurück zu Mahlzeiten',entryNutrients:'Beitrag zu den Tageswerten',captureMethod:'Erfasst über',dataSource:'Datenquelle',healthState:'Apple Health',entryQuantity:'Menge',entryStatus:'Verarbeitung',entryBarcode:'Barcode',entryId:'Eintrags-ID',detailTimeHint:'Die Änderung aktualisiert dein Tagebuch. Bereits exportierte Health-Werte bleiben unverändert; ein betroffener Tagesexport wird als geändert markiert.',entryUnknown:'Unbekannt / noch nicht berechnet',entryDetailsError:'Eintrag konnte nicht geladen werden.',detailManual:'Eigene Zutat',detailRecent:'Zuletzt benutzt',detailFavorite:'Favorit',detailPhoto:'Foto',detailSearch:'Lebensmittelsuche',detailDrink:'Getränke-Eingabe',detailText:'Text',detailRecipe:'Rezept',detailWater:'Getrunkenes Wasser',detailAlcohol:'Reiner Alkohol',detailUnitHint:'Ungeprüfte Quelleinheiten und fehlende Werte sind gekennzeichnet. Die Tabelle zeigt den Beitrag dieser Menge, keine Werte pro 100 g.'});
Object.assign(words.en,{backMeals:'Back to meals',entryNutrients:'Contribution to daily totals',captureMethod:'Captured via',dataSource:'Data source',healthState:'Apple Health',entryQuantity:'Amount',entryStatus:'Processing',entryBarcode:'Barcode',entryId:'Entry ID',detailTimeHint:'This change updates your journal. Previously exported Health values remain unchanged; any affected day export will be marked as changed.',entryUnknown:'Unknown / not calculated yet',entryDetailsError:'Could not load entry.',detailManual:'My ingredient',detailRecent:'Recently used',detailFavorite:'Favorite',detailPhoto:'Photo',detailSearch:'Food search',detailDrink:'Drink input',detailText:'Text',detailRecipe:'Recipe',detailWater:'Drinking water',detailAlcohol:'Pure alcohol',detailUnitHint:'Unverified source units and missing values are marked. This table shows the contribution of this amount, not values per 100 g.'});
let detailedEntry=null,detailGeneration=0;
function detailEntryId(){return location.hash.startsWith('#entry/')?location.hash.slice(7):null;}
function detailMetadata(label,value){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=t(label);dd.textContent=value;$('detailMetadata').append(dt,dd);}
function renderEntryDetails(setTime=false){
 const e=detailedEntry;if(!e)return;
 $('detailName').textContent=e.food?.['name_'+lang]||e.food?.product_name||e.description||e.barcode||t(e.drink||e.type);
 $('detailMetadata').replaceChildren();
 const method={manual:'detailManual',item:'detailSearch',picture:'detailPhoto',barcode:'entryBarcode',recipe:'detailRecipe',drink:'detailDrink',text:'detailText'}[e.type];
 detailMetadata('captureMethod',t(e.capture_method==='json_import'?'detailJsonImport':e.capture_method==='recent'?'detailRecent':e.capture_method==='favorite'?'detailFavorite':method||e.type));
 if(e.import_context?.title)detailMetadata('jsonMealTitle',e.import_context.title);
 if(e.import_context?.notes)detailMetadata('jsonItemNotes',e.import_context.notes);
 detailMetadata('time',new Date(e.timestamp).toLocaleString(lang));
 detailMetadata('entryQuantity',e.quantity?formatHome(e.quantity.value)+' '+t(e.quantity.unit==='portion'?'portions':e.quantity.unit==='fraction'?'fraction':e.quantity.unit):'—');
 detailMetadata('healthState',e.recipe_id?'—':t(e.health_status));
 detailMetadata('entryStatus',t(e.status));
 if(e.source?.provider)detailMetadata('dataSource',e.source.provider);
 if(e.barcode)detailMetadata('entryBarcode',e.barcode);
 detailMetadata('entryId',e.id);
 if(setTime){
 const d=new Date(e.timestamp);
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
 const generation=++detailGeneration;detailedEntry=null;
 $('detailName').textContent='…';$('detailMetadata').replaceChildren();$('detailNutrients').replaceChildren();$('detailWarnings').textContent='';$('detailTimeSave').disabled=true;$('detailDelete').disabled=true;$('detailTimeForm').hidden=true;
 try{
 const entry=await api('/entries/'+encodeURIComponent(id)+'/details');
 if(generation!==detailGeneration||currentPage!=='entry'||$('dashboard').hidden)return;
 detailedEntry=entry;$('detailTimeForm').hidden=false;renderEntryDetails(true);$('detailTimeSave').disabled=false;$('detailDelete').disabled=false;
 }catch(e){if(generation===detailGeneration){$('detailName').textContent=t('entryDetailsError');message(e.message,true);}}
}
$('detailTimeForm').onsubmit=async event=>{
 event.preventDefault();if(!detailedEntry)return;
 const id=detailedEntry.id,value=$('detailTime').value,button=$('detailTimeSave');button.disabled=true;
 try{
 const timestamp=new Date(value).toISOString();
 await api('/entries/'+id+'/time',{method:'PATCH',body:JSON.stringify({timestamp})});
 $('day').value=localDate(new Date(timestamp));
 await refresh();if(currentPage==='entry'&&detailEntryId()===id)await loadEntryDetails(id);message(t('saved'));
 }catch(e){message(e.message,true);}finally{button.disabled=!detailedEntry;}
};
$('detailDelete').onclick=async()=>{
 if(!detailedEntry)return;
 if(!confirm(t('confirmDeleteEntry')+(detailedEntry.health_status!=='pending'?'\n\n'+t('deleteHealthHint'):'')))return;
 const id=detailedEntry.id;$('detailDelete').disabled=true;
 try{const result=await api('/entries/'+id,{method:'DELETE'});detailGeneration++;detailedEntry=null;location.hash='meals';await refresh();message(t(result.health_correction_required?'deleteHealthNotice':'deleted'));}
 catch(e){message(e.message,true);$('detailDelete').disabled=false;}
};
window.addEventListener('friss-logout',()=>{detailGeneration++;detailedEntry=null;$('detailName').textContent='';$('detailMetadata').replaceChildren();$('detailNutrients').replaceChildren();$('detailWarnings').textContent='';$('detailTimeForm').reset();});
window.addEventListener('friss-data-updated',()=>{if(currentPage==='entry'&&detailEntryId()&&!detailedEntry)loadEntryDetails(detailEntryId());});
new MutationObserver(()=>renderEntryDetails(false)).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});
translate();
if(currentPage==='entry'&&!$('dashboard').hidden)loadEntryDetails(detailEntryId());
