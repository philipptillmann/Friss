Object.assign(words.de,{shortcutAPI:'API für Kurzbefehle',shortcutAPIHint:'Diesen Schlüssel im Kurzbefehl als Authorization-Header verwenden: Bearer <Schlüssel>.',showAPIKey:'API-Schlüssel anzeigen',hideAPIKey:'Ausblenden',apiKeyLabel:'API-Schlüssel',copyAPIKey:'Kopieren',apiKeyCopied:'Kopiert.',apiKeyManualCopy:'Schlüssel ausgewählt. Bitte gedrückt halten und kopieren.',apiKeyMissing:'Kein API-Schlüssel auf dem Server konfiguriert (FRISS_API_KEY).'});
Object.assign(words.en,{shortcutAPI:'API for Shortcuts',shortcutAPIHint:'Use this key in the Shortcut Authorization header: Bearer <key>.',showAPIKey:'Show API key',hideAPIKey:'Hide',apiKeyLabel:'API key',copyAPIKey:'Copy',apiKeyCopied:'Copied.',apiKeyManualCopy:'Key selected. Press and hold to copy it.',apiKeyMissing:'No API key configured on the server (FRISS_API_KEY).'});
(function(){
 let generation=0;
 function clear(){generation++;$('apiKeyValue').value='';$('apiKeyValueGroup').hidden=true;$('apiKeyReveal').textContent=t('showAPIKey');$('apiKeyReveal').disabled=false;$('apiKeyStatus').textContent='';}
 $('apiKeyReveal').onclick=async()=>{
 if(!$('apiKeyValueGroup').hidden){clear();return;}
 const mine=++generation;$('apiKeyReveal').disabled=true;
 try{const result=await api('/auth/api-key',{method:'POST'});if(mine!==generation||currentPage!=='settings'||$('dashboard').hidden)return;
 if(!result.configured){$('apiKeyStatus').textContent=t('apiKeyMissing');return;}
 $('apiKeyValue').value=result.api_key;$('apiKeyValueGroup').hidden=false;$('apiKeyReveal').textContent=t('hideAPIKey');
 }catch(e){if(mine===generation)$('apiKeyStatus').textContent=e.message;}
 finally{if(mine===generation)$('apiKeyReveal').disabled=false;}
 };
 $('apiKeyCopy').onclick=async()=>{
 const value=$('apiKeyValue').value;if(!value)return;const mine=generation;
 try{if(!navigator.clipboard?.writeText)throw Error('Clipboard unavailable');await navigator.clipboard.writeText(value);if(mine===generation)$('apiKeyStatus').textContent=t('apiKeyCopied');}
 catch{if(mine!==generation)return;$('apiKeyValue').focus();$('apiKeyValue').select();const copied=typeof document.execCommand==='function'&&document.execCommand('copy');$('apiKeyStatus').textContent=t(copied?'apiKeyCopied':'apiKeyManualCopy');}
 };
 window.addEventListener('friss-page',event=>{if(event.detail!=='settings')clear();});window.addEventListener('friss-logout',clear);
 document.addEventListener('visibilitychange',()=>{if(document.hidden)clear();});
 translate();
})();
