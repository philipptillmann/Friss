const fs=require('fs'),vm=require('vm'),assert=require('assert');
const els=new Map();const $=id=>{if(!els.has(id))els.set(id,{value:'',hidden:false,disabled:false,children:[],append(...n){this.children.push(...n)},replaceChildren(...n){this.children=n},reset(){},removeAttribute(){},getAttribute(k){return this[k]}});return els.get(id)};
let entry={id:'ingredient',recipe_id:'drink',type:'item',quantity:{value:90,unit:'g'},revision:1,food:{name_en:'Milk'},timestamp:'2026-10-18T10:00:00Z',status:'processed',health_status:'pending',contributions:{dietaryEnergyConsumed:{value:56,unit:'kcal'}}},calls=[];
$('dashboard').hidden=true;
const ctx=vm.createContext({$,words:{de:{},en:{}},lang:'en',t:k=>k,recipeRows:[{id:'drink',category:'drink'}],activeRecipe:null,document:{createElement:()=>({}),documentElement:{}},window:{addEventListener(){}},location:{hash:'#entry/ingredient'},currentPage:'entry',MutationObserver:class{observe(){}},localDate:d=>d.toISOString().slice(0,10),formatHome:String,tableRow:(target,k,v)=>target.append({k,v}),nutrientLabel:x=>x,translate(){},message(){},refresh:async()=>{},api:async(path,options)=>{if(!options)return entry;const body=JSON.parse(options.body);calls.push({path,body});entry={...entry,quantity:body.quantity,revision:2,contributions:{dietaryEnergyConsumed:{value:112,unit:'kcal'}}};return entry;}});
vm.runInContext(fs.readFileSync('app/static/entry-details.js','utf8'),ctx);
(async()=>{
 $('dashboard').hidden=false;await vm.runInContext("loadEntryDetails('ingredient')",ctx);
 assert.equal($('detailAmount').value,90);assert.equal($('detailBack').href,'#alcohol');assert.equal(ctx.activeRecipe,'drink');assert.equal($('detailCopyForm').hidden,true);assert.equal($('detailNutrientsTitle').textContent,'ingredientNutrients');assert.equal($('detailMetadata').children.some(n=>n.textContent==='healthState'),false);
 $('detailAmount').value=180;await $('detailAmountForm').onsubmit({preventDefault(){}});
 assert.equal(calls[0].path,'/entries/ingredient/amount');assert.deepEqual(calls[0].body,{quantity:{value:180,unit:'g'},revision:1});assert.equal($('detailNutrients').children[0].v,'112 kcal');
 console.log('Entry amount UI: recipe context, nutrients, amount edit and updated contribution passed');
})().catch(e=>{console.error(e);process.exitCode=1});
