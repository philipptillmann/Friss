const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map(),listeners={};
const $=id=>{if(!elements.has(id))elements.set(id,{disabled:false,hidden:false,value:'',focus(){}});return elements.get(id)};
let calls=[],fail=true,chosen=false;
const context=vm.createContext({$,words:{de:{},en:{}},t:k=>k==='recipeCopySuffix'?' (copy)':k,activeRecipe:'source',recipeRows:[{id:'source',name:'Soup'}],uuid:()=> 'duplicate-id',window:{addEventListener:(n,f)=>listeners[n]=f},refresh:async()=>{},chooseRecipe(){chosen=true},message(){},api:async(path,options)=>{calls.push({path,body:JSON.parse(options.body)});if(fail){fail=false;throw Error('Lost response')}return {id:'duplicate-id'}}});
const source=fs.readFileSync('app/static/app.js','utf8');
vm.runInContext(source.slice(source.indexOf('Object.assign(words.de,{duplicateRecipe:'),source.indexOf('function renderRecipes()')),context);
(async()=>{
 await $('duplicateRecipe').onclick();assert.equal($('recipeSelect').disabled,true);
 context.recipeRows[0].name='Changed source';await $('duplicateRecipe').onclick();
 assert.deepEqual(calls[0],calls[1]);assert.equal(calls[0].body.name,'Soup (copy)');
 assert.equal(context.activeRecipe,'duplicate-id');assert.equal(chosen,true);
 assert.equal($('recipeSelect').disabled,false);console.log('Recipe duplication UI: stable retry and editing the new recipe passed');
})().catch(e=>{console.error(e);process.exitCode=1});
