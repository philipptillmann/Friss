const fs=require('fs'),vm=require('vm'),assert=require('assert');
const els=new Map();
function element(tag){return {tag,value:'',hidden:false,children:[],append(...n){this.children.push(...n)},replaceChildren(...n){this.children=n},setAttribute(){},focus(){},scrollIntoView(){}}}
const $=id=>{if(!els.has(id))els.set(id,element('div'));return els.get(id)};
const ingredient={id:'ingredient',type:'item',bls_code:'MILK',food:{name_de:'Milch'},quantity:{value:90,unit:'g'},timestamp:'2026-10-14T08:30:00Z',status:'processed',health_status:'pending',nutrients:{dietaryEnergyConsumed:{value:50}}};
const context=vm.createContext({$,document:{createElement:element},currentPage:'recipes',activeRecipe:'recipe',recipeRows:[{id:'recipe',ingredients:[ingredient]}],rows:[],lang:'de',t:x=>x,formatNumber:String,attempt:null,searchSequence:0,editing:null,importedBasis:null,selected:null,reset(){},kindChange(){},localDate:d=>d.toISOString().slice(0,10)});
const source=fs.readFileSync('app/static/app.js','utf8');
vm.runInContext(source.slice(source.indexOf('function render(){'),source.indexOf('\n',source.indexOf('function render(){'))),context);
vm.runInContext(source.slice(source.indexOf('function resumeEntry(e){'),source.indexOf("$('alcoholEntryMode').onchange")),context);
vm.runInContext('render()',context);
const button=$('entries').children[0].children[0];assert.equal(button.tag,'button');button.onclick();
assert.equal(context.editing,'ingredient');assert.equal(context.selected.bls_code,'MILK');assert.equal($('amount').value,90);assert.equal($('selected').textContent,'Milch');assert.equal($('kind').disabled,true);assert.equal($('cancel').hidden,false);
console.log('Recipe ingredient UI: clicking restores the saved food and amount');
