const fs=require('fs'),vm=require('vm'),assert=require('assert');
const els=new Map();const $=id=>{if(!els.has(id))els.set(id,{value:'',children:[],textContent:'',replaceChildren(...n){this.children=n},append(...n){this.children.push(...n)},setAttribute(){},addEventListener(){}});return els.get(id)};
const context=vm.createContext({$,words:{de:{},en:{}},lang:'de',t:k=>k,document:{createElement:()=>({}),documentElement:{}},window:{addEventListener(){}},MutationObserver:class{observe(){}},setInterval(){},translate(){},recipeRows:[],currentPage:'home'});$('dashboard').hidden=true;
vm.runInContext(fs.readFileSync('app/static/home.js','utf8'),context);
function show(state,goals){context.state=state;context.goals=goals;vm.runInContext('homeState=state;homePreferences={goals};renderHomeGoalSummary()',context);return $('homeGoalSummary').textContent}
const state={nutrients:[{key:'dietaryEnergyConsumed',values:[{value:1500,unit:'kcal'}],total:1}],unresolved:0};
assert.ok(show(state,{energy_kcal:2000}).includes('1.500 / 2.000 kcal · 75 %'));assert.ok($('homeGoalSummary').textContent.includes('500 kcal goalRemaining'));
assert.ok(show(state,{energy_kcal:1000}).includes('500 kcal goalExceeded'));
assert.equal(show(state,null),'homeGoalSetup');
assert.ok(show({nutrients:[{key:'dietaryProtein',values:[{value:40,unit:'g'}],total:1,partial:true}],unresolved:0},{protein_g:100}).includes('40 / 100 g · 40 %'));
assert.ok($('homeGoalSummary').textContent.includes('homeGoalKnown'));
assert.ok(show({nutrients:[{key:'dietaryEnergyConsumed',values:[],total:1}],unresolved:1},{energy_kcal:2000}).includes('homeGoalUnknown'));
assert.ok(show({nutrients:[],unresolved:0},{energy_kcal:2000}).includes('0 / 2.000 kcal'));
const html=fs.readFileSync('app/static/index.html','utf8'),home=html.slice(html.indexOf('<section id="page-home"'),html.indexOf('<section id="page-recipes"'));
assert.equal(home.includes('customQuickButtons'),false);assert.ok(home.includes('todayPanel'));assert.ok(home.indexOf('homeGoalSummary')<home.indexOf('homeBarcode'));assert.ok(html.includes('id="alcoholQuickButtons"'));
console.log('Home summary: goal progress, over-target, fallback goals, incomplete data and stats-first layout passed');
