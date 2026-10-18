Object.assign(words.de,{backupTitle:'Datensicherung und Wiederherstellung',backupHint:'ZIP mit JSON, Originaldateien, Lebensmitteldaten, Rezepten, Einstellungen und Bildern herunterladen. Zugangsdaten werden nicht gesichert. Die Datei enthält persönliche Daten.',backupDownload:'Sicherung herunterladen',backupFile:'Friss-Sicherung (ZIP, bis 128 MiB)',backupInspect:'Sicherung prüfen',backupRestore:'Daten wiederherstellen',backupReplaceHint:'Wiederherstellung ersetzt alle Friss-Daten durch die Sicherung. Vorher wird der aktuelle Stand auf dem Server unter data/recovery gesichert. Apple Health wird dadurch nicht verändert; bei älteren Sicherungen Exportstatus vor erneutem Export prüfen.',backupConfirm:'Alle aktuellen Friss-Daten durch diese Sicherung ersetzen? Eine Wiederherstellung ist kein Zusammenführen. Apple Health bleibt unverändert.',backupWorking:'Sicherung wird verarbeitet …',backupDownloaded:'Sicherung heruntergeladen.',backupRestored:'Wiederhergestellt. Die Seite wird neu geladen.',backupCreated:'Erstellt',backupRecords:'Datensätze',backupFiles:'Originaldateien',backupChoose:'Bitte zuerst eine ZIP-Datei auswählen.'});
Object.assign(words.en,{backupTitle:'Backup and restore',backupHint:'Download a ZIP with JSON, originals, food data, recipes, settings and images. Credentials are excluded. The file contains personal data.',backupDownload:'Download backup',backupFile:'Friss backup (ZIP, up to 128 MiB)',backupInspect:'Check backup',backupRestore:'Restore data',backupReplaceHint:'Restore replaces all Friss data with the backup. The current state is saved on the server under data/recovery first. Apple Health is unchanged; after restoring an older backup check export status before exporting again.',backupConfirm:'Replace all current Friss data with this backup? Restore does not merge data. Apple Health remains unchanged.',backupWorking:'Processing backup …',backupDownloaded:'Backup downloaded.',backupRestored:'Restored. Reloading the page.',backupCreated:'Created',backupRecords:'Records',backupFiles:'Original files',backupChoose:'Choose a ZIP file first.'});
(function(){
 let generation=0,checked=null,busy=false;
 function lock(value){busy=value;$('backupDownload').disabled=value;$('backupFile').disabled=value;$('backupInspect').disabled=value;$('backupRestore').disabled=value||!checked;}
 function clear(){generation++;checked=null;$('backupFile').value='';$('backupSummary').textContent='';$('backupStatus').textContent='';$('backupRestore').hidden=true;lock(false);}
 $('backupFile').onchange=()=>{generation++;checked=null;$('backupSummary').textContent='';$('backupRestore').hidden=true;lock(false);};
 $('backupDownload').onclick=async()=>{
  if(busy)return;const mine=generation;lock(true);$('backupStatus').textContent=t('backupWorking');
  try{const r=await fetch('/backups/export');if(r.status===401){signout();throw Error(t('invalidKey'));}if(!r.ok){let detail;try{detail=(await r.json()).detail;}catch{}throw Error(detail||'HTTP '+r.status);}const blob=await r.blob();if(mine!==generation)return;const a=document.createElement('a'),url=URL.createObjectURL(blob);a.href=url;a.download='friss-backup-'+new Date().toISOString().slice(0,10)+'.zip';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);$('backupStatus').textContent=t('backupDownloaded');}
  catch(e){if(mine===generation)$('backupStatus').textContent=e.message;}finally{if(mine===generation)lock(false);}
 };
 $('backupInspect').onclick=async()=>{
  if(busy)return;const file=$('backupFile').files[0];if(!file){$('backupStatus').textContent=t('backupChoose');return;}if(file.size>128*1024*1024){$('backupStatus').textContent='ZIP > 128 MiB';return;}
  const mine=++generation;checked=null;lock(true);$('backupRestore').hidden=true;$('backupSummary').textContent='';$('backupStatus').textContent=t('backupWorking');
  try{const result=await api('/backups/inspect',{method:'POST',body:file,headers:{'Content-Type':'application/zip'}});if(mine!==generation)return;checked=file;$('backupSummary').textContent=t('backupCreated')+': '+result.created_at+' · Friss '+result.app_version+' · '+t('backupRecords')+': '+Object.values(result.counts).reduce((a,b)=>a+b,0)+' · '+t('backupFiles')+': '+result.files;$('backupRestore').hidden=false;$('backupStatus').textContent='';}
  catch(e){if(mine===generation)$('backupStatus').textContent=e.message;}finally{if(mine===generation)lock(false);}
 };
 $('backupRestore').onclick=async()=>{
  if(busy||!checked||!confirm(t('backupConfirm')))return;const file=checked,mine=generation;lock(true);$('backupStatus').textContent=t('backupWorking');
  try{await api('/backups/restore',{method:'POST',body:file,headers:{'Content-Type':'application/zip','X-Friss-Restore':'replace'}});if(mine!==generation)return;$('backupStatus').textContent=t('backupRestored');location.reload();}
  catch(e){if(mine===generation)$('backupStatus').textContent=e.message;}finally{if(mine===generation)lock(false);}
 };
 window.addEventListener('friss-logout',clear);window.addEventListener('friss-page',e=>{if(e.detail!=='settings')clear();});
})();
translate();
