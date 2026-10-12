const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map();
function element(){return {value:'',hidden:false,children:[],textContent:'',append(...nodes){this.children.push(...nodes)},replaceChildren(...nodes){this.children=[...nodes]},setAttribute(){},reset(){}}}
const $=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id)};
$('dashboard').hidden=true;
const context=vm.createContext({$,words:{de:{},en:{}},lang:'de',t:k=>k,document:{createElement:element,createElementNS:element,documentElement:{}},window:{addEventListener(){},dispatchEvent(){}},Event:class {},MutationObserver:class {observe(){}},setInterval(){},translate(){},recipeRows:[],currentPage:'home',localDate:()=> '2026-10-11',message(){},api:null,console});
vm.runInContext(fs.readFileSync('app/static/home.js','utf8'),context);
const summary={nutrients:[{key:'dietaryEnergyConsumed',values:[{value:1000,unit:'kcal'}],total:1,partial:false,qualifiers:[]}],unresolved:0,caffeine_mg:0,ethanol_g:0,drinking_water_ml:0};
(async()=>{
 let prefs={version:0,buttons:[],bac:null,goals:null},release;
 context.api=async(path,options)=>{
  if(path.startsWith('/home-summary'))return summary;
  if(options?.method==='PUT'){prefs={...JSON.parse(options.body),version:prefs.version+1};return structuredClone(prefs)}
  return structuredClone(prefs);
 };
 $('dashboard').hidden=false;
 await vm.runInContext('loadHome()',context);
 // A refresh started before the save must not overwrite the saved targets.
 const initialAPI=context.api;
 context.api=async(path,options)=>path==='/settings'&&!options?new Promise(resolve=>release=()=>resolve({version:0,buttons:[],bac:null,goals:null})):initialAPI(path,options);
 const pending=vm.runInContext('loadHome()',context);
 $('goalEnergy').value='2000';
 await $('goalsForm').onsubmit({preventDefault(){},submitter:element()});
 release();await pending;
 assert.equal(vm.runInContext('homePreferences.goals?.energy_kcal',context),2000,'late refresh must retain the saved calorie target');
 assert.match($('goalProgress').children[0].children[1].textContent,/2[.\s]?000 kcal/);
 assert.equal($('goalProgress').children[0].children[2].max,2000);
 assert.equal($('goalProgress').children[0].children[2].value,1000);
 context.api=initialAPI;
 await vm.runInContext('loadHome()',context);
 assert.equal(vm.runInContext('homePreferences.goals.energy_kcal',context),2000);
 console.log('Goal form save, progress display and delayed refresh checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
