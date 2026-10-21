const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map(),listeners={};
const $=id=>{if(!elements.has(id))elements.set(id,{value:'',hidden:false,disabled:false,children:[],append(...n){this.children.push(...n)},replaceChildren(...n){this.children=n},reset(){},removeAttribute(){}});return elements.get(id)};
let calls=[],fail=true;
const entry={id:'source',type:'drink',drink:'water',timestamp:'2026-10-14T10:00:00Z',quantity:{value:250,unit:'ml'},health_status:'synced',status:'processed',contributions:{}};
const context=vm.createContext({$,words:{de:{},en:{}},lang:'en',t:x=>x,document:{createElement:()=>({}),documentElement:{}},window:{addEventListener:(n,f)=>listeners[n]=f},location:{hash:'#entry/source'},currentPage:'entry',recipeRows:[],MutationObserver:class{observe(){}},localDate:d=>d.toISOString().slice(0,10),formatHome:String,tableRow(){},nutrientLabel:x=>x,translate(){},message(){},uuid:()=> 'copy-id',refresh:async()=>{},api:async(path,options)=>{if(!options)return entry;calls.push(JSON.parse(options.body));if(fail){fail=false;throw Error('Lost response')}return {id:'copy-id'};}});
const homeSource=fs.readFileSync('app/static/home.js','utf8');
vm.runInContext(homeSource.match(/const standardKeys=.*\n/)[0]+homeSource.match(/function compareHomeNutrients.*\n/)[0],context);
vm.runInContext(fs.readFileSync('app/static/entry-details.js','utf8'),context);
(async()=>{
 await vm.runInContext("loadEntryDetails('source')",context);
 assert.equal($('detailCopyForm').hidden,false);
 $('detailCopyTime').value='2026-10-15T18:00:00';
 await $('detailCopyForm').onsubmit({preventDefault(){}});
 assert.equal($('detailCopyTime').disabled,true);
 $('detailCopyTime').value='2026-10-16T18:00:00';
 await $('detailCopyForm').onsubmit({preventDefault(){}});
 assert.deepEqual(calls[1],calls[0]);assert.equal(calls[0].id,'copy-id');
 assert.equal(context.location.hash,'entry/copy-id');
 assert.equal($('day').value,'2026-10-15');
 listeners['friss-logout']();assert.equal($('detailCopyForm').hidden,true);
 console.log('Entry copy UI: target time, duplicate-safe retry and logout passed');
})().catch(e=>{console.error(e);process.exitCode=1});

