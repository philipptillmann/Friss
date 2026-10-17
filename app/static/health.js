Object.assign(words.de,{health:'Export',healthIntro:'Friss kann im Browser nicht direkt in Apple Health schreiben. Exportdatei auf dem iPhone mit einem Health-Kurzbefehl öffnen. Erst nach erfolgreichem Schreiben bestätigen.',exportDay:'Tag exportieren',downloadExport:'Exportdatei laden / teilen',confirmHealth:'Health-Schreiben bestätigen',failedHealth:'Export fehlgeschlagen / unklar',not_exported:'Noch nicht exportiert',prepared:'Vorbereitet · Health noch nicht bestätigt',confirmed:'In Health · bestätigt',needs_review:'Manuell prüfen',changedDay:'Seit Export geändert · Korrektur in Health erforderlich',bls_units:'BLS-Einheiten noch ungeprüft · Export gesperrt',unresolved:'Offene Einträge nachbearbeiten',previous_export:'Einzelne Einträge bereits reserviert / exportiert',no_nutrients:'Keine exportierbaren Nährwerte',empty:'Keine Einträge',healthConfirm:'Sind ALLE Werte dieses Tages erfolgreich in Apple Health gespeichert? Diese Bestätigung prüft Health nicht automatisch.',healthFailure:'Export als fehlgeschlagen oder unklar markieren? Nicht automatisch erneut exportieren, um doppelte Werte zu vermeiden.',healthPrepareZero:'Diesen Tag für Health reservieren? Fehlende Nährwerte werden entsprechend deiner Einstellung als 0 angenommen und mit exportiert.',healthPrepare:'Diesen Tag abschließen und für Health reservieren? Nur bekannte Nährwerte werden exportiert; fehlende Werte bleiben unbekannt.',healthNoDays:'Noch keine Tagebucheinträge.',healthGuide:'Anleitung für den iPhone-Kurzbefehl',healthGuideText:'Exportdatei als Eingabe annehmen → JSON-Wörterbuch lesen → samples wiederholen → identifier der passenden Aktion „Gesundheitsdaten protokollieren“ zuordnen → value und unit verwenden, timestamp als Datum. Erst wenn alle Aktionen erfolgreich waren, hier bestätigen. Bei Abbruch Bestand in Health prüfen. Alkohol in Gramm und BAC werden nicht als Ernährungswerte exportiert.'});
Object.assign(words.en,{health:'Export',healthIntro:'Friss cannot write to Apple Health from a browser. Open the export file on your iPhone with a Health shortcut. Confirm only after all samples have been written.',exportDay:'Export day',downloadExport:'Download / share export',confirmHealth:'Confirm Health write',failedHealth:'Export failed / uncertain',not_exported:'Not exported yet',prepared:'Prepared · Health not confirmed',confirmed:'In Health · confirmed',needs_review:'Review manually',changedDay:'Changed since export · Health correction required',bls_units:'BLS units unverified · export blocked',unresolved:'Resolve pending entries',previous_export:'Entries already reserved / exported individually',no_nutrients:'No exportable nutrients',empty:'No entries',healthConfirm:'Have ALL values for this day been successfully written to Apple Health? This confirmation does not check Health automatically.',healthFailure:'Mark this export as failed or uncertain? Do not automatically export again, to avoid duplicates.',healthPrepareZero:'Reserve this day for Health? Missing nutrients are assumed to be 0 according to your setting and included in the export.',healthPrepare:'Finish and reserve this day for Health? Only known nutrients are exported; missing values remain unknown.',healthNoDays:'No journal entries yet.',healthGuide:'iPhone shortcut instructions',healthGuideText:'Accept export file as input → parse JSON dictionary → repeat samples → map identifier to the matching Log Health Sample action → use value and unit, timestamp as the date. Confirm here only after all actions succeed. After interruption, check Health manually. Alcohol grams and BAC are not exported as nutrition values.'});
let healthGeneration=0;
function healthZone(){return Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC';}
async function loadHealthDays(){
 const generation=++healthGeneration;
 try{
 const days=await api('/health-days?tz='+encodeURIComponent(healthZone()));
 if(generation!==healthGeneration)return;
 $('healthDays').replaceChildren();
 if(!days.length){$('healthDays').textContent=t('healthNoDays');return;}
 for(const day of days){
 const article=document.createElement('article');article.className='healthDay';
 const title=document.createElement('h3');title.textContent=new Date(day.day+'T12:00:00').toLocaleDateString(lang,{dateStyle:'full'});
 const status=document.createElement('p');status.textContent=t(day.status)+' · '+day.entries+' '+t('entries');
 const actions=document.createElement('div');actions.className='bacActions';
 if(day.changed){const warning=document.createElement('p');warning.className='note';warning.textContent=t('changedDay');article.append(warning);}
 if(day.blocked){const warning=document.createElement('p');warning.className='note';warning.textContent=t(day.blocked);article.append(warning);}
 function button(label,handler){const b=document.createElement('button');b.type='button';b.textContent=t(label);b.onclick=async()=>{b.disabled=true;try{await handler();}catch(e){message(e.message,true);}finally{b.disabled=false;}};actions.append(b);return b;}
 if(!day.batch_id)button('exportDay',async()=>{
 if(!confirm(t(day.missing_nutrients_as_zero?'healthPrepareZero':'healthPrepare')))return;
 const batch=await api('/health-days/prepare',{method:'POST',body:JSON.stringify({day:day.day,timezone:healthZone()})});
 await loadHealthDays();await refresh();await shareHealthBatch(batch);
 }).disabled=!!day.blocked;
 else if(day.status==='prepared'){
 button('downloadExport',async()=>shareHealthBatch(await api('/health-days/'+day.batch_id))).disabled=day.changed;
 button('confirmHealth',async()=>{
 if(!confirm(t('healthConfirm')))return;
 const batch=await api('/health-days/'+day.batch_id);
 await api('/health-days/'+day.batch_id+'/ack',{method:'POST',body:JSON.stringify({export_token:batch.export_token,success:true})});
 await refresh();await loadHealthDays();
 });
 button('failedHealth',async()=>{
 if(!confirm(t('healthFailure')))return;
 const batch=await api('/health-days/'+day.batch_id);
 await api('/health-days/'+day.batch_id+'/ack',{method:'POST',body:JSON.stringify({export_token:batch.export_token,success:false})});
 await refresh();await loadHealthDays();
 });
 }
 article.prepend(title,status);article.append(actions);$('healthDays').append(article);
 }
 }catch(e){if(generation===healthGeneration)message(e.message,true);}
}
async function shareHealthBatch(batch){
 const payload={schema:'friss-health-day-v1',batch_id:batch.id,day:batch.day,timezone:batch.timezone,missing_nutrients_as_zero:!!batch.missing_nutrients_as_zero,samples:batch.samples};
 const file=new File([JSON.stringify(payload,null,2)],'friss-health-'+batch.day+'.json',{type:'application/json'});
 if(navigator.canShare?.({files:[file]})){
 try{await navigator.share({files:[file],title:'Friss · '+batch.day});return;}catch(e){if(e.name==='AbortError')return;}
 }
 const url=URL.createObjectURL(file),a=document.createElement('a');a.href=url;a.download=file.name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
}
window.addEventListener('friss-page',e=>{if(e.detail==='health'&&!$('dashboard').hidden)loadHealthDays();});
window.addEventListener('friss-data-updated',()=>{if(currentPage==='health')loadHealthDays();});
window.addEventListener('friss-logout',()=>{healthGeneration++;$('healthDays').replaceChildren();});
new MutationObserver(()=>{if(currentPage==='health'&&!$('dashboard').hidden)loadHealthDays();}).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});
translate();

