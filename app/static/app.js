function formatNumber(value){return new Intl.NumberFormat(lang,{maximumFractionDigits:2}).format(value);}
function uuid(){const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;const h=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;}
const $=id=>document.getElementById(id);
const words={de:{logout:'Abmelden',welcome:'Dein Tag. Dein Überblick.',loginHint:'Melde dich an. Auf diesem Gerät bleibst du bis zu 30 Tage angemeldet.',key:'Passwort',connect:'Verbinden',journal:'DEIN ERNÄHRUNGSTAGEBUCH',overview:'Alles im Blick.',refresh:'Aktualisieren',energy:'Kalorien',water:'Wasser',caffeine:'Koffein',alcohol:'Alkohol',ethanol:'g Ethanol',totalsHint:'Summen berechneter Einträge. Fehlende Werte und Getränkekalorien werden nicht geschätzt. BLS-Werte sind vorläufig; ihr Health-Export ist gesperrt.',add:'Eintrag hinzufügen',kind:'Erfassung',food:'Lebensmittel suchen',text:'Text',photo:'Foto (JPEG)',search:'Lebensmittel suchen',description:'Beschreibung / Barcode',amount:'Menge (g)',volume:'Menge (ml)',time:'Zeitpunkt',caffeineAmount:'Koffein gesamt (mg)',coffee:'Kaffee / Koffein',abv:'Alkoholgehalt (% vol)',save:'Speichern',cancel:'Abbrechen',entries:'Deine Einträge',reviewHint:'Offene Einträge anklicken, um Lebensmittel und Menge zuzuordnen.',footer:'Deine Daten auf deinem Server.',empty:'Noch keine Einträge für diesen Tag.',processed:'Berechnet',needs_review:'Nachbearbeiten',failed:'Fehlgeschlagen',unprocessed:'Offen',synced:'Health bestätigt',pending:'Health ausstehend',claimed:'Health reserviert',saved:'Gespeichert.',select:'Bitte ein Lebensmittel auswählen.',none:'Keine Treffer.',resolve:'Eintrag nachbearbeiten',invalidKey:'Bitte erneut anmelden.',loadError:'Nicht geladen — bitte erneut aktualisieren.',retry:'Übertragung fehlgeschlagen. Erneut Speichern sendet denselben Eintrag.',photoMissing:'Bitte eine JPEG-Datei auswählen.',limit:'Es werden maximal 1.000 Einträge angezeigt; Summen können unvollständig sein.'},en:{logout:'Sign out',welcome:'Your day. At a glance.',loginHint:'Sign in. Stay signed in on this device for up to 30 days.',key:'Password',connect:'Connect',journal:'YOUR FOOD JOURNAL',overview:'Everything at a glance.',refresh:'Refresh',energy:'Calories',water:'Water',caffeine:'Caffeine',alcohol:'Alcohol',ethanol:'g ethanol',totalsHint:'Totals from calculated entries. Missing values and drink calories are not estimated. BLS values are provisional; their Health export is blocked.',add:'Add an entry',kind:'Capture',food:'Search food',text:'Text',photo:'Photo (JPEG)',search:'Search food',description:'Description / barcode',amount:'Amount (g)',volume:'Volume (ml)',time:'Time',caffeineAmount:'Total caffeine (mg)',coffee:'Coffee / caffeine',abv:'Alcohol content (% ABV)',save:'Save',cancel:'Cancel',entries:'Your entries',reviewHint:'Select an unresolved entry to assign a food and quantity.',footer:'Your data on your server.',empty:'No entries for this day yet.',processed:'Calculated',needs_review:'Needs review',failed:'Failed',unprocessed:'Pending',synced:'Health confirmed',pending:'Health pending',claimed:'Health reserved',saved:'Saved.',select:'Please select a food.',none:'No matches.',resolve:'Review entry',invalidKey:'Please sign in again.',loadError:'Not loaded — please refresh again.',retry:'Transfer failed. Saving again retries the same entry.',photoMissing:'Please select a JPEG file.',limit:'Only 1,000 entries are shown; totals may be incomplete.'}};
let lang=localStorage.getItem('frissLanguage')||'de',key='',selected=null,editing=null,importedBasis=null,rows=[],attempt=null,searchSequence=0;
Object.assign(words.de,{recipes:'Rezepte',destination:'Speichern in',daily:'Tagebuch',chooseRecipe:'Rezept auswählen',newRecipe:'Neues Rezept',recipeName:'Rezeptname',servings:'Portionen im ganzen Rezept',finishedWeight:'Fertiges Gesamtgewicht (g, optional)',recipeNotes:'Notizen / Zubereitung',saveRecipe:'Rezept speichern',intakeAmount:'Gegessene Menge',intakeUnit:'Einheit',portions:'Portionen',fraction:'Anteil des ganzen Rezepts (0–1)',logRecipe:'Zum Tagebuch hinzufügen',recipeHint:'Zutaten unten erfassen und das Rezept als Ziel auswählen. Erst vollständig zugeordnete Zutaten können als Verzehr gebucht werden.',ingredients:'Zutaten',ready:'Bereit',recipe:'Rezept'});
Object.assign(words.en,{recipes:'Recipes',destination:'Save to',daily:'Daily journal',chooseRecipe:'Choose recipe',newRecipe:'New recipe',recipeName:'Recipe name',servings:'Servings in the whole recipe',finishedWeight:'Finished total weight (g, optional)',recipeNotes:'Notes / preparation',saveRecipe:'Save recipe',intakeAmount:'Amount eaten',intakeUnit:'Unit',portions:'Servings',fraction:'Fraction of the whole recipe (0–1)',logRecipe:'Add to daily journal',recipeHint:'Capture ingredients below and select the recipe as destination. Resolve all ingredients before logging a serving.',ingredients:'Ingredients',ready:'Ready',recipe:'Recipe'});
Object.assign(words.de,{recipeAdditions:'Zusätzliche Mengen fürs ganze Rezept',recipeAdditionsHint:'Nur ergänzen, was noch nicht in den Zutaten erfasst ist. Die Mengen werden zusätzlich addiert.',recipeWater:'Wasser (ml)',recipeCaffeine:'Koffein (mg)',recipeAlcohol:'Reiner Alkohol (g)'});
Object.assign(words.en,{recipeAdditions:'Additional amounts for the whole recipe',recipeAdditionsHint:'Only add amounts not already included in ingredients. These amounts are added on top.',recipeWater:'Water (ml)',recipeCaffeine:'Caffeine (mg)',recipeAlcohol:'Pure alcohol (g)'});
Object.assign(words.de,{sourceBLS:'BLS',sourceOFF:'Open Food Facts',sourceManual:'Eigene Zutat',sourceRecipe:'Rezept',sourceDrink:'Getränk',sourceFavorite:'Favorit',sourceAI:'KI-Import',sourceUnknown:'Nicht zugeordnet'});
Object.assign(words.en,{sourceBLS:'BLS',sourceOFF:'Open Food Facts',sourceManual:'My ingredient',sourceRecipe:'Recipe',sourceDrink:'Drink',sourceFavorite:'Favorite',sourceAI:'AI import',sourceUnknown:'Unassigned'});
let recipeRows=[],activeRecipe='',recipeDraft=null,intakeAttempt=null;
Object.assign(words.de,{home:'Home',meals:'Mahlzeiten',quickAdd:'Schnell hinzufügen',coffeeQuick:'Kaffee',quickHint:'Für heute, zum aktuellen Zeitpunkt. Koffein ist ein vorbelegter Schätzwert.',eatRecipe:'Rezept essen',recipeHint:'Zutaten hier erfassen. Erst vollständig zugeordnete Zutaten können als Verzehr gebucht werden.',retryQuick:'Übertragung fehlgeschlagen. Derselbe Button versucht denselben Eintrag erneut.'});
Object.assign(words.en,{home:'Home',meals:'Meals',quickAdd:'Quick add',coffeeQuick:'Coffee',quickHint:'Logged for today at the current time. Caffeine is a preset estimate.',eatRecipe:'Eat a recipe',recipeHint:'Capture ingredients here. Resolve all ingredients before logging a serving.',retryQuick:'Transfer failed. Tap the same button to retry the same entry.'});
Object.assign(words.de,{deleteEntry:'Löschen',resetDay:'Tag zurücksetzen',confirmDeleteEntry:'Diesen Eintrag wirklich löschen?',confirmReset:'Alle Tagebucheinträge für {date} wirklich löschen? Rezepte bleiben erhalten.',deleteHealthHint:'Bereits an Apple Health übertragene Werte werden dort nicht automatisch gelöscht.',deleted:'Gelöscht.',deleteHealthNotice:'In Friss gelöscht. Bereits übertragene Werte bitte in Apple Health separat entfernen.'});
Object.assign(words.en,{deleteEntry:'Delete',resetDay:'Reset day',confirmDeleteEntry:'Really delete this entry?',confirmReset:'Really delete all journal entries for {date}? Recipes are kept.',deleteHealthHint:'Values already sent to Apple Health are not automatically deleted there.',deleted:'Deleted.',deleteHealthNotice:'Deleted in Friss. Please remove previously exported values separately in Apple Health.'});
Object.assign(words.de,{manualPage:'Manuell',chooseManageRecipe:'Rezepte auswählen / anlegen',drinkRecipes:'Getränke',drinks:'Getränke',manualDrink:'Getränk manuell eintragen',drinkVolume:'Gesamtvolumen des Getränkerezepts (ml)',drinkABV:'Alkoholgehalt des gesamten Getränks (% vol)',drinkABVHint:'Optional: endgültigen Alkoholgehalt mit Gesamtvolumen angeben. Er ersetzt den Alkohol aus Zutaten und darf nicht mit zusätzlichem reinem Alkohol kombiniert werden. Nährwerte über Zutaten erfassen; Zutaten aus Eigene Zutaten oder JSON können eigene Nährwerte enthalten.',saveFuture:'Nur für zukünftige Einträge speichern',saveAmend:'Speichern und bisherige Einträge korrigieren',confirmAmend:'Alle bereits gebuchten Portionen dieses Rezepts mit dem aktuellen Stand neu berechnen? Mengen und Zeitpunkte bleiben erhalten. Bereits exportierte Apple-Health-Werte müssen dort separat korrigiert werden.',migrateDrink:'Als Getränk verschieben',migrateFood:'Als Lebensmittelrezept verschieben',confirmMigrate:'Das gespeicherte Rezept in die andere Kategorie verschieben? Nicht gespeicherte Änderungen werden dabei verworfen. Zutaten und Schnellwahl-Verknüpfungen bleiben erhalten.',logDefinedDrink:'Getränk eintragen',amendedCount:'Korrigierte Tagebucheinträge'});
Object.assign(words.en,{manualPage:'Manual',chooseManageRecipe:'Select / create recipes',drinkRecipes:'Drinks',drinks:'Drinks',manualDrink:'Enter a drink manually',drinkVolume:'Total drink recipe volume (ml)',drinkABV:'Final drink alcohol content (% ABV)',drinkABVHint:'Optional: final ABV needs the total volume. It replaces alcohol calculated from ingredients and cannot be combined with additional pure alcohol. Add nutrients through ingredients, including My ingredients or JSON imports.',saveFuture:'Save for future entries only',saveAmend:'Save and correct previously logged entries',confirmAmend:'Recalculate all previously logged portions of this recipe using its current definition? Amounts and times stay unchanged. Values already exported to Apple Health must be corrected there separately.',migrateDrink:'Move to Drinks',migrateFood:'Move to food recipes',confirmMigrate:'Move the saved recipe to the other category? Unsaved changes will be discarded. Ingredients and quick-add links stay intact.',logDefinedDrink:'Log drink',amendedCount:'Corrected diary entries'});
function recipePage(){return currentPage==='recipes'||currentPage==='alcohol';}
function recipeCategory(){return currentPage==='alcohol'?'drink':'food';}
let currentPage='home',reusedVia=null;
const t=k=>words[lang][k]||k;
function message(s,error=false){$('message').textContent=s;$('message').className=error?'error':'';}
function localDate(d){return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
function now(){const d=new Date();$('time').value=localDate(d)+'T'+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');}
function translate(){document.documentElement.lang=lang;$('lang').value=lang;document.querySelectorAll('[data-i]').forEach(e=>e.textContent=t(e.dataset.i));kindChange(false);renderRecipes();render();updatePageLabels();}
async function api(path,options={}){const response=await fetch(path,{...options,headers:{...(options.body instanceof File?{'Content-Type':'image/jpeg'}:{'Content-Type':'application/json'}),...options.headers}});if(response.status===401){signout();throw Error(t('invalidKey'));}if(!response.ok){let detail;try{detail=(await response.json()).detail;}catch{}const error=Error(typeof detail==='string'?detail:JSON.stringify(detail)||`HTTP ${response.status}`);error.status=response.status;throw error;}return response.json();}
function signout(){window.dispatchEvent(new Event('friss-logout'));key='';sessionStorage.removeItem('frissKey');rows=[];recipeRows=[];activeRecipe='';recipeDraft=null;intakeAttempt=null;selected=null;editing=null;attempt=null;$('entryForm').reset();$('results').replaceChildren();$('selected').textContent='';$('key').value='';$('dashboard').hidden=true;$('login').hidden=false;$('logout').hidden=true;now();}
async function refresh(){try{const start=new Date($('day').value+'T00:00:00');const end=new Date(start);end.setDate(end.getDate()+1);if(typeof loadHome==='function')await loadHome();recipeRows=await api('/recipes');renderRecipes();rows=await api('/entries?limit=1000&start='+encodeURIComponent(start.toISOString())+'&end='+encodeURIComponent(end.toISOString()));render();window.dispatchEvent(new Event('friss-data-updated'));message(rows.length===1000?t('limit'):'');}catch(e){rows=[];render();message(t('loadError')+' '+e.message,true);}}
function nutrient(e,name,unit){const n=e.nutrients?.[name];if(!n)return 0;const scale={g:1000,mg:1,mcg:.001};if(n.unit===unit)return n.value;return unit==='mg'&&scale[n.unit]?n.value*scale[n.unit]:0;}
// Shared source badges for search results and saved entries.
function sourceLabel(source,category){return t(source==='recipe'?(category==='drink'?'sourceDrink':'sourceRecipe'):{bls:'sourceBLS',off:'sourceOFF',manual:'sourceManual',drink:'sourceDrink',favorite:'sourceFavorite',ai:'sourceAI',unknown:'sourceUnknown'}[source]||'sourceUnknown');}
function sourceBadge(source,category){const badge=document.createElement('span');badge.className='sourceBadge source-'+(source==='recipe'&&category==='drink'?'drink':source);badge.textContent=sourceLabel(source,category);return badge;}
function entrySourceBadge(entry){
 const provider=entry.source?.provider;
 if(entry.type==='recipe'||entry.recipe_snapshot){const category=entry.recipe_snapshot?.category||recipeRows.find(r=>r.id===(entry.recipe_snapshot?.id||entry.source?.recipe_id))?.category||'food';return sourceBadge('recipe',category);}
 if(entry.imported_nutrition||provider==='ChatGPT import')return sourceBadge('ai');
 if(entry.type==='manual'||entry.manual_id||provider==='Manual')return sourceBadge('manual');
 if(entry.bls_code||entry.food?.bls_code||provider==='BLS')return sourceBadge('bls');
 if(entry.barcode||provider==='Open Food Facts')return sourceBadge('off');
 if(entry.type==='drink')return sourceBadge('drink');
 return sourceBadge('unknown');
}
// End shared source badges.
function render(){if(typeof renderHome==='function')renderHome();const visible=recipePage()?(recipeRows.find(r=>r.id===activeRecipe)?.ingredients||[]):rows;$('resetDay').hidden=recipePage();$('resetDay').disabled=!visible.length;$('count').textContent=visible.length;$('entries').replaceChildren();if(!visible.length){const p=document.createElement('p');p.textContent=t('empty');$('entries').append(p);}for(const e of visible){const item=document.createElement('div');item.className='entry';const body=document.createElement('a');body.href='#entry/'+e.id;body.className='entryLink';const name=document.createElement('strong');name.textContent=e.food?.['name_'+lang]||e.food?.product_name||e.description||e.barcode||t(e.drink||e.type);const meta=document.createElement('p');meta.textContent=new Date(e.timestamp).toLocaleTimeString(lang,{hour:'2-digit',minute:'2-digit'})+' · '+(e.quantity?formatNumber(e.quantity.value)+' '+e.quantity.unit:'—')+(e.nutrients?.dietaryEnergyConsumed?' · '+formatNumber(e.nutrients.dietaryEnergyConsumed.value)+' kcal':'');const health=document.createElement('p');health.textContent=t(e.health_status);body.append(name,entrySourceBadge(e),meta);if(!recipePage())body.append(health);if(e.reason){const reason=document.createElement('p');reason.textContent=e.reason;body.append(reason);}const badge=document.createElement('button');badge.type='button';badge.className='badge'+(e.status==='processed'?'':' open');badge.textContent=t(e.status);badge.disabled=e.health_status!=='pending'||e.type==='recipe';badge.onclick=()=>resumeEntry(e);const actions=document.createElement('div');actions.className='entryActions';const remove=document.createElement('button');remove.type='button';remove.className='danger';remove.textContent=t('deleteEntry');remove.setAttribute('aria-label',t('deleteEntry')+' · '+name.textContent);remove.onclick=()=>deleteLoggedEntry(e,remove);actions.append(badge,remove);item.append(body,actions);$('entries').append(item);}}
async function deleteLoggedEntry(entry,button){
 if(!confirm(t('confirmDeleteEntry')+(entry.health_status!=='pending'?'\n\n'+t('deleteHealthHint'):'')))return;
 button.disabled=true;
 try{const result=await api('/entries/'+entry.id,{method:'DELETE'});if(editing===entry.id)reset();await refresh();message(t(result.health_correction_required?'deleteHealthNotice':'deleted'));}
 catch(e){message(e.message,true);}finally{button.disabled=false;}
}
$('resetDay').onclick=async()=>{
 const date=$('day').value;
 if(!confirm(t('confirmReset').replace('{date}',date)+'\n\n'+t('deleteHealthHint')))return;
 const button=$('resetDay');button.disabled=true;
 try{const start=new Date(date+'T00:00:00'),end=new Date(start);end.setDate(end.getDate()+1);
 const result=await api('/entries?start='+encodeURIComponent(start.toISOString())+'&end='+encodeURIComponent(end.toISOString()),{method:'DELETE'});
 reset();await refresh();message(t(result.health_correction_required?'deleteHealthNotice':'deleted'));
 }catch(e){message(e.message,true);}finally{button.disabled=!rows.length;}
};
function kindChange(clear=true){if(clear||recipePage()&&selected?.source==='recipe'){selected=null;}if(recipePage()&&['recipe','drink_recipe'].includes($('kind').value))$('kind').value='item';const kind=$('kind').value;const recipe=['recipe','drink_recipe'].includes(kind)||kind==='item'&&selected?.source==='recipe';$('mealRecipeGroup').hidden=!recipe;$('mealRecipe').required=recipe;$('mealRecipe').disabled=!recipe;$('mealRecipeAmount').disabled=!recipe;$('mealRecipeUnit').disabled=!recipe;$('mealRecipeAmount').max=$('mealRecipeUnit').value==='fraction'?'1':'';$('mealRecipeAmount').required=recipe;$('mealRecipeUnit').required=recipe;$('entryFinishGroup').hidden=!recipe&&!['water','coffee','alcohol'].includes(kind);$('amount').disabled=recipe;$('entryAmountGroup').hidden=recipe;$('kind').querySelector('option[value="recipe"]').disabled=recipePage();$('kind').querySelector('option[value="recipe"]').hidden=recipePage();$('kind').querySelector('option[value="drink_recipe"]').disabled=recipePage();$('kind').querySelector('option[value="drink_recipe"]').hidden=recipePage();$('manualCaptureGroup').hidden=kind!=='manual';$('manualCaptureSelect').required=kind==='manual';$('manualCaptureSelect').disabled=kind!=='manual'||kind==='manual'&&!!editing;$('barcodeCapture').hidden=kind!=='barcode';const drink=['water','coffee','alcohol'].includes(kind);$('searchGroup').hidden=!['item','off'].includes(kind);$('descriptionGroup').hidden=!['text','barcode'].includes(kind);$('photoGroup').hidden=kind!=='picture';$('caffeineGroup').hidden=kind!=='coffee';$('alcoholEntryModeGroup').hidden=kind!=='alcohol';$('abvGroup').hidden=kind!=='alcohol'||$('alcoholEntryMode').value==='g';$('amountLabel').textContent=t(kind==='alcohol'&&$('alcoholEntryMode').value==='g'?'alcoholGrams':drink?'volume':'amount');$('amount').required=drink||!!editing;$('caffeineInput').required=kind==='coffee';$('abv').required=kind==='alcohol'&&$('alcoholEntryMode').value!=='g';$('photo').required=kind==='picture';$('description').required=['text','barcode'].includes(kind);if(clear){searchSequence++;reusedVia=null;selected=null;$('selected').textContent='';$('results').replaceChildren();}renderMealRecipeChoices();}
$('lang').onchange=()=>{lang=$('lang').value;localStorage.setItem('frissLanguage',lang);translate();};$('logout').onclick=async()=>{try{await api('/auth/logout',{method:'POST'});signout();}catch(e){message(e.message,true);}};$('refresh').onclick=refresh;$('day').onchange=refresh;$('kind').onchange=()=>kindChange();
$('loginForm').onsubmit=async e=>{e.preventDefault();try{await api('/auth/login',{method:'POST',body:JSON.stringify({password:$('key').value})});$('key').value='';$('dashboard').hidden=false;$('login').hidden=true;$('logout').hidden=false;await refresh();}catch(error){message(error.message,true);}};

function reset(){importedBasis=null;editing=null;attempt=null;$('kind').disabled=false;$('destination').disabled=false;$('entryForm').reset();$('cancel').hidden=true;$('formTitle').textContent=t('add');now();kindChange();$('destination').value=recipePage()?activeRecipe:'';}
$('cancel').onclick=reset;
$('entryForm').onsubmit=async event=>{event.preventDefault();const k=$('kind').value;if(attempt?.recipe||(['recipe','drink_recipe'].includes(k)||k==='item'&&selected?.source==='recipe')&&!attempt){await submitMealRecipe(event);return;}const drink=['water','coffee','alcohol'].includes(k);if(!attempt){if(['item','off'].includes(k)&&!selected){message(t('select'),true);return;}if(k==='picture'&&!$('photo').files[0]){message(t('photoMissing'),true);return;}const quantity=$('amount').value?{value:Number($('amount').value),unit:drink?k==='alcohol'&&$('alcoholEntryMode').value==='g'?'g':'ml':importedBasis==='100ml'?'ml':'g'}:null;const body={id:uuid(),type:drink?'drink':k==='off'?'barcode':k,timestamp:new Date($('time').value).toISOString(),quantity};if($('entryFinish').value)body.finished_at=new Date($('entryFinish').value).toISOString();if(recipePage()){if(!activeRecipe){message(t('chooseRecipe'),true);return;}body.recipe_id=activeRecipe;}if(k==='manual')body.manual_id=$('manualCaptureSelect').value;if(reusedVia)body.capture_method=reusedVia;if(k==='item'){if(selected.source==='manual'){body.type='manual';body.manual_id=selected.id;}else if(selected.source==='off'){body.type='barcode';body.barcode=selected.id;}else body.bls_code=selected.id||selected.bls_code;}if(k==='off')body.barcode=selected.barcode;if(k==='text')body.description=$('description').value;if(k==='barcode')body.barcode=$('description').value.trim();if(drink)body.drink=k;if(k==='coffee')body.caffeine_mg=Number($('caffeineInput').value);if(k==='alcohol'&&$('alcoholEntryMode').value!=='g')body.alcohol_abv=Number($('abv').value);attempt={body,file:k==='picture'?$('photo').files[0]:null,editing};}
$('save').disabled=true;try{const a=attempt;if(a.editing){await api('/entries/'+a.editing+'/resolve',{method:'POST',body:JSON.stringify({bls_code:a.body.bls_code,quantity:a.body.quantity,timestamp:a.body.timestamp,finished_at:a.body.finished_at??null,barcode:a.body.barcode,description:a.body.description,caffeine_mg:a.body.caffeine_mg,alcohol_abv:a.body.alcohol_abv})});}else{await api('/entries',{method:'POST',body:JSON.stringify(a.body)});if(a.file)await api('/entries/'+a.body.id+'/photo',{method:'PUT',body:a.file});}reset();await refresh();message(t('saved'));}catch(e){$('cancel').hidden=false;message(t('retry')+' '+e.message,true);}finally{$('save').disabled=false;}};
$('day').value=localDate(new Date());now();translate();$('logout').hidden=true;sessionStorage.removeItem('frissKey');(async()=>{try{await api('/health');$('dashboard').hidden=false;$('login').hidden=true;$('logout').hidden=false;await refresh();}catch{}})();

Object.assign(words.de,{duplicateRecipe:'Rezept duplizieren',recipeCopySuffix:' (Kopie)',recipeDuplicateRetry:'Übertragung unklar. Erneut duplizieren wiederholt denselben Vorgang ohne weitere Kopie.'});
Object.assign(words.en,{duplicateRecipe:'Duplicate recipe',recipeCopySuffix:' (copy)',recipeDuplicateRetry:'Transfer uncertain. Duplicate again to retry without another copy.'});
let recipeDuplicateAttempt=null,recipeDuplicateBusy=false;
$('duplicateRecipe').onclick=async()=>{
 if(!activeRecipe||recipeDuplicateBusy)return;
 const source=recipeRows.find(r=>r.id===activeRecipe);if(!source)return;
 recipeDuplicateAttempt??={source:source.id,id:uuid(),name:source.name.slice(0,190)+t('recipeCopySuffix')};
 const attempt=recipeDuplicateAttempt;recipeDuplicateBusy=true;$('duplicateRecipe').disabled=true;$('recipeSelect').disabled=true;$('newRecipe').disabled=true;
 try{
 const result=await api('/recipes/'+attempt.source+'/duplicate',{method:'POST',body:JSON.stringify({id:attempt.id,name:attempt.name})});
 if(recipeDuplicateAttempt!==attempt||$('dashboard').hidden)return;
 recipeDuplicateAttempt=null;activeRecipe=result.id;await refresh();$('recipeSelect').value=result.id;chooseRecipe();$('recipeName').focus();message(t('saved'));
 }catch(e){if([400,404,409,422].includes(e.status)){recipeDuplicateAttempt=null;message(e.message,true);}else message(t('recipeDuplicateRetry')+' '+e.message,true);}
 finally{recipeDuplicateBusy=false;$('duplicateRecipe').disabled=!activeRecipe;$('recipeSelect').disabled=!!recipeDuplicateAttempt;$('newRecipe').disabled=!!recipeDuplicateAttempt;}
};
window.addEventListener('friss-logout',()=>{recipeDuplicateAttempt=null;$('recipeSelect').disabled=false;$('newRecipe').disabled=false;});
Object.assign(words.de,{drinkIntake:'Getränk trinken',chooseDrink:'Getränk auswählen',drinkConsumedAmount:'Getrunkene Menge',foodRecipeSource:'Lebensmittelrezepte',drinkRecipeSource:'Getränke'});
Object.assign(words.en,{drinkIntake:'Drink a beverage',chooseDrink:'Choose drink',drinkConsumedAmount:'Amount drunk',foodRecipeSource:'Food recipes',drinkRecipeSource:'Drinks'});
function intakeCategory(){return $('kind').value==='drink_recipe'||$('kind').value==='item'&&selected?.source==='recipe'&&selected.category==='drink'?'drink':'food';}
function renderMealRecipeChoices(){
 const previous=$('mealRecipe').value,category=intakeCategory();$('mealRecipe').replaceChildren();
 const blank=document.createElement('option');blank.value='';blank.textContent='—';$('mealRecipe').append(blank);
 for(const r of recipeRows){if((r.category||'food')!==category)continue;const option=document.createElement('option');option.value=r.id;option.textContent=r.name;$('mealRecipe').append(option);}
 $('mealRecipe').value=recipeRows.some(r=>r.id===previous&&(r.category||'food')===category)?previous:'';
 $('mealRecipeLabel').textContent=t(category==='drink'?'chooseDrink':'chooseRecipe');$('mealRecipeAmountLabel').textContent=t(category==='drink'?'drinkConsumedAmount':'intakeAmount');
}
function renderRecipes(){
 const destination=$('destination').value; $('destination').replaceChildren();const daily=document.createElement('option');daily.value='';daily.textContent=t('daily');$('destination').append(daily);
 $('recipeSelect').replaceChildren();const blank=document.createElement('option');blank.value='';blank.textContent='—';$('recipeSelect').append(blank);
 for(const r of recipeRows){for(const target of [$('destination'),$('recipeSelect')]){if(target===$('recipeSelect')&&(r.category||'food')!==recipeCategory())continue;const option=document.createElement('option');option.value=r.id;option.textContent=r.name;target.append(option);}}
 $('destination').value=destination; $('recipeSelect').value=activeRecipe;renderMealRecipeChoices();updateMealRecipeInfo();
 $('recipeEditorTitle').setAttribute('data-i',recipeCategory()==='drink'?'drinkRecipes':'recipes');$('recipeEditorTitle').textContent=t(recipeCategory()==='drink'?'drinkRecipes':'recipes');
 $('recipeAmend').hidden=!activeRecipe;$('migrateRecipe').hidden=!activeRecipe;$('migrateRecipe').textContent=t(recipeCategory()==='drink'?'migrateFood':'migrateDrink');$('drinkDefinitionFields').hidden=recipeCategory()!=='drink';$('logDefinedDrink').hidden=recipeCategory()!=='drink'||!activeRecipe;
 $('duplicateRecipe').disabled=!activeRecipe||recipeDuplicateBusy;
 const r=recipeRows.find(r=>r.id===activeRecipe);$('recipeInfo').textContent=r?`${t('ingredients')}: ${r.ingredients.length} · ${t(r.status)} · ${formatNumber(r.servings)} ${t('portions')}`:'';
 if(recipePage()){$('entryPanel').hidden=!r;$('entriesPanel').hidden=!r;}
 if(typeof renderQuickRecipeChoices==='function')renderQuickRecipeChoices();
 updatePageLabels();
}
function chooseRecipe(){activeRecipe=$('recipeSelect').value;recipeDraft=null;intakeAttempt=null;const r=recipeRows.find(r=>r.id===activeRecipe);$('recipeName').value=r?.name||'';$('servings').value=r?.servings||1;$('finishedWeight').value=r?.finished_weight_g||'';$('recipeNotes').value=r?.notes||'';$('recipeVolume').value=r?.finished_volume_ml||'';$('recipeABV').value=r?.alcohol_abv??'';$('recipeWater').value=r?.added_water_ml||0;$('recipeCaffeine').value=r?.added_caffeine_mg||0;$('recipeAlcohol').value=r?.added_ethanol_g||0;$('destination').value=recipePage()?activeRecipe:'';renderRecipes();render();}
$('recipeSelect').onchange=chooseRecipe;
$('newRecipe').onclick=()=>{$('recipeSelect').value='';chooseRecipe();$('recipeName').focus();};
$('recipeForm').onsubmit=async event=>{event.preventDefault();const button=event.submitter;button.disabled=true;try{const amend=button.id==='recipeAmend';if(amend&&!confirm(t('confirmAmend')))return;const body={category:recipeCategory(),finished_volume_ml:$('recipeVolume').value?Number($('recipeVolume').value):null,alcohol_abv:recipeCategory()==='drink'&&$('recipeABV').value!==''?Number($('recipeABV').value):null,name:$('recipeName').value,servings:Number($('servings').value),finished_weight_g:$('finishedWeight').value?Number($('finishedWeight').value):null,notes:$('recipeNotes').value,added_water_ml:Number($('recipeWater').value),added_caffeine_mg:Number($('recipeCaffeine').value),added_ethanol_g:Number($('recipeAlcohol').value)};let amended=0;if(activeRecipe){const result=await api('/recipes/'+activeRecipe,{method:'PUT',body:JSON.stringify({...body,amend_existing:amend})});amended=result.amended_entries;}else{recipeDraft=recipeDraft||uuid();await api('/recipes',{method:'POST',body:JSON.stringify({id:recipeDraft,...body})});activeRecipe=recipeDraft;recipeDraft=null;}$('destination').value=recipePage()?activeRecipe:'';await refresh();$('destination').value=recipePage()?activeRecipe:'';message(t('saved')+(amend?' · '+t('amendedCount')+': '+amended:''));}catch(e){message(e.message,true);}finally{button.disabled=false;}};
$('migrateRecipe').onclick=async()=>{
 if(!activeRecipe||!confirm(t('confirmMigrate')))return;
 const button=$('migrateRecipe');button.disabled=true;
 try{const target=recipeCategory()==='food'?'drink':'food';const id=activeRecipe;await api('/recipes/'+id+'/category',{method:'PATCH',body:JSON.stringify({category:target})});await refresh();location.hash=target==='drink'?'alcohol':'recipes';showPage(target==='drink'?'alcohol':'recipes');activeRecipe=id;$('recipeSelect').value=id;chooseRecipe();message(t('saved'));}catch(e){message(e.message,true);}finally{button.disabled=false;}
};
$('logDefinedDrink').onclick=()=>{const id=activeRecipe;location.hash='meals';showPage('meals');$('kind').value='drink_recipe';kindChange();$('mealRecipe').value=id;$('mealRecipeUnit').value='portion';$('mealRecipeAmount').value=1;updateMealRecipeInfo();$('entryPanel').scrollIntoView({behavior:'smooth'});};
$('destination').parentElement.querySelector('label[for="destination"]').hidden=true;$('destination').hidden=true;
function updatePageLabels(){ $('formTitle').textContent=editing?t('resolve'):recipePage()?t('ingredients'):t('add');$('listTitle').textContent=recipePage()?t('ingredients'):t('entries'); }
function showPage(page){
 const detailId=page.startsWith('entry/')?page.slice(6):null;if(detailId)page='entry';
 if(!['home','meals','recipes','alcohol','settings','statistics','health','entry','favorites','manual'].includes(page))page='home';
 if(page!==currentPage&&attempt){message(t('retry'),true);return;}
 if(page!==currentPage&&editing)reset();
 currentPage=page;
 for(const name of ['home','meals','recipes','alcohol','settings','statistics','health','entry','favorites','manual'])$('page-'+name).hidden=name!==page;
 document.querySelectorAll('[data-page]').forEach(b=>{b.setAttribute('aria-current',(b.dataset.page===page||(page==='entry'&&b.dataset.page==='meals'))?'page':'false');});
 if(page==='recipes'||page==='alcohol'){if(activeRecipe&&(recipeRows.find(r=>r.id===activeRecipe)?.category||'food')!==recipeCategory()){activeRecipe='';$('recipeForm').reset();$('recipeName').value='';$('recipeVolume').value='';$('recipeABV').value='';}$(page==='alcohol'?'drinkRecipeEditorHost':'foodRecipeEditorHost').append($('recipeEditor'),$('recipeCaptureHost'));renderRecipes();}
 const host=recipePage()?$('recipeCaptureHost'):$('mealCaptureHost');host.append($('entryPanel'),$('entriesPanel'));
 $('destination').value=recipePage()?activeRecipe:'';
 $('entryPanel').hidden=recipePage()&&!activeRecipe;$('entriesPanel').hidden=recipePage()&&!activeRecipe;
 $('dayControls').hidden=page!=='meals';kindChange(false);updatePageLabels();render();window.dispatchEvent(new CustomEvent('friss-page',{detail:page}));if(page==='entry'&&typeof loadEntryDetails==='function')loadEntryDetails(detailId);
}
for(const button of document.querySelectorAll('[data-page]'))button.onclick=()=>{location.hash=button.dataset.page;};
window.addEventListener('hashchange',()=>showPage(location.hash.slice(1)));
$('mealRecipe').onchange=updateMealRecipeInfo;
$('mealRecipeUnit').onchange=()=>{$('mealRecipeAmount').max=$('mealRecipeUnit').value==='fraction'?'1':'';updateMealRecipeInfo();};
function updateMealRecipeInfo(){
 const recipe=recipeRows.find(r=>r.id===$('mealRecipe').value);
 $('mealRecipeInfo').textContent=recipe?formatNumber(recipe.servings)+' '+t('portions')+' · '+t(recipe.status)+(recipe.finished_weight_g?' · '+formatNumber(recipe.finished_weight_g)+' g':''):'';
}
async function submitMealRecipe(event){
 if(!attempt){
 const recipe=recipeRows.find(r=>r.id===$('mealRecipe').value);
 if(!recipe){message(t('chooseRecipe'),true);return;}
 if((recipe.category||'food')!==intakeCategory()){message(t('chooseRecipe'),true);return;}
 if(recipe.status!=='ready'){message(t('recipeHint'),true);return;}
 if($('mealRecipeUnit').value==='g'&&!recipe.finished_weight_g){message(t('finishedWeight'),true);return;}
 attempt={recipe:recipe.id,body:{id:uuid(),timestamp:new Date($('time').value).toISOString(),unit:$('mealRecipeUnit').value,amount:Number($('mealRecipeAmount').value),finished_at:$('entryFinish').value?new Date($('entryFinish').value).toISOString():null}};
 }
 $('save').disabled=true;
 try{await api('/recipes/'+attempt.recipe+'/intake',{method:'POST',body:JSON.stringify(attempt.body)});reset();await refresh();message(t('saved'));}
 catch(e){$('cancel').hidden=false;message(t('retry')+' '+e.message,true);}finally{$('save').disabled=false;}
}
const originalChooseRecipe=chooseRecipe;
chooseRecipe=function(){originalChooseRecipe();showPage(currentPage);};
showPage(location.hash.slice(1));
$('recipeSelect').onchange=()=>chooseRecipe();

Object.assign(words.de,{searchLearningError:'Auswahl übernommen, Suchsortierung konnte nicht gespeichert werden.'});
Object.assign(words.en,{searchLearningError:'Selection filled in, but search preference could not be saved.'});
async function rememberFoodSelection(query,code,searchLang){
 const body={id:uuid(),query,bls_code:code,lang:searchLang};
 try{await api('/food-search/selections',{method:'POST',body:JSON.stringify(body)});}
 catch(e){if(!$('dashboard').hidden)message(t('searchLearningError')+' '+e.message,true);}
}

function resumeEntry(e){
 if(attempt){message(t('retry'),true);return;}
 searchSequence++;reset();editing=e.id;
 const code=e.bls_code||e.food?.bls_code;
 importedBasis=e.imported_nutrition&&!code?e.imported_nutrition.basis:null;
 const kind=importedBasis?'text':e.type==='manual'?'manual':e.type==='drink'?e.drink:code?'item':e.type==='barcode'?'barcode':'item';
 $('kind').value=kind;$('alcoholEntryMode').value=kind==='alcohol'&&e.quantity?.unit==='g'?'g':'ml';$('kind').disabled=true;$('destination').disabled=true;kindChange();
 const label=e.food?.['name_'+lang]||e.food?.product_name||e.description||e.barcode||code||'';
 if(e.type==='manual'){if(typeof restoreManualSelection==='function')restoreManualSelection(e);$('manualCaptureSelect').disabled=true;}
 if(code){selected={...(e.food||{}),bls_code:code,display_name:label};$('selected').textContent=label;$('search').value=label;}
 else{$('search').value=e.description||'';$('selected').textContent=e.food?.product_name||'';}
 if(importedBasis)$('amountLabel').textContent=t(importedBasis==='100ml'?'volume':'amount');
 $('description').value=e.type==='barcode'?e.barcode||'':e.description||'';
 if(e.finished_at){const end=new Date(e.finished_at);$('entryFinish').value=new Date(end-end.getTimezoneOffset()*60000).toISOString().slice(0,19);}
 $('amount').value=e.quantity?.value??'';$('caffeineInput').value=e.caffeine_mg??'';$('abv').value=e.alcohol_abv??'';
 const d=new Date(e.timestamp);$('time').value=localDate(d)+'T'+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')+':'+String(d.getSeconds()).padStart(2,'0')+(d.getMilliseconds()?'.'+String(d.getMilliseconds()).padStart(3,'0'):'');
 $('formTitle').textContent=t('resolve');$('cancel').hidden=false;$('entryPanel').scrollIntoView({behavior:'smooth',block:'start'});
 if(kind==='item'&&!selected)$('search').focus();else if(!$('amount').value)$('amount').focus();else if(kind==='coffee'&&!$('caffeineInput').value)$('caffeineInput').focus();else if(kind==='alcohol'&&!$('abv').value)$('abv').focus();else $('amount').focus();
}

$('alcoholEntryMode').onchange=()=>kindChange(false);

