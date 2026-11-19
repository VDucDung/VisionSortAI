import {JSDOM,VirtualConsole} from 'jsdom';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const html=fs.readFileSync(new URL('../../ModelAI/trashsmart/components/annotator.html',import.meta.url),'utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const first='01_user_photos/glass/valid__one.jpg',second='01_user_photos/metal/test__two.jpg';
async function waitFor(test){for(let i=0;i<60;i++){if(test())return;await new Promise(r=>setTimeout(r,5));}throw Error('DOM state timed out');}
async function setup(excluded=false,queueMode=false){
 const errors=[],posted=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
 const dom=new JSDOM(html,{url:'http://127.0.0.1:8766/'+(queueMode?'?queue=import-fixture':''),runScripts:'outside-only',virtualConsole:vc});const w=dom.window,d=w.document;
 w.HTMLCanvasElement.prototype.getContext=()=>({clearRect(){},drawImage(){},strokeRect(){},fillText(){}});
 w.HTMLCanvasElement.prototype.setPointerCapture=()=>{};
 w.Image=class{width=100;height=200;set src(value){queueMicrotask(()=>this.onload?.());}};
 w.crypto.randomUUID=()=>Math.random().toString(36).slice(2);
 w.confirm=()=>true;
 const files={files:[first,second],notes:{csv_group_1:{body_material:'glass',body_verified:'false',cap_material:'unknown',cap_verified:'false',label_material:'unknown',label_verified:'false',verification_basis:'Source label only'},csv_group_2:{body_material:'metal',body_verified:'false'}},imageIndex:{[first]:{groupId:'csv_group_1',split:'val',excludeFromBottleTraining:excluded},[second]:{groupId:'csv_group_2',split:'test'}},intakeAudit:{photoCount:2,matchedPhotoCount:2,errors:[],needsReviewPhotos:0}};
 files.reviewQueues=[{id:'import-fixture',title:'ZIP candidates',files:[second]},{id:'empty',title:'Empty',files:[]}];
 w.fetch=async(url,opts)=>({ok:true,json:async()=>{if(url==='/api/files')return files;if(opts?.method==='POST'){posted.push(JSON.parse(opts.body));return {saved:true};}return null;}});
 w.eval(code);await waitFor(()=>d.querySelector('#group').value===(queueMode?'csv_group_2':'csv_group_1'));
 const canvas=d.querySelector('#canvas');canvas.getBoundingClientRect=()=>({left:0,top:0,width:100,height:200});
 function draw(x1,y1,x2,y2){canvas.dispatchEvent(new w.MouseEvent('pointerdown',{clientX:x1,clientY:y1}));canvas.dispatchEvent(new w.MouseEvent('pointerup',{clientX:x2,clientY:y2}));}
 return {w,d,posted,draw,async close(){await new Promise(r=>setTimeout(r,20));assert.deepEqual(errors,[]);w.close();}};
}
{
 const a=await setup();assert.equal(a.d.querySelector('#group').value,'csv_group_1');assert.equal(a.d.querySelector('#material').value,'unknown');assert.equal(a.d.querySelector('#verified').checked,false);assert.match(a.d.querySelector('#material-notes').textContent,/Source label only/);
 a.draw(10,10,90,190);a.d.querySelector('#save').click();await waitFor(()=>a.posted.length);assert.equal(a.posted[0].split,'val');assert.equal(a.posted[0].groupId,'csv_group_1');await a.close();console.log('PASS CSV group and source split preserved without auto-verifying materials');
}
{
 const a=await setup();a.d.querySelector('#material').value='metal';a.d.querySelector('#verified').checked=true;a.d.querySelector('#basis').value='old evidence';
 const picker=a.d.querySelector('#files');picker.value=second;picker.dispatchEvent(new a.w.Event('change'));await waitFor(()=>a.d.querySelector('#group').value==='csv_group_2');assert.equal(a.d.querySelector('#material').value,'unknown');assert.equal(a.d.querySelector('#verified').checked,false);assert.equal(a.d.querySelector('#basis').value,'');await a.close();console.log('PASS image change clears previous material confirmation');
}
{
 const a=await setup();a.d.querySelector('#material').value='glass';a.d.querySelector('#verified').checked=true;a.d.querySelector('#kind').value='cap';a.d.querySelector('#kind').dispatchEvent(new a.w.Event('change'));assert.equal(a.d.querySelector('#material').value,'unknown');assert.equal(a.d.querySelector('#verified').checked,false);await a.close();console.log('PASS part change does not carry whole-body material into cap');
}
{
 const a=await setup(true);assert(a.d.querySelector('#save').disabled);a.draw(10,10,90,190);assert.equal(a.d.querySelectorAll('#boxes button').length,0);assert.match(a.d.querySelector('#message').textContent,/ngo\u00e0i ph\u1ea1m vi/);await a.close();console.log('PASS explicitly excluded example is view-only');
}
{
 const a=await setup(false,true);assert.equal(a.d.querySelector('#review-queue').value,'import-fixture');assert.equal(a.d.querySelector('#files').options.length,1);assert.equal(a.d.querySelector('#files').value,second);assert.equal(a.d.querySelector('#material').value,'unknown');assert.equal(a.d.querySelector('#verified').checked,false);await a.close();console.log('PASS imported queue deep link selects existing photo without relabeling');
}
{
 const a=await setup();const picker=a.d.querySelector('#review-queue');picker.value='import-fixture';picker.dispatchEvent(new a.w.Event('change'));await waitFor(()=>a.d.querySelector('#group').value==='csv_group_2');picker.value='';picker.dispatchEvent(new a.w.Event('change'));await waitFor(()=>a.d.querySelector('#files').options.length===2);assert.equal(a.d.querySelector('#files').value,second);await a.close();console.log('PASS queue filter can return to all photos');
}
{
 const a=await setup();const picker=a.d.querySelector('#review-queue');picker.value='empty';picker.dispatchEvent(new a.w.Event('change'));await waitFor(()=>a.d.querySelector('#save').disabled);assert.equal(a.d.querySelector('#files').options.length,0);a.d.querySelector('#save').click();assert.equal(a.posted.length,0);assert.equal(a.d.querySelector('#group').value,'');await a.close();console.log('PASS empty review queue cannot save previous photo annotation');
}
{
 const a=await setup();a.draw(10,10,90,190);a.w.confirm=()=>false;const picker=a.d.querySelector('#review-queue');picker.value='import-fixture';picker.dispatchEvent(new a.w.Event('change'));assert.equal(picker.value,'');assert.equal(a.d.querySelector('#files').value,first);assert.equal(a.d.querySelector('#boxes').children.length,1);await a.close();console.log('PASS canceling queue change preserves unsaved geometry');
}
console.log('8 grouped annotation DOM flows passed.');

