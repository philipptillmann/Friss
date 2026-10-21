const fs=require('fs'),vm=require('vm'),assert=require('assert');
const els=new Map();function element(tag){return {tag,value:'',children:[],append(...nodes){this.children.push(...nodes)},replaceChildren(...nodes){this.children=nodes},setAttribute(){}}}const $=id=>{if(!els.has(id))els.set(id,element('div'));return els.get(id)};
const app=fs.readFileSync('app/static/app.js','utf8'),home=fs.readFileSync('app/static/home.js','utf8');
const context=vm.createContext({$,document:{createElement:element},recipeRows:[{id:'legacy-drink',category:'drink'}],t:k=>k,rows:[],recipePage:()=>false,formatNumber:String,lang:'de'});
vm.runInContext(app.slice(app.indexOf('// Shared source badges'),app.indexOf('// End shared source badges')),context);
vm.runInContext(home.match(/const standardKeys=.*\n/)[0]+home.match(/function compareHomeNutrients.*\n/)[0],context);
function badge(entry,expected,label){context.entry=entry;const result=vm.runInContext('entrySourceBadge(entry)',context);assert.equal(result.className,'sourceBadge source-'+expected);assert.equal(result.textContent,label)}
badge({type:'item',bls_code:'BLS'},'bls','sourceBLS');
badge({type:'picture',food:{bls_code:'BLS'}},'bls','sourceBLS');
badge({type:'barcode',source:{provider:'Open Food Facts'}},'off','sourceOFF');
badge({type:'manual',capture_method:'favorite'},'manual','sourceManual');
badge({type:'text',imported_nutrition:{},capture_method:'json_import'},'ai','sourceAI');
badge({type:'recipe',source:{provider:'BLS'},recipe_snapshot:{category:'food'}},'recipe','sourceRecipe');
badge({type:'recipe',source:{provider:'BLS'},recipe_snapshot:{category:'drink'}},'drink','sourceDrink');
badge({type:'recipe',source:{recipe_id:'legacy-drink'}},'drink','sourceDrink');
badge({type:'drink',drink:'coffee'},'drink','sourceDrink');
badge({type:'picture'},'unknown','sourceUnknown');
// Meal overview renders the badge using the shared implementation.
context.rows=[{id:'meal',type:'manual',food:{name_de:'Milch'},quantity:{value:90,unit:'g'},timestamp:'2026-10-21T08:00:00Z',status:'processed',health_status:'pending'}];
vm.runInContext(app.slice(app.indexOf('function render(){'),app.indexOf('\n',app.indexOf('function render(){'))),context);vm.runInContext('render()',context);
assert.equal($('entries').children[0].children[0].children[1].className,'sourceBadge source-manual');
// Shared Home/detail ordering includes virtual water/alcohol positions and unchanged unknown keys.
context.keys=['dietaryVitaminC','dietaryCaffeine','ethanol_g','dietaryWater','dietaryCarbohydrates','drinking_water_ml','dietaryFatTotal','dietaryProtein','dietaryEnergyConsumed','dietaryCalcium'];
assert.deepEqual(Array.from(vm.runInContext('keys.sort(compareHomeNutrients)',context)),['dietaryEnergyConsumed','dietaryProtein','dietaryCarbohydrates','dietaryFatTotal','drinking_water_ml','dietaryCaffeine','ethanol_g','dietaryCalcium','dietaryVitaminC','dietaryWater']);
console.log('Entry presentation: shared source colors, recipe snapshots, legacy entries, meal badges and Home nutrient order passed');
