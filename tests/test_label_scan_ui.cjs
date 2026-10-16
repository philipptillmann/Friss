const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map(),listeners={};const $=id=>{if(!elements.has(id))elements.set(id,{value:'',files:[],hidden:false,disabled:false,textContent:'',click(){this.clicked=true},scrollIntoView(){}});return elements.get(id)};
let draft=null,requests=[],pending=null;
const result={text:'Per 100g\nProtein 4 g',nutrients:{dietaryProtein:{value:4,unit:'g'}},warnings:['Check label']};
const context=vm.createContext({$,words:{de:{},en:{}},t:k=>k,translate(){},window:{addEventListener:(n,f)=>listeners[n]=f},manualFieldsReady:true,manualImportPending:false,manualImportGeneration:0,manualEditing:null,manualSource:null,manualDraft:null,manualHasDraft:()=>false,confirm:()=>true,barcodeImage:async file=>file,editManual:value=>{draft=value;context.manualImportGeneration++},api:async(path,opts)=>{requests.push({path,opts});return pending?new Promise(resolve=>pending.resolve=resolve):result}});
vm.runInContext(fs.readFileSync('app/static/label-scan.js','utf8'),context);
(async()=>{
 $('labelScanFile').files=[{name:'label.jpg'}];await $('labelScanFile').onchange();
 assert.equal(requests[0].path,'/manual-ingredients/scan-label');assert.equal(draft.nutrients.dietaryProtein.value,4);assert.equal(draft.name_de,'');assert.ok(draft.notes.includes(result.text));assert.equal($('labelScanReview').hidden,false);assert.equal(context.manualEditing,null);
 draft=null;pending={};$('labelScanFile').files=[{}];const inflight=$('labelScanFile').onchange();await new Promise(resolve=>setImmediate(resolve));context.manualImportGeneration++;pending.resolve(result);await inflight;assert.equal(draft,null,'stale OCR must not overwrite newer input');
 listeners['friss-logout']();assert.equal($('labelScanText').textContent,'');assert.equal($('labelScanReview').hidden,true);
 console.log('Label scanner UI: review-only import, stale response and logout passed');
})().catch(e=>{console.error(e);process.exitCode=1});
