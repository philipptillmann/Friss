const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map();
function element(){return {value:'',hidden:false,children:[],textContent:'',append(...nodes){this.children.push(...nodes)},replaceChildren(...nodes){this.children=[...nodes]},setAttribute(){},addEventListener(){},showModal(){this.open=true},close(){this.open=false},reset(){}}}
const $=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id)};
$('dashboard').hidden=true;
const context=vm.createContext({$,words:{de:{},en:{}},lang:'de',t:k=>k,document:{createElement:element,createElementNS:element,documentElement:{}},window:{addEventListener(){},dispatchEvent(){}},Event:class {},MutationObserver:class {observe(){}},setInterval(){},translate(){},recipeRows:[],currentPage:'home',localDate:()=> '2026-10-11',message(){},api:null,console});
vm.runInContext(fs.readFileSync('app/static/home.js','utf8'),context);
const summary={nutrients:[{key:'dietaryEnergyConsumed',values:[{value:1000,unit:'kcal'}],total:1,partial:false,qualifiers:[],contributors:[{id:'meal',name_de:'Test meal',timestamp:'2026-10-12T12:00:00Z',type:'manual',quantity:{value:100,unit:'g'},values:[{value:1000,unit:'kcal'}]}]}],unresolved:0,caffeine_mg:0,ethanol_g:0,drinking_water_ml:0};
(async()=>{
 let prefs={version:0,buttons:[],bac:null,goals:null},release;
 context.api=async(path,options)=>{
  if(path.startsWith('/home-summary'))return {...summary,missing_nutrients_as_zero:!!prefs.missing_nutrients_as_zero};
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
 $('goalProgress').children[0].children[1].children[0].onclick();
 assert.equal($('homeContributors').open,true);assert.equal($('homeContributorsList').children[0].href,'#entry/meal');
 $('homeContributorsClose').onclick();assert.equal($('homeContributors').open,false);
 context.api=initialAPI;
 context.refresh=async()=>vm.runInContext('loadHome()',context);
 await vm.runInContext('loadHome()',context);
 assert.equal(vm.runInContext('homePreferences.goals.energy_kcal',context),2000);
 $('missingValuesZero').checked=true;await $('missingValuesForm').onsubmit({preventDefault(){},submitter:element()});
 assert.equal(vm.runInContext('homePreferences.missing_nutrients_as_zero',context),true);assert.equal($('homeZeroHint').hidden,false);
 $('missingValuesZero').checked=false;await $('missingValuesForm').onsubmit({preventDefault(){},submitter:element()});
 assert.equal(vm.runInContext('homePreferences.missing_nutrients_as_zero',context),false);assert.equal($('homeZeroHint').hidden,true);
 console.log('Goal form save, progress display and delayed refresh checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
