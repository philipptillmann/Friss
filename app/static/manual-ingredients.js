Object.assign(words.de,{manualIngredients:'Eigene Zutaten',chooseManual:'Eigene Zutat auswählen',manageManual:'Eigene Zutaten verwalten',manualIntro:'Eigene Lebensmittel mit Nährwerten pro 100 g speichern und in Mahlzeiten oder Rezepten verwenden.',newManual:'Neue Zutat',editManual:'Zutat bearbeiten',manualNameDe:'Name (Deutsch)',manualNameEn:'Name (Englisch)',per100g:'Nährwerte pro 100 g',manualValuesHint:'Nur bekannte Werte eintragen. Leer bleibt unbekannt; 0 bedeutet einen bekannten Nullwert. Energie wird nicht aus Makros geschätzt. Änderungen gelten für künftig hinzugefügte Einträge.',manualAlcohol:'Reiner Alkohol (g pro 100 g)',noManual:'Noch keine eigenen Zutaten angelegt.',confirmDeleteManual:'Eigene Zutat wirklich löschen? Bereits gespeicherte Mahlzeiten und Rezeptzutaten behalten ihre Nährwerte.',manualSnapshot:'Gespeicherter Stand der Zutat',manualNeedNutrient:'Bitte mindestens einen Nährwert eintragen.',manualLoadError:'Eigene Zutaten konnten nicht geladen werden.'});
Object.assign(words.en,{manualIngredients:'My ingredients',chooseManual:'Choose my ingredient',manageManual:'Manage my ingredients',manualIntro:'Save your own foods with nutrients per 100 g, then use them in meals or recipes.',newManual:'New ingredient',editManual:'Edit ingredient',manualNameDe:'Name (German)',manualNameEn:'Name (English)',per100g:'Nutrients per 100 g',manualValuesHint:'Enter known values only. Empty means unknown; 0 means a known zero. Energy is not estimated from macros. Changes apply to future entries.',manualAlcohol:'Pure alcohol (g per 100 g)',noManual:'No ingredients added yet.',confirmDeleteManual:'Really delete this ingredient? Logged meals and recipe ingredients will retain their values.',manualSnapshot:'Recorded ingredient version',manualNeedNutrient:'Please enter at least one nutrient.',manualLoadError:'Could not load your ingredients.'});
let manualItems=[],manualSchema=[],manualEditing=null,manualDraft=null,manualGeneration=0,manualRestoredEntry=null,manualFieldsReady=false,manualImportGeneration=0,manualSource=null,manualImportPending=false;
function manualName(item){return item['name_'+lang]||item.name_de;}
function renderManualChoices(){
 for(const id of ['manualCaptureSelect','favoriteManual']){
 const select=$(id),chosen=select.value;select.replaceChildren();const blank=document.createElement('option');blank.value='';blank.textContent='—';select.append(blank);
 for(const item of manualItems){const o=document.createElement('option');o.value=item.id;o.textContent=manualName(item);select.append(o);}
 if(id==='manualCaptureSelect'&&editing&&manualRestoredEntry?.id===editing&&!manualItems.some(i=>i.id===manualRestoredEntry.manual_id)){
 const o=document.createElement('option');o.value=manualRestoredEntry.manual_id;o.textContent=manualName(manualRestoredEntry.manual_snapshot)+' · '+t('manualSnapshot');select.append(o);
 }
 select.value=chosen;
 }
 if(editing&&manualRestoredEntry?.id===editing){$('manualCaptureSelect').value=manualRestoredEntry.manual_id;$('manualCaptureSelect').disabled=true;}
 updateManualCaptureInfo();
}
function ensureManualOption(selectId,id,label){
 const select=$(selectId);
 if(id&&!Array.from(select.options).some(o=>o.value===id)){const option=document.createElement('option');option.value=id;option.textContent=label;select.append(option);}
 select.value=id||'';
}
function updateManualCaptureInfo(){
 const id=$('manualCaptureSelect').value;
 const item=editing&&manualRestoredEntry?.id===editing?manualRestoredEntry.manual_snapshot:manualItems.find(i=>i.id===id);
 $('manualCaptureInfo').textContent=item?(editing?t('manualSnapshot')+' · ':'')+t('per100g')+' · '+Object.keys(item.nutrients).length:'';
}
function restoreManualSelection(entry){
 manualRestoredEntry=entry;renderManualChoices();$('manualCaptureSelect').value=entry.manual_id;updateManualCaptureInfo();
}
function buildManualFields(){
 if(manualFieldsReady)return;
 $('manualNutrientFields').replaceChildren();
 const ordered=manualSchema.slice().sort((a,b)=>{
 const aa=standardKeys.indexOf(a.key),bb=standardKeys.indexOf(b.key);
 return (aa<0?100:aa)-(bb<0?100:bb)||a.key.localeCompare(b.key);
 });
 for(const field of ordered){
 const row=document.createElement('div');row.className='manualNutrient';
 const label=document.createElement('label');label.htmlFor='manualValue-'+field.key;label.dataset.manualNutrient=field.key;label.textContent=nutrientLabel(field.key);
 const input=document.createElement('input');input.id=label.htmlFor;input.type='number';input.min='0';input.step='any';
 const unit=document.createElement('select');unit.id='manualUnit-'+field.key;unit.setAttribute('aria-label',nutrientLabel(field.key)+' · unit');
 for(const name of field.units){const option=document.createElement('option');option.value=name;option.textContent=name==='mcg'?'µg':name;unit.append(option);}unit.value=field.unit;
 row.append(label,input,unit);$('manualNutrientFields').append(row);
 }
 manualFieldsReady=true;
}
function renderManualList(){
 $('manualList').replaceChildren();const query=$('manualFilter').value.trim().toLocaleLowerCase();
 const filtered=manualItems.filter(i=>(i.name_de+' '+i.name_en).toLocaleLowerCase().includes(query));
 if(!filtered.length)$('manualList').textContent=t('noManual');
 for(const item of filtered){
 const row=document.createElement('div');row.className='favoriteRow';const title=document.createElement('strong');title.textContent=manualName(item);
 const info=document.createElement('p');const energy=item.nutrients.dietaryEnergyConsumed;info.className='note';info.textContent=t('per100g')+(energy?' · '+formatHome(energy.value)+' kcal':'');
 const actions=document.createElement('div');actions.className='bacActions';
 const edit=document.createElement('button');edit.type='button';edit.textContent=t('edit');edit.onclick=()=>editManual(item);
 const remove=document.createElement('button');remove.type='button';remove.className='danger';remove.textContent=t('deleteEntry');remove.onclick=()=>deleteManual(item);
 row.append(title,info);actions.append(edit,remove);row.append(actions);$('manualList').append(row);
 }
}
async function loadManualIngredients(){
 const generation=++manualGeneration;
 try{
 const [items,schema]=await Promise.all([api('/manual-ingredients'),api('/manual-ingredients/schema')]);
 if(generation!==manualGeneration||$('dashboard').hidden)return;
 manualItems=items;manualSchema=schema;buildManualFields();renderManualList();renderManualChoices();$('manualSave').disabled=false;$('manualImportButton').disabled=manualImportPending;
 }catch(e){if(generation===manualGeneration)message(t('manualLoadError')+' '+e.message,true);}
}
function editManual(item=null){
 manualImportGeneration++;manualSource=item?.source||null;
 manualEditing=item;manualDraft=null;$('manualForm').reset();$('manualEditorTitle').textContent=t(item?'editManual':'newManual');
 $('manualNameDe').value=item?.name_de||'';$('manualNameEn').value=item?.name_en||'';$('manualNotes').value=item?.notes||'';$('manualEthanol').value=item?.ethanol_g_per100??'';
 for(const field of manualSchema){$('manualValue-'+field.key).value=item?.nutrients[field.key]?.value??'';$('manualUnit-'+field.key).value=item?.nutrients[field.key]?.unit||field.unit;}
 $('manualNameDe').focus();
}
$('manualForm').onsubmit=async event=>{
 event.preventDefault();if(!manualFieldsReady)return;const button=$('manualSave');button.disabled=true;
 try{
 const nutrients={};for(const field of manualSchema){const input=$('manualValue-'+field.key);if(input.value!=='')nutrients[field.key]={value:Number(input.value),unit:$('manualUnit-'+field.key).value};}
 const alcohol=$('manualEthanol').value;if(!Object.keys(nutrients).length&&alcohol==='')throw Error(t('manualNeedNutrient'));
 const body={name_de:$('manualNameDe').value.trim(),name_en:$('manualNameEn').value.trim(),notes:$('manualNotes').value,nutrients,ethanol_g_per100:alcohol===''?null:Number(alcohol),version:manualEditing?.version??0,source:manualSource};
 if(manualEditing)await api('/manual-ingredients/'+manualEditing.id,{method:'PUT',body:JSON.stringify(body)});
 else{manualDraft??=uuid();await api('/manual-ingredients',{method:'POST',body:JSON.stringify({id:manualDraft,...body})});}
 editManual();await loadManualIngredients();message(t('saved'));
 }catch(e){message(e.message,true);}finally{button.disabled=false;}
};
async function deleteManual(item){
 if(!confirm(t('confirmDeleteManual')))return;
 try{await api('/manual-ingredients/'+item.id+'?version='+item.version,{method:'DELETE'});if(manualEditing?.id===item.id)editManual();await loadManualIngredients();message(t('deleted'));}
 catch(e){message(e.message,true);}
}
$('newManual').onclick=()=>editManual();$('manualCancel').onclick=()=>editManual();$('manualFilter').oninput=renderManualList;
$('manualCaptureSelect').onchange=updateManualCaptureInfo;
$('manualSave').disabled=true;$('manualImportButton').disabled=true;
window.addEventListener('friss-data-updated',()=>{if(!$('dashboard').hidden)loadManualIngredients();});
window.addEventListener('friss-page',()=>{if(!$('dashboard').hidden)loadManualIngredients();});
window.addEventListener('friss-logout',()=>{manualGeneration++;manualImportGeneration++;manualSource=null;manualImportPending=false;$('manualImportForm').reset();$('manualImportStatus').textContent='';$('manualImportButton').disabled=true;manualItems=[];manualSchema=[];manualEditing=null;manualDraft=null;manualRestoredEntry=null;manualFieldsReady=false;$('manualForm').reset();$('manualNutrientFields').replaceChildren();$('manualFilter').value='';renderManualList();renderManualChoices();$('manualSave').disabled=true;});
new MutationObserver(()=>{renderManualList();renderManualChoices();for(const label of document.querySelectorAll('[data-manual-nutrient]'))label.textContent=nutrientLabel(label.dataset.manualNutrient);$('manualEditorTitle').textContent=t(manualEditing?'editManual':'newManual');}).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});
translate();if(!$('dashboard').hidden)loadManualIngredients();

Object.assign(words.de,{manualImportURL:'FoodData- oder FDDB-Link',manualImport:'Nährwerte importieren',manualImportHint:'Link zu fooddata.the50.store/ingredients oder einer deutschen FDDB-Lebensmittelseite einfügen. Import erstellt eine neue Zutat zur Prüfung; gespeichert wird erst mit Speichern. Namen kannst du anschließend anpassen.',manualImportLoading:'Nährwerte werden geladen …',manualImportDone:'Werte pro 100 g übernommen. Bitte prüfen und speichern.',manualImportError:'Import fehlgeschlagen.',manualImportReplace:'Die aktuellen Eingaben durch eine neue importierte Zutat ersetzen?',manualImportMissing:'Nicht verfügbare oder nicht unterstützte Nährwerte bleiben leer.',manualImportWater:'Wassergehalt bleibt in Gramm; keine Umrechnung in getrunkenes Wasser.',manualImportCarbs:'Kohlenhydrate auf die europäische Angabe ohne Ballaststoffe umgerechnet: US-Gesamtwert minus Ballaststoffe. Ballaststoffe und Kalorien bleiben unverändert.',manualImportCarbsUnknown:'Kohlenhydrate bleiben leer: Ballaststoffe fehlen oder sind höher als die Gesamtkohlenhydrate.',manualImportSkipped:'Nicht übernommen',manualImportOther:'Weitere Hinweise stehen in den Notizen.',manualImportCancelled:'Import nicht übernommen, weil die Eingaben inzwischen geändert wurden.'});
Object.assign(words.en,{manualImportURL:'FoodData or FDDB link',manualImport:'Import nutrients',manualImportHint:'Paste a fooddata.the50.store/ingredients link or a German FDDB food-page link. The import creates a new ingredient for review; use Save to store it. You can edit the names afterwards.',manualImportLoading:'Loading nutrients …',manualImportDone:'Values per 100 g imported. Please review and save.',manualImportError:'Import failed.',manualImportReplace:'Replace your current input with a new imported ingredient?',manualImportMissing:'Missing or unsupported nutrients remain empty.',manualImportWater:'Food water stays in grams; no conversion to drinking water.',manualImportCarbs:'Carbohydrates converted to the European value excluding fibre: US total minus dietary fibre. Fibre and energy are unchanged.',manualImportCarbsUnknown:'Carbohydrates remain empty: fibre is missing or greater than total carbohydrates.',manualImportSkipped:'Not imported',manualImportOther:'Additional information is included in the notes.',manualImportCancelled:'Import was not applied because the input changed while loading.'});
function manualHasDraft(){return manualEditing||['manualNameDe','manualNameEn','manualNotes','manualEthanol'].some(id=>$(id).value!=='')||manualSchema.some(field=>$('manualValue-'+field.key)?.value!=='');}
$('manualImportForm').onsubmit=async event=>{
 event.preventDefault();if(!manualFieldsReady||manualImportPending)return;
 if(manualHasDraft()&&!confirm(t('manualImportReplace')))return;
 const button=$('manualImportButton'),generation=++manualImportGeneration;manualImportPending=true;button.disabled=true;$('manualImportStatus').textContent=t('manualImportLoading');
 const url=$('manualImportURL').value.trim();
 try{
 const imported=await api('/manual-ingredients/import',{method:'POST',body:JSON.stringify({url})});
 if(generation!==manualImportGeneration||$('dashboard').hidden)return;
 editManual(imported);manualEditing=null;manualSource=imported.source;manualDraft=null;$('manualEditorTitle').textContent=t('newManual');
 const hints=[t('manualImportDone'),t('manualImportMissing')];
 if(imported.nutrients.dietaryWater?.unit==='g')hints.push(t('manualImportWater'));
 if(imported.source.carbohydrate_conversion)hints.push(t(imported.source.carbohydrate_conversion.status==='converted'?'manualImportCarbs':'manualImportCarbsUnknown'));
 if(imported.skipped.length)hints.push(t('manualImportSkipped')+': '+imported.skipped.map(v=>v.name).join(', '));
 $('manualImportStatus').textContent=hints.join(' ');$('manualForm').scrollIntoView({behavior:'smooth',block:'start'});
 }catch(e){if(generation===manualImportGeneration)$('manualImportStatus').textContent=t('manualImportError')+' '+e.message;}
 finally{manualImportPending=false;button.disabled=!manualFieldsReady;}
};
// Editing while a source request is pending cancels applying its result.
function cancelStaleImport(){if(manualImportPending){manualImportGeneration++;$('manualImportStatus').textContent=t('manualImportCancelled');}}
$('manualForm').addEventListener('input',cancelStaleImport);
$('manualImportURL').oninput=cancelStaleImport;
translate();
