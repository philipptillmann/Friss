Object.assign(words.de,{scanBarcode:'Barcode fotografieren',scanHint:'Barcode scharf und vollständig aufnehmen. Alternativ die Nummer eingeben. Das Foto wird nur auf deinem Server ausgewertet.',scanWorking:'Barcode wird gelesen …',scanFailed:'Kein Barcode lesbar. Näher und scharf fotografieren oder Nummer eingeben.',scanFound:'Barcode übernommen. Menge prüfen und speichern.',scanChoose:'Mehrere Barcodes erkannt — bitte auswählen:',scanRetryPending:'Bitte den ausstehenden Eintrag zuerst erneut speichern oder abbrechen.'});
Object.assign(words.en,{scanBarcode:'Photograph barcode',scanHint:'Capture the complete barcode sharply. You can also enter the number manually. The photo is decoded only on your server.',scanWorking:'Reading barcode …',scanFailed:'Could not read a barcode. Take a closer, sharp photo or enter the number.',scanFound:'Barcode filled in. Check the amount and save.',scanChoose:'Multiple barcodes found — please choose:',scanRetryPending:'Please retry or cancel the pending entry first.'});
async function barcodeImage(file){
 const url=URL.createObjectURL(file);
 try{
 const image=new Image();image.src=url;await image.decode();
 const scale=Math.min(1,2400/Math.max(image.naturalWidth,image.naturalHeight));
 const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(image.naturalWidth*scale));canvas.height=Math.max(1,Math.round(image.naturalHeight*scale));
 const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0,canvas.width,canvas.height);
 const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.95));
 if(!blob)throw Error('Image conversion failed');
 return blob;
 }finally{URL.revokeObjectURL(url);}
}
function installBarcodePicker(prefix,target,isActive){
 const input=$(prefix+'File'),button=$(prefix+'Button'),status=$(prefix+'Status'),results=$(prefix+'Results');
 let generation=0;
 button.onclick=()=>{if(prefix==='barcode'&&attempt){message(t('scanRetryPending'),true);return;}input.click();};
 input.onchange=async()=>{
 const file=input.files[0];input.value='';if(!file)return;
 const seq=++generation;button.disabled=true;results.replaceChildren();status.textContent=t('scanWorking');
 try{
 const blob=await barcodeImage(file);
 const response=await api('/barcode-scan',{method:'POST',body:blob,headers:{'Content-Type':'image/jpeg'}});
 if(seq!==generation||!isActive()||$('dashboard').hidden)return;
 const apply=code=>{$(target).value=code;$(target).dispatchEvent(new Event('input',{bubbles:true}));results.replaceChildren();status.textContent=t('scanFound');$(target).focus();};
 if(response.barcodes.length===1)apply(response.barcodes[0]);
 else{
 status.textContent=t('scanChoose');
 for(const code of response.barcodes){const choice=document.createElement('button');choice.type='button';choice.className='result';choice.textContent=code;choice.onclick=()=>{if(isActive())apply(code);};results.append(choice);}
 }
 }catch(e){if(seq===generation&&isActive()&&!$('dashboard').hidden){status.textContent=t('scanFailed');message(t('scanFailed')+' '+e.message,true);}}
 finally{if(seq===generation)button.disabled=false;}
 };
 window.addEventListener('friss-logout',()=>{generation++;button.disabled=false;status.textContent='';results.replaceChildren();});
 // Changing capture mode or page must invalidate a pending photo result.
 const cancel=()=>{generation++;button.disabled=false;status.textContent='';results.replaceChildren();};
 $(prefix==='barcode'?'kind':'quickType').addEventListener('change',cancel);
 if(prefix==='barcode'){
 $('entryForm').addEventListener('reset',cancel);
 window.addEventListener('friss-page',cancel);
 }else $('quickForm').addEventListener('reset',cancel);
}
installBarcodePicker('barcode','description',()=>$('kind').value==='barcode');
installBarcodePicker('quickBarcode','quickDescription',()=>$('quickType').value==='barcode');
translate();
