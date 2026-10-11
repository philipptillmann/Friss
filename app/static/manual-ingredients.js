Object.assign(words.de,{manualIngredients:'Eigene Zutaten',chooseManual:'Eigene Zutat auswählen',manageManual:'Eigene Zutaten verwalten',manualIntro:'Eigene Lebensmittel mit Nährwerten pro 100 g speichern und in Mahlzeiten oder Rezepten verwenden.',newManual:'Neue Zutat',editManual:'Zutat bearbeiten',manualNameDe:'Name (Deutsch)',manualNameEn:'Name (Englisch)',per100g:'Nährwerte pro 100 g',manualValuesHint:'Nur bekannte Werte eintragen. Leer bleibt unbekannt; 0 bedeutet einen bekannten Nullwert. Energie wird nicht aus Makros geschätzt. Änderungen gelten für künftig hinzugefügte Einträge.',manualAlcohol:'Reiner Alkohol (g pro 100 g)',noManual:'Noch keine eigenen Zutaten angelegt.',confirmDeleteManual:'Eigene Zutat wirklich löschen? Bereits gespeicherte Mahlzeiten und Rezeptzutaten behalten ihre Nährwerte.',manualSnapshot:'Gespeicherter Stand der Zutat',manualNeedNutrient:'Bitte mindestens einen Nährwert eintragen.',manualLoadError:'Eigene Zutaten konnten nicht geladen werden.'});
Object.assign(words.en,{manualIngredients:'My ingredients',chooseManual:'Choose my ingredient',manageManual:'Manage my ingredients',manualIntro:'Save your own foods with nutrients per 100 g, then use them in meals or recipes.',newManual:'New ingredient',editManual:'Edit ingredient',manualNameDe:'Name (German)',manualNameEn:'Name (English)',per100g:'Nutrients per 100 g',manualValuesHint:'Enter known values only. Empty means unknown; 0 means a known zero. Energy is not estimated from macros. Changes apply to future entries.',manualAlcohol:'Pure alcohol (g per 100 g)',noManual:'No ingredients added yet.',confirmDeleteManual:'Really delete this ingredient? Logged meals and recipe ingredients will retain their values.',manualSnapshot:'Recorded ingredient version',manualNeedNutrient:'Please enter at least one nutrient.',manualLoadError:'Could not load your ingredients.'});
let manualItems=[],manualSchema=[],manualEditing=null,manualDraft=null,manualGeneration=0,manualRestoredEntry=null,manualFieldsReady=false;
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
 for(const name of field.units){const option=document.createElement('option');option.value=name;option.textContent=name;unit.append(option);}unit.value=field.unit;
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
 manualItems=items;manualSchema=schema;buildManualFields();renderManualList();renderManualChoices();$('manualSave').disabled=false;
 }catch(e){if(generation===manualGeneration)message(t('manualLoadError')+' '+e.message,true);}
}
function editManual(item=null){
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
 const body={name_de:$('manualNameDe').value.trim(),name_en:$('manualNameEn').value.trim(),notes:$('manualNotes').value,nutrients,ethanol_g_per100:alcohol===''?null:Number(alcohol),version:manualEditing?.version??0};
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
$('manualSave').disabled=true;
window.addEventListener('friss-data-updated',()=>{if(!$('dashboard').hidden)loadManualIngredients();});
window.addEventListener('friss-page',()=>{if(!$('dashboard').hidden)loadManualIngredients();});
window.addEventListener('friss-logout',()=>{manualGeneration++;manualItems=[];manualSchema=[];manualEditing=null;manualDraft=null;manualRestoredEntry=null;manualFieldsReady=false;$('manualForm').reset();$('manualNutrientFields').replaceChildren();$('manualFilter').value='';renderManualList();renderManualChoices();$('manualSave').disabled=true;});
new MutationObserver(()=>{renderManualList();renderManualChoices();for(const label of document.querySelectorAll('[data-manual-nutrient]'))label.textContent=nutrientLabel(label.dataset.manualNutrient);$('manualEditorTitle').textContent=t(manualEditing?'editManual':'newManual');}).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});
translate();if(!$('dashboard').hidden)loadManualIngredients();
