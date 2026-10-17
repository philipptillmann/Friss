const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map();const $=id=>{if(!elements.has(id))elements.set(id,{value:'',hidden:false,textContent:'',children:[],replaceChildren(...n){this.children=n},append(...n){this.children.push(...n)}});return elements.get(id)};
let calls=[],pending=[],learned=0;
const context=vm.createContext({$,words:{de:{},en:{}},lang:'de',t:k=>k,reusedVia:null,selected:null,searchSequence:0,document:{createElement:()=>({})},clearTimeout(){pending=[]},setTimeout:f=>{pending.push(f)},rememberFoodSelection(){learned++},message(){},api:async path=>{calls.push(path);return [{barcode:'4001234567890',display_name:'Hafermilch',brand:'Marke',package_quantity:'1 L'}]}});
const source=fs.readFileSync('app/static/app.js','utf8');
vm.runInContext(source.slice(source.indexOf("Object.assign(words.de,{offSearch:"),source.indexOf('\nfunction reset()')),context);
(async()=>{
 $('kind').value='off';$('search').value='H';$('search').oninput();assert.equal(pending.length,0);
 $('search').value='Hafer';$('search').oninput();assert.equal(calls.length,0);await pending[0]();
 assert.ok(calls[0].startsWith('/products/search?'));assert.ok($('results').children[0].textContent.includes('Marke'));
 $('results').children[0].onclick();assert.equal(context.selected.barcode,'4001234567890');assert.equal(learned,0);
 assert.ok(source.includes("if(k==='off')body.barcode=selected.barcode"));
 console.log('OFF search UI: debounce, product selection and barcode capture passed');
})().catch(e=>{console.error(e);process.exitCode=1});
