const fs=require('fs'),vm=require('vm'),assert=require('assert');
const els=new Map();const $=id=>{if(!els.has(id))els.set(id,{value:'',disabled:false,hidden:false,children:[],replaceChildren(...n){this.children=n},append(...n){this.children.push(...n)},setAttribute(){},addEventListener(){}});return els.get(id)};
let sent,fail=false;
const ctx=vm.createContext({$,words:{de:{},en:{}},lang:'en',t:k=>k,document:{createElement:()=>({}),documentElement:{}},window:{addEventListener(){},dispatchEvent(){}},Event:class{},MutationObserver:class{observe(){}},setInterval(){},translate(){},recipeRows:[],currentPage:'settings',message(){},api:async(path,options)=>{assert.equal(path,'/settings');sent=JSON.parse(options.body);if(fail)throw Error('Conflict');return {...sent,version:sent.version+1}}});$('dashboard').hidden=true;
vm.runInContext(fs.readFileSync('app/static/home.js','utf8'),ctx);
$('dashboard').hidden=false;
vm.runInContext("homePreferences={buttons:[{id:'a',label:'A',entry:{}},{id:'b',label:'B',entry:{}},{id:'c',label:'C',entry:{}}],version:4};renderHome=()=>{}",ctx);
(async()=>{
 $('quickSelect').value='b';await vm.runInContext('moveQuickButton(-1)',ctx);
 assert.deepEqual(sent.buttons.map(b=>b.id),['b','a','c']);assert.equal($('quickSelect').value,'b');assert.equal($('quickMoveUp').disabled,true);assert.equal($('quickMoveDown').disabled,false);
 await vm.runInContext('moveQuickButton(1)',ctx);assert.deepEqual(sent.buttons.map(b=>b.id),['a','b','c']);assert.equal(sent.version,5);
 fail=true;await vm.runInContext('moveQuickButton(1)',ctx);assert.equal(vm.runInContext('homePreferences.buttons.map(b=>b.id).join()',ctx),'a,b,c');assert.equal($('quickSelect').disabled,false);
 console.log('Quick order UI: persisted moves, selection, boundaries and failed-save recovery passed');
})().catch(e=>{console.error(e);process.exitCode=1});
