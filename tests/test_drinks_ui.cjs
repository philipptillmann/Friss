const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map();const $=id=>{if(!elements.has(id))elements.set(id,{value:'',hidden:false,disabled:false,children:[],append(...n){this.children.push(...n)},replaceChildren(...n){this.children=n},setAttribute(){},focus(){}});return elements.get(id)};
function element(){return {value:'',textContent:''}}
let sent=[],confirmed=true;
const context=vm.createContext({$,document:{createElement:element},recipeRows:[{id:'food',name:'Soup',ingredients:[],servings:1},{id:'drink',name:'Coffee',category:'drink',ingredients:[],servings:1}],currentPage:'alcohol',activeRecipe:'drink',recipeCategory:()=>context.currentPage==='alcohol'?'drink':'food',recipePage:()=>true,recipeDuplicateBusy:false,lang:'en',t:k=>k,formatNumber:String,updateMealRecipeInfo(){},updatePageLabels(){},render(){},refresh:async()=>{},message(){},confirm:()=>confirmed,api:async(path,options)=>{sent.push({path,body:JSON.parse(options.body)});return {amended_entries:2}},recipeDraft:null,uuid:()=> 'new',intakeAttempt:null});
const source=fs.readFileSync('app/static/app.js','utf8');
const render=source.slice(source.indexOf('function intakeCategory(){'),source.indexOf('function chooseRecipe(){'));
vm.runInContext(render,context);vm.runInContext('renderRecipes()',context);
assert.equal($('recipeSelect').children.length,2);assert.equal($('recipeSelect').children[1].value,'drink');assert.equal($('destination').children.length,3);
assert.equal($('drinkDefinitionFields').hidden,false);
const handler=source.slice(source.indexOf("$('recipeForm').onsubmit="),source.indexOf("$('migrateRecipe').onclick="));vm.runInContext(handler,context);
$('recipeName').value='Coffee';$('servings').value='1';$('recipeVolume').value='200';$('recipeABV').value='0';$('recipeWater').value='0';$('recipeCaffeine').value='80';$('recipeAlcohol').value='0';
(async()=>{
 const event={preventDefault(){},submitter:{id:'recipeAmend',disabled:false}};confirmed=false;await $('recipeForm').onsubmit(event);assert.equal(sent.length,0);
 confirmed=true;await $('recipeForm').onsubmit(event);assert.equal(sent[0].body.amend_existing,true);assert.equal(sent[0].body.category,'drink');assert.equal(sent[0].body.finished_volume_ml,200);assert.equal(sent[0].body.alcohol_abv,0);
 await $('recipeForm').onsubmit({...event,submitter:{id:'future',disabled:false}});assert.equal(sent[1].body.amend_existing,false);
 console.log('Drinks UI: recipe category filtering, ABV/volume and confirmed save modes passed');
})().catch(e=>{console.error(e);process.exitCode=1});

