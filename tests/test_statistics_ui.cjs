const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map();function el(){return {value:'',children:[],attributes:{},append(...n){this.children.push(...n)},replaceChildren(...n){this.children=n},setAttribute(k,v){this.attributes[k]=v}}}
const $=id=>{if(!elements.has(id))elements.set(id,el());return elements.get(id)};
const context=vm.createContext({$,words:{de:{},en:{}},lang:'en',t:k=>k,nutrientLabel:k=>k,document:{createElement:el,createElementNS:el,querySelectorAll:()=>[],documentElement:{}},window:{addEventListener(){}},MutationObserver:class{observe(){}},localDate:d=>d.toISOString().slice(0,10),translate(){},currentPage:'home'});
vm.runInContext(fs.readFileSync('app/static/statistics.js','utf8'),context);
$('statsMetric').value='energy_kcal';$('statsInspect').value=0;
vm.runInContext(`statisticsData={logged_days:1,unresolved:0,timezone:'UTC',goals:{energy_kcal:2000},metric_definitions:{energy_kcal:{key:'dietaryEnergyConsumed',unit:'kcal'},dietaryVitaminC:{key:'dietaryVitaminC',unit:'mg'}},metrics:{energy_kcal:{average:100,total:100,days:1},dietaryVitaminC:{average:25,total:25,days:1}},days:[{date:'2026-10-14',entries:1,unresolved:0,values:{energy_kcal:100,dietaryVitaminC:25},partial:{}}]};renderStatistics()`,context);
assert.equal($('statsMetric').children.length,2);
let line=$('statsChart').children.find(n=>n.attributes['data-daily-goal']===2000);
assert.ok(line);assert.ok(line.attributes.y1>=30&&line.attributes.y1<=280,'goal must be inside chart even when larger than all bars');
$('statsMetric').value='dietaryVitaminC';$('statsMetric').onchange();
assert.equal($('statsChart').children.some(n=>n.attributes['data-daily-goal']),false);
assert.ok($('statsReadout').textContent.includes('25 mg'));assert.ok($('statsCards').children[0].children[0].textContent.includes('dietaryVitaminC'));
console.log('Statistics UI: all nutrient choices, selected values and visible goal line passed');
