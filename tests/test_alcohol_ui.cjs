const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map(),listeners={};
function element(){return {value:'',hidden:false,disabled:false,children:[],textContent:'',append(...nodes){this.children.push(...nodes)},replaceChildren(...nodes){this.children=[...nodes]},setAttribute(){},reset(){},reportValidity(){return true},addEventListener(){}}}
const $=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id)};
$('alcoholMode').value='ml';$('alcoholABV').value='5';
const posts=[];let fail=false,ids=0;
const profile={mass_kg:80,distribution:.68,elimination_percent_per_hour:.015,absorption_per_hour:3};
const preferences={version:1,buttons:[{id:'quick',label:'20 g',entry:{type:'drink',drink:'alcohol',quantity:{value:20,unit:'g'}}}]};
const context=vm.createContext({words:{de:{},en:{}},lang:'de',t:k=>k,document:{getElementById:$,createElement:element,createElementNS:element,documentElement:{}},window:{addEventListener(name,fn){listeners[name]=fn}},MutationObserver:class {observe(){}},setInterval(){},recipeRows:[],currentPage:'alcohol',localDate:d=>d.toISOString().slice(0,10),uuid:()=>String(++ids),confirm:()=>true,quickPictogram:()=>element(),deleteLoggedEntry(){},message(){},refresh:async()=>{},api:async(path,options)=>{
 if(options?.method==='POST'){posts.push({path,body:JSON.parse(options.body)});if(fail){fail=false;throw Error('network interrupted')}return {}}
 if(path==='/settings')return preferences;
 const params=new URL('http://test'+path).searchParams,start=params.get('start'),end=params.get('end');
 return {start,end,profile,entries:[],ethanol_g:0,current_bac:{percent:0},points:[{timestamp:start,bac_percent:0},{timestamp:end,bac_percent:0}]};
}});
vm.runInContext(fs.readFileSync('app/static/bac.js','utf8'),context);
(async()=>{
 $('alcoholMode').value='g';$('alcoholAmount').value='20';$('alcoholName').value='Test';$('alcoholTime').value='2026-10-12T18:15:00';
 $('alcoholFinish').value='2026-10-12T19:15:00';
 fail=true;const event={preventDefault(){},submitter:element()};
 await $('alcoholForm').onsubmit(event);
 assert.equal(posts[0].body.finished_at,'2026-10-12T19:15:00.000Z');assert.equal(posts[0].body.quantity.unit,'g');assert.equal(posts[0].body.quantity.value,20);assert.equal(posts[0].body.alcohol_abv,undefined);
 assert.equal($('alcoholTime').disabled,true);
 $('alcoholAmount').value='50';await $('alcoholForm').onsubmit(event);
 assert.deepEqual(posts[1].body,posts[0].body,'uncertain manual transfer must retry identical ID and input');
 assert.equal($('alcoholTime').disabled,false);
 $('alcoholMode').value='ml';$('alcoholAmount').value='500';$('alcoholABV').value='5';$('alcoholTime').value='2026-10-12T19:00:00';await $('alcoholForm').onsubmit(event);
 assert.equal(posts[2].body.alcohol_abv,5);assert.equal(posts[2].body.quantity.unit,'ml');
 $('alcoholTime').value='2026-10-12T20:00:00';
 const tile=$('alcoholQuickButtons').children[0];fail=true;await tile.onclick();await $('alcoholQuickButtons').children[0].onclick();
 assert.equal(posts[3].path,'/quick-buttons/quick/intake');assert.deepEqual(posts[4].body,posts[3].body);
 assert.ok(Math.abs(Date.now()-Date.parse(posts[3].body.timestamp))<10000,'quick add uses now instead of the manual-entry time');
 console.log('Alcohol journal UI: grams, ABV, custom times and idempotent manual/quick retries passed');
})().catch(e=>{console.error(e);process.exitCode=1});
