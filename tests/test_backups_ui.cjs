const fs=require('fs'),vm=require('vm'),assert=require('assert');
const els=new Map(),listeners={},calls=[];let allowed=false,reloaded=false;
const $=id=>{if(!els.has(id))els.set(id,{value:'',hidden:false,disabled:false,files:[],textContent:''});return els.get(id)};
const ctx=vm.createContext({$,words:{de:{},en:{}},t:k=>k,translate(){},window:{addEventListener:(n,f)=>listeners[n]=f},confirm:()=>allowed,location:{reload(){reloaded=true}},api:async(path,options)=>{calls.push({path,headers:options.headers,body:options.body});return path.endsWith('inspect')?{created_at:'2026-10-18',app_version:'1.32.0',counts:{entries:3,recipes:2},files:4}:{restored:true}}});
vm.runInContext(fs.readFileSync('app/static/backups.js','utf8'),ctx);
(async()=>{
 const file={name:'backup.zip',size:100};$('backupFile').files=[file];await $('backupInspect').onclick();assert.equal(calls.length,1);assert.equal(calls[0].path,'/backups/inspect');assert.equal($('backupRestore').hidden,false);assert.ok($('backupSummary').textContent.includes('5'));
 await $('backupRestore').onclick();assert.equal(calls.length,1,'cancel must not restore');allowed=true;await $('backupRestore').onclick();assert.equal(calls[1].path,'/backups/restore');assert.equal(calls[1].headers['X-Friss-Restore'],'replace');assert.equal(calls[1].body,file);assert.ok(reloaded);
 listeners['friss-logout']();assert.equal($('backupRestore').hidden,true);assert.equal($('backupFile').value,'');
 console.log('Backup UI: inspect before restore, confirmation, original file upload, reload and logout clearing passed');
})().catch(e=>{console.error(e);process.exitCode=1});
