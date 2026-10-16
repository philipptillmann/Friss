Object.assign(words.de,{labelScan:'Nährwertetikett fotografieren',labelScanText:'Erkannter Text',labelScanWorking:'Etikett wird auf deinem Server gelesen …',labelScanDone:'Vorschläge pro 100 g übernommen. Namen eintragen, alle Werte mit dem Etikett vergleichen und speichern. Salz wurde gegebenenfalls in Natrium umgerechnet.',labelScanUnknown:'Keine eindeutigen Werte pro 100 g erkannt. Bitte nur die 100-g-Spalte fotografieren oder Werte manuell eingeben. Portionsangaben, US-Labels und 100-ml-Angaben werden nicht automatisch umgerechnet.',labelScanError:'Etikett konnte nicht gelesen werden.',labelScanReady:'Bitte warten, bis die Zutatenmaske geladen ist.'});
Object.assign(words.en,{labelScan:'Photograph nutrition label',labelScanText:'Recognized text',labelScanWorking:'Reading label on your server …',labelScanDone:'Per-100-g suggestions filled in. Enter a name, check every value against the label, then save. Salt was converted to sodium where applicable.',labelScanUnknown:'No unambiguous per-100-g values found. Photograph only the 100-g column or enter values manually. Per-serving, US and per-100-ml labels are not automatically converted.',labelScanError:'Could not read the label.',labelScanReady:'Please wait for the ingredient form to load.'});
(function(){
 let sequence=0;
 $('labelScanButton').onclick=()=>{if(!manualFieldsReady){$('labelScanStatus').textContent=t('labelScanReady');return;}if(!manualImportPending)$('labelScanFile').click();};
 $('labelScanFile').onchange=async()=>{
 const file=$('labelScanFile').files[0];$('labelScanFile').value='';if(!file||manualImportPending||!manualFieldsReady)return;
 if(manualHasDraft()&&!confirm(t('manualImportReplace')))return;
 const mine=++sequence,generation=++manualImportGeneration;manualImportPending=true;$('labelScanButton').disabled=true;$('manualImportButton').disabled=true;$('labelScanStatus').textContent=t('labelScanWorking');$('labelScanReview').hidden=true;
 try{
 const image=await barcodeImage(file);const result=await api('/manual-ingredients/scan-label',{method:'POST',body:image});
 if(mine!==sequence||generation!==manualImportGeneration||$('dashboard').hidden)return;
 $('labelScanText').textContent=result.text;$('labelScanReview').hidden=false;
 if(!Object.keys(result.nutrients).length){$('labelScanStatus').textContent=t('labelScanUnknown');return;}
 editManual({name_de:'',name_en:'',notes:'Nutrition label OCR (review required)\n'+result.warnings.join('\n')+'\n\n'+result.text.slice(0,8000),nutrients:result.nutrients});
 manualEditing=null;manualSource=null;manualDraft=null;$('manualEditorTitle').textContent=t('newManual');$('labelScanStatus').textContent=t('labelScanDone');$('manualForm').scrollIntoView({behavior:'smooth',block:'start'});
 }catch(e){if(mine===sequence&&generation===manualImportGeneration)$('labelScanStatus').textContent=t('labelScanError')+' '+e.message;}
 finally{if(mine===sequence){manualImportPending=false;$('labelScanButton').disabled=false;$('manualImportButton').disabled=!manualFieldsReady;}}
 };
 window.addEventListener('friss-logout',()=>{sequence++;$('labelScanFile').value='';$('labelScanText').textContent='';$('labelScanStatus').textContent='';$('labelScanReview').hidden=true;$('labelScanButton').disabled=false;});
 translate();
})();
