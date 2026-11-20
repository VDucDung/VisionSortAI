import {JSDOM,VirtualConsole} from 'jsdom';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const frontendRoot=new URL('../',import.meta.url);
import {mountApplication} from '../assets/src/application.js';
const result={id:7,status:'DONE',cloudinaryUrl:'https://example.com/original.png',annotatedUrl:'https://example.com/annotated.png',createdAt:'2026-10-31T06:00:00Z',count:1,confidenceAvg:.93,requiresConfirmation:true,detections:[{id:9,label:'plastic',labelDisplay:'Chai nhựa',confidence:.93,status:'NEEDS_CONFIRM',binName:'Thu gom nhựa',action:'Làm sạch trước khi thu gom.'}]};
const summary={id:7,accountId:1,fullName:'Người kiểm thử',phone:'0912345678',createdAt:result.createdAt,imageUrl:result.cloudinaryUrl,status:'DONE',count:1,confidenceAvg:.93,materials:['plastic'],requiresConfirmation:true};
const pageResult=items=>({items,total:items.length,page:0,size:12,totalPages:1});
const statistics={totalScans:1,totalUsers:2,activeUsers:1,failedScans:0,completedScans:1,totalObjects:1,confidenceAvg:.93,needsConfirmation:1,from:'2026-10-01',to:'2026-10-31',materials:[{label:'plastic',count:1}],daily:[{label:'2026-10-30',count:0},{label:'2026-10-31',count:1}]};
async function waitFor(test){for(let i=0;i<50;i++){if(test())return;await new Promise(r=>setTimeout(r,5));}throw Error('Timed out waiting for frontend state');}
async function app(page,area='user',routes={},authenticated=true,query='') {
 const errors=[],calls=[];const console=new VirtualConsole();console.on('jsdomError',e=>{if(!e.message.includes('navigation'))errors.push(e.message);});
 const dom=new JSDOM(`<body data-page="${page}" data-area="${area}"><div id="app"></div></body>`,{url:`http://127.0.0.1:5173/${area==='admin'?'Admin':'User'}/test.html${query}`,runScripts:'outside-only',virtualConsole:console});
 const w=dom.window;w.Headers=Headers;w.AbortSignal=AbortSignal;w.TRASHSMART_CONFIG={apiBase:'http://127.0.0.1:8080'};
 w.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};w.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');this.dispatchEvent(new w.Event('close'));};
 w.URL.createObjectURL=()=> 'blob:http://127.0.0.1/fixture';w.URL.revokeObjectURL=()=>{};
 w.Image=class {width=200;height=200;async decode(){}};
 if(authenticated)w.sessionStorage.setItem(`trashsmart.${area}.session`,JSON.stringify({token:'test-token',account:{role:area==='admin'?'ADMIN':'USER'}}));
 w.fetch=async(url,opts)=>{
   const path=url.replace('http://127.0.0.1:8080/api/v1','');calls.push({path,opts});
   const key=Object.keys(routes).find(key=>path===key || key.endsWith('*')&&path.startsWith(key.slice(0,-1)));
   let value=key?routes[key]:path==='/system/info'?{application:'TrashSmart',scanApiVersion:1,adminProfileApiVersion:1}:path==='/auth/me'?{data:{id:1,fullName:'Người kiểm thử',phone:'0912345678',role:area==='admin'?'ADMIN':'USER'}}:path.startsWith('/admin/statistics')?statistics:path.startsWith('/admin/scans')?pageResult([summary]):path.startsWith('/scans?')?pageResult([summary]):path.startsWith('/scans/')?result:{};
   if(typeof value==='function')value=await value(path,opts);
   if(value instanceof Error)throw value;
   return {ok:!value.__status||value.__status<400,status:value.__status||200,json:async()=>value};
 };
 mountApplication(w);await waitFor(()=>w.document.querySelector('main:not(:has(>.loading)),.notice.error') || !authenticated && calls.length);
 return {dom,w,d:w.document,calls,errors,close(){assert.deepEqual(errors,[]);w.close();}};
}
const tests=[];
async function test(name,fn){await fn();tests.push(name);console.log('PASS',name);}
await test('Hai trang User và Admin giữ riêng trạng thái và trình xử lý khi cùng mở',async()=>{
 const [user,admin]=await Promise.all([
  app('history','user',{'/auth/me':{fullName:'User riêng',role:'USER'}}),
  app('home','admin',{'/auth/me':{fullName:'Admin riêng',role:'ADMIN'}})
 ]);
 await waitFor(()=>user.d.querySelector('.scan-card')&&admin.d.querySelector('.stats'));
 assert.equal(user.d.querySelector('.account-name').textContent,'User riêng');
 assert.equal(admin.d.querySelector('.account-name').textContent,'Admin riêng');
 user.d.querySelector('#material').value='plastic';
 user.d.querySelector('#filters').dispatchEvent(new user.w.Event('submit',{cancelable:true}));
 await waitFor(()=>user.calls.some(c=>c.path.includes('material=plastic')));
 assert(!admin.calls.some(c=>c.path.includes('material=plastic')));
 assert(admin.d.querySelector('.sidebar'));
 user.close();admin.close();
});
await test('Trang chủ dùng thương hiệu chung và kiểm tra ảnh trước khi gửi',async()=>{
 const a=await app('home','user',{},false);assert.match(a.d.querySelector('h1').textContent,/Phân loại đúng/);assert.equal(a.d.querySelector('.brand img').getAttribute('src'),'../assets/logo.svg');a.d.querySelector('#scan').click();assert.match(a.d.querySelector('#upload-error').textContent,/chọn hoặc chụp/);a.close();
});
await test('Tải ảnh gửi đúng multipart qua BE',async()=>{
 const a=await app('home','user',{'/scans':result});const input=a.d.querySelector('#file');Object.defineProperty(input,'files',{value:[new a.w.File(['image'],'chai.png',{type:'image/png'})]});input.dispatchEvent(new a.w.Event('change'));await waitFor(()=>a.d.querySelector('.preview'));a.d.querySelector('#scan').click();await waitFor(()=>a.calls.some(c=>c.path==='/scans')&&!a.d.querySelector('#scan').disabled);const upload=a.calls.find(c=>c.path==='/scans');assert.equal(upload.opts.method,'POST');assert.equal(upload.opts.body.get('file').name,'chai.png');assert.equal(upload.opts.headers.get('Authorization'),'Bearer test-token');a.close();
});
await test('Kết quả giữ trạng thái cần xác nhận và đổi ảnh gốc/nhận diện',async()=>{
 const a=await app('result','user',{},true,'?id=7');await waitFor(()=>a.d.querySelector('.detection'));assert.match(a.d.querySelector('#result').textContent,/Cần kiểm tra thêm/);assert.match(a.d.querySelector('.detection').textContent,/93%/);const buttons=a.d.querySelectorAll('[data-image]');buttons[1].click();assert.equal(a.d.querySelector('[data-result-image]').src,result.cloudinaryUrl);a.close();
});
await test('Kết quả rỗng có hướng dẫn chụp lại',async()=>{
 const a=await app('result','user',{'/scans/7':{...result,count:0,detections:[]}},true,'?id=7');await waitFor(()=>a.d.querySelector('.empty h2'));assert.match(a.d.querySelector('.empty').textContent,/Chưa tìm thấy vật thể/);a.close();
});
await test('Lượt quét lỗi có thể thử lại cùng ID',async()=>{
 let retry=false;const a=await app('result','user',{'/scans/7':()=>retry?result:{...result,status:'ERROR',errorMessage:'AI đang bận'},'/scans/7/retry':()=>{retry=true;return result;}},true,'?id=7');await waitFor(()=>a.d.querySelector('[data-retry]'));a.d.querySelector('[data-retry]').click();await waitFor(()=>a.d.querySelector('.detection'));assert(a.calls.some(c=>c.path==='/scans/7/retry'&&c.opts.method==='POST'));a.close();
});
await test('Lịch sử gửi bộ lọc vật liệu và chặn khoảng ngày sai',async()=>{
 const a=await app('history');await waitFor(()=>a.d.querySelector('.scan-card'));a.d.querySelector('#material').value='plastic';a.d.querySelector('#filters').dispatchEvent(new a.w.Event('submit',{cancelable:true}));await waitFor(()=>a.calls.some(c=>c.path.includes('material=plastic')));a.d.querySelector('#from').value='2026-10-31';a.d.querySelector('#to').value='2026-10-01';a.d.querySelector('#filters').dispatchEvent(new a.w.Event('submit',{cancelable:true}));assert.match(a.d.querySelector('#filter-error').textContent,/Ngày bắt đầu/);a.close();
});
await test('Dashboard admin hiển thị dữ liệu API và bốn mục điều hướng',async()=>{
 const a=await app('home','admin');await waitFor(()=>a.d.querySelector('.stats'));assert.equal(a.d.querySelectorAll('.sidebar .nav a').length,6);assert.equal(a.d.querySelectorAll('.stat').length,4);assert(a.d.querySelector('svg.chart'));assert.match(a.d.querySelector('main').textContent,/Không phải độ chính xác/);a.close();
});
await test('Admin mở chi tiết lượt quét trong hộp thoại',async()=>{
 const a=await app('history','admin');await waitFor(()=>a.d.querySelector('[data-detail]'));a.d.querySelector('[data-detail]').click();await waitFor(()=>a.d.querySelector('#detail-dialog .detection'));assert(a.d.querySelector('dialog').hasAttribute('open'));a.close();
});
await test('Admin thống kê dùng cùng layout và bộ lọc ngày',async()=>{
 const a=await app('statistics','admin');await waitFor(()=>a.d.querySelector('.stats'));assert(a.d.querySelector('#filters'));assert.match(a.d.querySelector('main').textContent,/Trạng thái xử lý/);a.close();
});
await test('Admin cập nhật và khóa tài khoản bằng API',async()=>{
 const user={id:1,fullName:'Người kiểm thử',phone:'0912345678',email:'test@example.com',active:true,createdAt:'2026-10-01T08:00:00'};
 const a=await app('users','admin',{'/admin/users?*':pageResult([user]),'/admin/users/1':user});await waitFor(()=>a.d.querySelector('[data-edit]'));a.d.querySelector('[data-edit]').click();a.d.querySelector('[name=active]').checked=false;a.d.querySelector('#edit-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));await waitFor(()=>a.calls.some(c=>c.opts.method==='PATCH'));const patch=a.calls.find(c=>c.opts.method==='PATCH');assert.equal(patch.path,'/admin/users/1');assert.equal(JSON.parse(patch.opts.body).active,false);a.close();
});
await test('Admin chỉ có đăng nhập, user có đăng ký',async()=>{
 const a=await app('login','admin',{},false);assert(!a.d.querySelector('a[href*="register"]'));assert.equal(a.d.querySelector('#identifier').type,'email');a.close();const b=await app('register','user',{},false);assert(b.d.querySelector('#fullName'));assert.equal(b.d.querySelector('#password').minLength,8);b.close();
});
await test('Lỗi kết nối có thông báo và nút thử lại',async()=>{
 const a=await app('history','user',{'/scans?*':new Error('offline')});await waitFor(()=>a.d.querySelector('#history .notice.error'));assert.match(a.d.querySelector('#history').textContent,/Không thể kết nối máy chủ/);assert(a.d.querySelector('[data-reload]'));a.close();
});
async function chooseImage(a,name='photo.png') {
 const input=a.d.querySelector('#file');Object.defineProperty(input,'files',{value:[new a.w.File(['image'],name,{type:'image/png'})]});
 input.dispatchEvent(new a.w.Event('change'));await waitFor(()=>a.d.querySelector('.preview'));
}
const loginResponse={data:{token:'new-test-token',account:{id:1,fullName:'Đã đăng nhập',role:'USER'}}};
async function signIn(a) {
 await waitFor(()=>a.d.querySelector('#signin-form'));
 a.d.querySelector('#signin-id').value='0912345678';a.d.querySelector('#signin-password').value='test-password';
 a.d.querySelector('#signin-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
}
await test('Tên file dài được giới hạn trong khung ảnh và có tooltip đầy đủ',async()=>{
 const a=await app('home');const name='camera_'.repeat(45)+'.png';await chooseImage(a,name);
 const title=a.d.querySelector('.upload-filename');assert.equal(title.title,name);assert.equal(title.textContent,name);
 const css=fs.readFileSync(new URL('assets/styles.css',frontendRoot),'utf8');
 const style=a.d.createElement('style');style.textContent=css;a.d.head.append(style);
 assert.equal(a.w.getComputedStyle(title).textOverflow,'ellipsis');assert.equal(a.w.getComputedStyle(title).whiteSpace,'nowrap');
 assert.equal(a.w.getComputedStyle(a.d.querySelector('.hero')).gridTemplateColumns,'repeat(2,minmax(0,1fr))');a.close();
});
await test('Chọn ảnh khi chưa đăng nhập: đăng nhập tại chỗ và gửi cùng ảnh',async()=>{
 const a=await app('home','user',{'/auth/login/user':loginResponse,'/scans':result},false);
 await chooseImage(a,'kept-photo.png');a.d.querySelector('#scan').click();await signIn(a);
 await waitFor(()=>a.calls.some(c=>c.path==='/scans')&&!a.d.querySelector('#scan').disabled);
 const upload=a.calls.find(c=>c.path==='/scans');assert.equal(upload.opts.body.get('file').name,'kept-photo.png');
 assert.equal(upload.opts.headers.get('Authorization'),'Bearer new-test-token');assert.match(a.d.querySelector('.account-actions').textContent,/Đã đăng nhập/);a.close();
});
await test('Đăng nhập sai hoặc hủy không làm mất ảnh đã chọn',async()=>{
 const a=await app('home','user',{'/auth/login/user':{__status:401,message:'Sai tài khoản hoặc mật khẩu'}},false);
 await chooseImage(a);a.d.querySelector('#scan').click();await signIn(a);await waitFor(()=>a.d.querySelector('#signin-error').textContent);
 assert.match(a.d.querySelector('#signin-error').textContent,/Sai tài khoản/);assert(!a.calls.some(c=>c.path==='/scans'));
 a.d.querySelector('.signin-dialog [data-close]').click();await waitFor(()=>!a.d.querySelector('#scan').disabled);
 assert(a.d.querySelector('.preview'));assert.match(a.d.querySelector('#upload-error').textContent,/Ảnh vẫn được giữ/);a.close();
});
await test('Phiên hết hạn: thông báo lý do, đăng nhập lại, gửi ảnh tối đa một lần nữa',async()=>{
 let meCount=0,uploads=0;
 const a=await app('home','user',{'/auth/me':()=>++meCount===1?{data:loginResponse.data.account}:{__status:401,message:'Token đã hết hạn'},
 '/scans':()=>++uploads===1?{__status:401,message:'Token đã hết hạn'}:result,'/auth/login/user':loginResponse});
 await chooseImage(a);a.d.querySelector('#scan').click();await waitFor(()=>a.d.querySelector('.signin-reason'));
 assert.match(a.d.querySelector('.signin-reason').textContent,/Token đã hết hạn/);await signIn(a);
 await waitFor(()=>uploads===2&&!a.d.querySelector('#scan').disabled);assert(a.d.querySelector('.preview'));assert(a.w.sessionStorage.getItem('trashsmart.user.session'));a.close();
});
await test('401 do BE lỗi nhưng phiên vẫn hợp lệ: giữ token và không chuyển đăng nhập',async()=>{
 const a=await app('home','user',{'/scans':{__status:401,message:'Unauthorized'}});await chooseImage(a);a.d.querySelector('#scan').click();
 await waitFor(()=>!a.d.querySelector('#scan').disabled);assert.match(a.d.querySelector('#upload-error').textContent,/phiên đăng nhập vẫn hợp lệ/);
 assert(a.w.sessionStorage.getItem('trashsmart.user.session'));assert(!a.d.querySelector('.signin-dialog'));assert(a.d.querySelector('.preview'));a.close();
});
await test('Lỗi upload 500/502/413 giữ ảnh, giữ phiên và hiển thị đúng lỗi',async()=>{
 for(const status of [500,502,413]) {
  const a=await app('home','user',{'/scans':{__status:status,message:`Upload error ${status}`}});await chooseImage(a);a.d.querySelector('#scan').click();
  await waitFor(()=>!a.d.querySelector('#scan').disabled);assert.match(a.d.querySelector('#upload-error').textContent,new RegExp(String(status)));
  assert(a.w.sessionStorage.getItem('trashsmart.user.session'));assert(a.d.querySelector('.preview'));assert(!a.d.querySelector('.signin-dialog'));a.close();
 }
});
await test('Trang con giữ header cả khi kiểm tra phiên hoặc tải dữ liệu lỗi',async()=>{
 for(const p of ['history','result']) {
  const a=await app(p,'user',{'/auth/me':new Error('offline')},true,p==='result'?'?id=7':'');
  assert(a.d.querySelector('header.topbar'));assert.equal(a.d.querySelectorAll('nav.nav a').length,3);
  assert(a.d.querySelector('#main .notice.error'));assert(a.d.querySelector('footer'));
  assert(a.d.querySelector('nav a[href*="history.html"]').href.includes('v=20261107-hitl-adminverify'));a.close();
 }
 const b=await app('history','user',{'/scans?*':new Error('offline')});
 await waitFor(()=>b.d.querySelector('#history .notice.error'));assert(b.d.querySelector('header.topbar'));b.close();
});
await test('Nhận ra BE cũ trước khi upload và giữ ảnh cùng phiên đăng nhập',async()=>{
 const a=await app('home','user',{'/system/info':{__status:401}});await chooseImage(a);a.d.querySelector('#scan').click();
 await waitFor(()=>!a.d.querySelector('#scan').disabled);assert.match(a.d.querySelector('#upload-error').textContent,/BE đang chạy bản cũ/);
 assert(!a.calls.some(c=>c.path==='/scans'));assert(a.w.sessionStorage.getItem('trashsmart.user.session'));assert(a.d.querySelector('.preview'));a.close();
});
await test('Ba trang user cùng tải đúng phiên bản shell và tài nguyên',async()=>{
 for(const name of ['index','history','result_analys']) {
  const html=fs.readFileSync(new URL(`User/${name}.html`,frontendRoot),'utf8');
  assert(html.includes('../assets/app.js?v=20261107-hitl-adminverify'));assert(html.includes('../assets/styles.css?v=20261107-hitl-adminverify'));
  assert(!html.includes('SMARTDISPOSAL'));assert(html.includes('data-area="user"'));
 }
});
const ownProfile={id:1,fullName:'Admin Profile',phone:'0912345678',email:'admin@example.com',role:'ADMIN'};
await test('Admin có trang hồ sơ riêng và liên kết trên header/sidebar',async()=>{
 const a=await app('profile','admin',{'/admin/profile':ownProfile});await waitFor(()=>a.d.querySelector('#profile-form'));
 assert(a.d.querySelector('.account-profile-link'));assert(a.d.querySelector('.sidebar a[aria-current=page]').href.includes('profile.html'));
 assert.equal(a.d.querySelector('#profile-email').value,ownProfile.email);assert(a.d.querySelector('#password-form'));a.close();
});
await test('Lưu hồ sơ cập nhật tên trên header và phiên đăng nhập',async()=>{
 const changed={...ownProfile,fullName:'Admin Changed'};
 const a=await app('profile','admin',{'/admin/profile':(p,o)=>o.method==='PATCH'?{token:'profile-token',account:changed}:ownProfile});
 await waitFor(()=>a.d.querySelector('#profile-form'));a.d.querySelector('#profile-name').value=changed.fullName;
 a.d.querySelector('#profile-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
 await waitFor(()=>a.d.querySelector('#profile-success').textContent);
 assert.equal(a.d.querySelector('.account-name').textContent,changed.fullName);assert.equal(a.d.querySelector('[data-profile-name]').textContent,changed.fullName);
 assert.equal(JSON.parse(a.w.sessionStorage.getItem('trashsmart.admin.session')).token,'profile-token');
 assert(!Object.keys(JSON.parse(a.calls.find(c=>c.opts.method==='PATCH').opts.body)).includes('id'));a.close();
});
await test('Đổi email yêu cầu mật khẩu hiện tại và lỗi không làm mất dữ liệu nhập',async()=>{
 const a=await app('profile','admin',{'/admin/profile':(p,o)=>o.method==='PATCH'?{__status:409,message:'Email đã được sử dụng'}:ownProfile});
 await waitFor(()=>a.d.querySelector('#profile-form'));const email=a.d.querySelector('#profile-email');email.value='new@example.com';email.dispatchEvent(new a.w.Event('input'));
 assert(a.d.querySelector('#profile-confirm-password').required);a.d.querySelector('#profile-confirm-password').value='current-password';
 a.d.querySelector('#profile-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));await waitFor(()=>a.d.querySelector('#profile-error').textContent);
 assert.match(a.d.querySelector('#profile-error').textContent,/Email đã được sử dụng/);assert.equal(email.value,'new@example.com');assert(!a.d.querySelector('.signin-dialog'));a.close();
});
await test('Xác nhận mật khẩu không khớp bị chặn trước khi gọi API',async()=>{
 const a=await app('profile','admin',{'/admin/profile':ownProfile});await waitFor(()=>a.d.querySelector('#password-form'));
 a.d.querySelector('#password-current').value='old-password';a.d.querySelector('#password-new').value='new-password';a.d.querySelector('#password-confirm').value='different-password';
 a.d.querySelector('#password-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));assert.match(a.d.querySelector('#password-error').textContent,/chưa khớp/);
 assert(!a.calls.some(c=>c.path==='/admin/profile/password'));a.close();
});
await test('Đổi mật khẩu lưu token mới và xóa các ô mật khẩu sau khi thành công',async()=>{
 const a=await app('profile','admin',{'/admin/profile':ownProfile,'/admin/profile/password':{token:'rotated-password-token',account:ownProfile}});
 await waitFor(()=>a.d.querySelector('#password-form'));a.d.querySelector('#password-current').value='old-password';a.d.querySelector('#password-new').value='new-password';a.d.querySelector('#password-confirm').value='new-password';
 a.d.querySelector('#password-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));await waitFor(()=>a.d.querySelector('#password-success').textContent);
 assert.equal(a.d.querySelector('#password-current').value,'');assert.equal(a.d.querySelector('#password-new').value,'');
 assert.equal(JSON.parse(a.w.sessionStorage.getItem('trashsmart.admin.session')).token,'rotated-password-token');assert.match(a.d.querySelector('#password-success').textContent,/phiên đăng nhập cũ/);a.close();
});
await test('Bộ chọn ảnh hỗ trợ WebP và gửi nguyên file qua API',async()=>{
 const a=await app('home','user',{'/scans':result});const input=a.d.querySelector('#file');
 assert(input.accept.includes('.webp'));assert(input.accept.includes('image/webp'));
 const file=new a.w.File(['webp-fixture'],'can.webp',{type:'image/webp'});Object.defineProperty(input,'files',{value:[file]});
 input.dispatchEvent(new a.w.Event('change'));await waitFor(()=>a.d.querySelector('.preview'));a.d.querySelector('#scan').click();
 await waitFor(()=>a.calls.some(c=>c.path==='/scans')&&!a.d.querySelector('#scan').disabled);
 const sent=a.calls.find(c=>c.path==='/scans').opts.body.get('file');assert.equal(sent.name,'can.webp');assert.equal(sent.type,'image/webp');a.close();
});
await test('WebP vẫn chọn được nếu Windows không cung cấp MIME',async()=>{
 const a=await app('home');const input=a.d.querySelector('#file');Object.defineProperty(input,'files',{value:[new a.w.File(['image'],'PHOTO.WEBP')]});
 input.dispatchEvent(new a.w.Event('change'));await waitFor(()=>a.d.querySelector('.preview'));assert.equal(a.d.querySelector('#upload-error').textContent,'');a.close();
});
await test('Bộ chọn vẫn chặn định dạng ngoài danh sách hỗ trợ',async()=>{
 const a=await app('home');const input=a.d.querySelector('#file');Object.defineProperty(input,'files',{value:[new a.w.File(['image'],'photo.gif',{type:'image/gif'})]});
 input.dispatchEvent(new a.w.Event('change'));assert.match(a.d.querySelector('#upload-error').textContent,/JPG, PNG hoặc WebP/);assert(!a.d.querySelector('.preview'));a.close();
});
await test('Một chai có ba bộ phận, không bị đếm thành bốn chai',async()=>{
 const r=withComponents();const a=await app('result','user',{'/scans/7':r},true,'?id=7');await waitFor(()=>a.d.querySelectorAll('.component-row').length===3);
 assert.equal(a.d.querySelectorAll('.detection').length,1);assert.match(a.d.querySelector('.component-summary').textContent,/3 bộ phận/);assert.match(a.d.querySelector('.result-meta').textContent,/1Chai/);a.close();
});
await test('Lịch sử cũ không tự sinh vật liệu bộ phận',async()=>{
 const a=await app('result','user',{},true,'?id=7');await waitFor(()=>a.d.querySelector('.detection'));assert.equal(a.d.querySelectorAll('.component-row').length,0);assert.match(a.d.querySelector('.component-state').textContent,/chưa phân tích bộ phận/);a.close();
});
await test('Model chưa sẵn sàng giữ kết quả chai và báo rõ trạng thái',async()=>{
 const r=withComponents();r.componentCount=0;r.detections[0].components=[];r.detections[0].componentAnalysisStatus='MODEL_UNAVAILABLE';
 const a=await app('result','user',{'/scans/7':r},true,'?id=7');await waitFor(()=>a.d.querySelector('.component-state'));assert.match(a.d.querySelector('.component-state').textContent,/chưa sẵn sàng/);assert.match(a.d.querySelector('.detection').textContent,/Chai nhựa/);a.close();
});
await test('Chọn bộ phận đánh dấu khung trên ảnh gốc, đổi ảnh xóa đánh dấu',async()=>{
 const a=await app('result','user',{'/scans/7':withComponents()},true,'?id=7');await waitFor(()=>a.d.querySelector('[data-component-box]'));
 const photo=a.d.querySelector('[data-result-image]');Object.defineProperty(photo,'naturalWidth',{value:800});Object.defineProperty(photo,'naturalHeight',{value:1000});photo.decode=async()=>{};photo.dispatchEvent(new a.w.Event('load'));
 a.d.querySelector('[data-component-box]').click();await waitFor(()=>!a.d.querySelector('[data-component-overlay]').hasAttribute('hidden'));
 assert.equal(photo.src,result.cloudinaryUrl);const rect=a.d.querySelector('[data-component-rect]');assert.equal(rect.getAttribute('x'),'340');assert.equal(rect.getAttribute('width'),'120');assert.equal(a.d.querySelector('[data-component-overlay]').getAttribute('viewBox'),'0 0 800 1000');
 a.d.querySelector('[data-image]').click();assert(a.d.querySelector('[data-component-overlay]').hasAttribute('hidden'));a.close();
});
await test('Bộ phận chưa rõ vật liệu không hiển thị kết luận giấy mặc định',async()=>{
 const a=await app('result','user',{'/scans/7':withComponents()},true,'?id=7');await waitFor(()=>a.d.querySelectorAll('.component-row').length===3);const row=a.d.querySelectorAll('.component-row')[2];assert.match(row.textContent,/Chưa xác định/);assert.match(row.textContent,/Cần kiểm tra thêm/);assert(!/Giấy/.test(row.textContent));a.close();
});
await test('Nội dung tên model và bộ phận được escape',async()=>{
 const r=withComponents();r.componentModelVersion='<img src=x onerror=alert(1)>';r.detections[0].components[0].partName='<script>alert(1)</script>';
 const a=await app('result','user',{'/scans/7':r},true,'?id=7');await waitFor(()=>a.d.querySelectorAll('.component-row').length===3);assert.equal(a.d.querySelectorAll('#result script').length,0);assert(!a.d.querySelector('#result [onerror]'));a.close();
});
await test('Admin thống kê bộ phận riêng với vật thể',async()=>{
 const s={...statistics,totalComponents:3,componentsNeedingConfirmation:1,componentMaterials:[{label:'metal',count:1},{label:'glass',count:1},{label:'unknown',count:1}]};
 const a=await app('statistics','admin',{'/admin/statistics?*':s});await waitFor(()=>a.d.querySelector('.component-statistics'));assert.equal(a.d.querySelectorAll('.component-statistics').length,1);assert.match(a.d.querySelector('.component-statistics').textContent,/3 bộ phận/);assert.match(a.d.querySelector('.component-statistics').textContent,/không cộng vào số chai/);a.close();
});
function withComponents(){return {...result,componentCount:3,componentModelVersion:'parts-test-v1',detections:[{...result.detections[0],componentAnalysisStatus:'COMPLETED',components:[
 {id:1,partType:'cap',partName:'Nắp chai',material:'metal',materialName:'Kim loại',detectionConfidence:.93,materialConfidence:.88,status:'DETECTED',x1:340,y1:70,x2:460,y2:140,action:'Tách riêng nắp.'},
 {id:2,partType:'body',partName:'Thân/vỏ chai',material:'glass',materialName:'Thủy tinh',detectionConfidence:.96,materialConfidence:.91,status:'DETECTED',x1:260,y1:140,x2:540,y2:930,action:'Thu gom thủy tinh.'},
 {id:3,partType:'label',partName:'Nhãn dán',material:'unknown',materialName:'Chưa xác định',detectionConfidence:.89,materialConfidence:.4,status:'NEEDS_CONFIRM',x1:285,y1:500,x2:515,y2:750,action:'Kiểm tra vật liệu trực tiếp.'}
 ]}]};}

fs.writeFileSync(new URL('./frontend-test-results.json',import.meta.url),JSON.stringify({passed:tests.length,tests},null,2));
console.log(`${tests.length} frontend flow tests passed.`);


function detailedFixture(){return {requestId:7,status:'COMPLETED',experimental:true,modelVersion:'components-experimental-fixture',componentCount:3,imageWidth:800,imageHeight:1000,parents:[{detectionId:9,componentAnalysisStatus:'COMPLETED',components:[
 {partType:'cap',partName:'Nắp chai',material:'metal',materialName:'Kim loại',status:'NEEDS_CONFIRM',detectionConfidence:.9,materialConfidence:.8,x1:340,y1:60,x2:460,y2:150},
 {partType:'body',partName:'Thân/vỏ chai',material:'glass',materialName:'Thủy tinh',status:'NEEDS_CONFIRM',detectionConfidence:.95,materialConfidence:.85,x1:200,y1:150,x2:600,y2:900},
 {partType:'label',partName:'Nhãn dán',material:'unknown',materialName:'Chưa xác định',status:'NEEDS_CONFIRM',detectionConfidence:.8,materialConfidence:.4,x1:250,y1:400,x2:550,y2:600}]}]};}
await test('Tab chi tiết chỉ gọi model mới khi được bấm, giữ hai chế độ cũ',async()=>{
 const a=await app('result','user',{'/scans/7/detailed':detailedFixture()},true,'?id=7');await waitFor(()=>a.d.querySelector('[data-detail-tab]'));
 assert.equal(a.d.querySelectorAll('[data-image]').length,2);assert.equal(a.calls.filter(c=>c.path.endsWith('/detailed')).length,0);
 a.d.querySelector('[data-detail-tab]').click();await waitFor(()=>a.d.querySelector('.detail-summary'));
 assert.equal(a.calls.filter(c=>c.path.endsWith('/detailed')).length,1);const call=a.calls.find(c=>c.path.endsWith('/detailed'));assert.equal(call.opts.method,'POST');assert.equal(call.opts.headers.get('Authorization'),'Bearer test-token');
 assert(!a.d.querySelector('[data-detail-panel]').hidden);assert(a.d.querySelector('[data-standard-detections]').hidden);assert.equal(a.d.querySelectorAll('.component-row').length,3);
 a.d.querySelector('[data-image]').click();assert(!a.d.querySelector('[data-standard-detections]').hidden);assert(a.d.querySelector('[data-detail-panel]').hidden);assert.equal(a.d.querySelector('[data-result-image]').src,result.annotatedUrl);assert.match(a.d.querySelector('.detection').textContent,/93%/);a.close();
});
await test('Bấm chi tiết nhiều lần chỉ gửi một yêu cầu, sau đó dùng kết quả đã tải',async()=>{
 let resolve;const promise=new Promise(r=>resolve=r);const a=await app('result','user',{'/scans/7/detailed':()=>promise},true,'?id=7');await waitFor(()=>a.d.querySelector('[data-detail-tab]'));
 const tab=a.d.querySelector('[data-detail-tab]');tab.click();tab.click();assert.equal(a.calls.filter(c=>c.path.endsWith('/detailed')).length,1);resolve(detailedFixture());await waitFor(()=>a.d.querySelector('.detail-summary'));
 a.d.querySelector('[data-image]').click();tab.click();assert.equal(a.calls.filter(c=>c.path.endsWith('/detailed')).length,1);a.close();
});
await test('Lỗi model chi tiết giữ ảnh cũ và phiên đăng nhập',async()=>{
 const a=await app('result','user',{'/scans/7/detailed':{__status:503,message:'Model chi tiết đang bận'}},true,'?id=7');await waitFor(()=>a.d.querySelector('[data-detail-tab]'));a.d.querySelector('[data-detail-tab]').click();await waitFor(()=>a.d.querySelector('[data-detail-retry]'));
 assert.match(a.d.querySelector('[data-detail-panel]').textContent,/đang bận/);assert(a.w.sessionStorage.getItem('trashsmart.user.session'));
 a.d.querySelectorAll('[data-image]')[1].click();assert.equal(a.d.querySelector('[data-result-image]').src,result.cloudinaryUrl);assert(!a.calls.some(c=>c.path.endsWith('/retry')));a.close();
});
await test('Kết quả chi tiết trả muộn không đổi chế độ nhận diện người dùng đã chọn',async()=>{
 let resolve;const promise=new Promise(r=>resolve=r);const a=await app('result','user',{'/scans/7/detailed':()=>promise},true,'?id=7');await waitFor(()=>a.d.querySelector('[data-detail-tab]'));
 a.d.querySelector('[data-detail-tab]').click();a.d.querySelector('[data-image]').click();resolve(detailedFixture());await waitFor(()=>a.d.querySelector('.detail-summary'));
 assert(a.d.querySelector('[data-detail-panel]').hidden);assert.equal(a.d.querySelector('[data-result-image]').src,result.annotatedUrl);assert(!a.d.querySelector('[data-standard-summary]').hidden);a.close();
});
await test('Chi tiết vẽ các khung riêng và chọn được từng bộ phận',async()=>{
 const a=await app('result','user',{'/scans/7/detailed':detailedFixture()},true,'?id=7');await waitFor(()=>a.d.querySelector('[data-detail-tab]'));
 const photo=a.d.querySelector('[data-result-image]');Object.defineProperty(photo,'naturalWidth',{value:800});Object.defineProperty(photo,'naturalHeight',{value:1000});photo.decode=async()=>{};
 a.d.querySelector('[data-detail-tab]').click();await waitFor(()=>a.d.querySelectorAll('[data-all-component-overlay] rect').length===3);
 assert.equal(photo.src,result.cloudinaryUrl);a.d.querySelector('[data-component-box]').click();await waitFor(()=>!a.d.querySelector('[data-component-overlay]').hasAttribute('hidden'));
 photo.dispatchEvent(new a.w.Event('load'));await new Promise(r=>setTimeout(r,5));assert(!a.d.querySelector('[data-component-overlay]').hasAttribute('hidden'));assert(a.d.querySelector('[data-all-component-overlay]').hasAttribute('hidden'));
 assert.equal(a.d.querySelector('[data-component-rect]').getAttribute('x'),'340');a.close();
});
await test('Chi tiết unknown không suy ra vật liệu từ nhãn cả chai',async()=>{
 const a=await app('result','user',{'/scans/7/detailed':detailedFixture()},true,'?id=7');await waitFor(()=>a.d.querySelector('[data-detail-tab]'));a.d.querySelector('[data-detail-tab]').click();await waitFor(()=>a.d.querySelector('.detail-summary'));
 const last=[...a.d.querySelectorAll('.component-row')].at(-1);assert.match(last.textContent,/Chưa xác định/);assert(!last.textContent.includes('Nhựa'));assert(!last.textContent.includes('Giấy'));a.close();
});
await test('Tên bộ phận và model trong chi tiết được escape',async()=>{
 const value=detailedFixture();value.modelVersion='<img src=x onerror=alert(1)>';value.parents[0].components[0].partName='<script>alert(1)</script>';
 const a=await app('result','user',{'/scans/7/detailed':value},true,'?id=7');await waitFor(()=>a.d.querySelector('[data-detail-tab]'));a.d.querySelector('[data-detail-tab]').click();await waitFor(()=>a.d.querySelector('.detail-summary'));
 assert(!a.d.querySelector('[data-detail-panel] [onerror]'));assert.equal(a.d.querySelectorAll('[data-detail-panel] script').length,0);a.close();
});
await test('Thử lại chi tiết gọi đúng endpoint mà không quét lại model cũ',async()=>{
 let attempts=0;const a=await app('result','user',{'/scans/7/detailed':()=>++attempts===1?{__status:503,message:'Thử lại'}:detailedFixture()},true,'?id=7');await waitFor(()=>a.d.querySelector('[data-detail-tab]'));
 a.d.querySelector('[data-detail-tab]').click();await waitFor(()=>a.d.querySelector('[data-detail-retry]'));a.d.querySelector('[data-detail-retry]').click();await waitFor(()=>a.d.querySelector('.detail-summary'));
 assert.equal(attempts,2);assert(!a.calls.some(c=>c.path==='/scans/7/retry'));a.close();
});
console.log(`${tests.length} total frontend flows passed, including independent detailed recognition.`);

const hitlResult=()=>({...result,detections:[{...result.detections[0],x1:1,y1:2,x2:90,y2:180}]});
const hitlCase={learningCaseId:'case-1',feedbackRevision:0,feedbackState:'OPEN',queryRecommended:true,queryPriority:.46,
  partType:'label',partName:'Nhãn dán',material:'paper',materialName:'Giấy',materialConfidence:.54,detectionConfidence:.9,
  status:'NEEDS_CONFIRM',x1:20,y1:50,x2:80,y2:100};
function hitlDetail(component=hitlCase){return {requestId:7,status:'COMPLETED',experimental:true,modelVersion:'exp-hitl',componentCount:1,parents:[{detectionId:9,componentAnalysisStatus:'COMPLETED',components:[{...component}]}]};}
await test('HITL ưu tiên hỏi bộ phận chưa chắc và không chọn sẵn câu trả lời',async()=>{
 const a=await app('result','user',{'/scans/7':hitlResult(),'/scans/7/detailed':hitlDetail()},true,'?id=7');
 await waitFor(()=>a.d.querySelector('[data-detail-tab]'));a.d.querySelector('[data-detail-tab]').click();await waitFor(()=>a.d.querySelector('[data-hitl-form]'));
 assert(a.d.querySelector('.hitl-feedback').open);assert.equal(a.d.querySelectorAll('[data-hitl-form] input:checked').length,0);
 assert.equal(a.d.querySelectorAll('[data-hitl-form] input[type=radio]').length,5);assert.equal(a.d.querySelector('[name=trainingConsent]').checked,false);a.close();
});
await test('HITL gửi vật liệu sửa và căn cứ, giữ dự đoán AI và chặn gửi trùng',async()=>{
 let releaseFeedback;
 const a=await app('result','user',{'/scans/7':hitlResult(),'/scans/7/detailed':hitlDetail(),'/scans/7/learning/case-1/feedback':()=>new Promise(resolve=>releaseFeedback=resolve)},true,'?id=7');
 await waitFor(()=>a.d.querySelector('[data-detail-tab]'));a.d.querySelector('[data-detail-tab]').click();await waitFor(()=>a.d.querySelector('[data-hitl-form]'));
 const form=a.d.querySelector('[data-hitl-form]');form.querySelector('[value=plastic]').checked=true;form.elements.verificationBasis.value='PHYSICAL_CHECK';form.elements.regionCorrect.checked=true;form.elements.trainingConsent.checked=true;
 form.dispatchEvent(new a.w.Event('submit',{bubbles:true,cancelable:true}));form.dispatchEvent(new a.w.Event('submit',{bubbles:true,cancelable:true}));
 await waitFor(()=>releaseFeedback);const calls=a.calls.filter(c=>c.path.endsWith('/feedback'));assert.equal(calls.length,1);
 assert.deepEqual(JSON.parse(calls[0].opts.body),{material:'plastic',verificationBasis:'PHYSICAL_CHECK',regionCorrect:true,trainingConsent:true,note:'',revision:0});
 releaseFeedback({feedbackState:'PENDING',humanMaterial:'plastic',revision:1});await waitFor(()=>!a.d.querySelector('[data-hitl-form]'));
 assert.match(a.d.querySelector('.hitl-feedback').textContent,/Chờ admin duyệt/);assert.match(a.d.querySelector('.component-select').textContent,/Giấy/);a.close();
});
await test('HITL lỗi gửi giữ nguyên lựa chọn và cho gửi lại',async()=>{
 const a=await app('result','user',{'/scans/7':hitlResult(),'/scans/7/detailed':hitlDetail(),'/scans/7/learning/case-1/feedback':{__status:503,message:'Chưa lưu được'}},true,'?id=7');
 await waitFor(()=>a.d.querySelector('[data-detail-tab]'));a.d.querySelector('[data-detail-tab]').click();await waitFor(()=>a.d.querySelector('[data-hitl-form]'));
 const form=a.d.querySelector('[data-hitl-form]');form.querySelector('[value=unknown]').checked=true;form.elements.verificationBasis.value='UNSURE';form.dispatchEvent(new a.w.Event('submit',{bubbles:true,cancelable:true}));
 await waitFor(()=>form.querySelector('[data-hitl-error]').textContent);assert.match(form.textContent,/Chưa lưu được/);assert(form.querySelector('[value=unknown]').checked);assert.equal(form.querySelector('button').disabled,false);a.close();
});
await test('HITL phản hồi đã lưu vẫn hiện khi mở lại chi tiết',async()=>{
 const a=await app('result','user',{'/scans/7':hitlResult(),'/scans/7/detailed':hitlDetail({...hitlCase,feedbackState:'APPROVED',humanMaterial:'plastic',feedbackRevision:2})},true,'?id=7');
 await waitFor(()=>a.d.querySelector('[data-detail-tab]'));a.d.querySelector('[data-detail-tab]').click();await waitFor(()=>a.d.querySelector('.hitl-feedback'));
 assert.equal(a.d.querySelector('[data-hitl-form]'),null);assert.match(a.d.querySelector('.hitl-feedback').textContent,/Đã duyệt để học/);a.close();
});
const queueCase={id:'case-1',scanId:7,detectionId:9,modelVersion:'exp-hitl',imageUrl:'https://example.com/a.jpg',imageWidth:100,imageHeight:200,partType:'label',predictedMaterial:'paper',materialConfidence:.54,detectionConfidence:.9,x1:20,y1:50,x2:80,y2:100,feedbackState:'PENDING',humanMaterial:'plastic',verificationBasis:'PHYSICAL_CHECK',regionCorrect:true,trainingConsent:true,humanNote:'Đã bóc nhãn',revision:1};
const hitlQueue=c=>({items:[c],total:1,page:0,totalPages:1,pending:1,approved:0,rejected:0});
await test('Admin duyệt đúng case/revision và chỉ mở nút học khi đủ điều kiện',async()=>{
 const a=await app('learning','admin',{'/admin/learning?*':hitlQueue(queueCase),'/admin/learning/case-1/review':{feedbackState:'APPROVED'}});
 await waitFor(()=>a.d.querySelector('[data-hitl-review]'));assert(a.d.querySelector('.sidebar a[aria-current=page]').href.includes('learning.html'));
 const form=a.d.querySelector('[data-hitl-review]'),button=form.querySelector('[value=APPROVE]');assert.equal(button.disabled,false);
 form.dispatchEvent(new a.w.SubmitEvent('submit',{bubbles:true,cancelable:true,submitter:button}));await waitFor(()=>a.calls.some(c=>c.path.endsWith('/review')));
 assert.deepEqual(JSON.parse(a.calls.find(c=>c.path.endsWith('/review')).opts.body),{decision:'APPROVE',note:'',revision:1});await waitFor(()=>a.d.querySelector('[data-hitl-review]'));a.close();
});
await test('Admin không duyệt nhãn unknown hoặc thiếu đồng ý; ghi chú được escape',async()=>{
 const a=await app('learning','admin',{'/admin/learning?*':hitlQueue({...queueCase,humanMaterial:'unknown',trainingConsent:false,humanNote:'<img src=x onerror=alert(1)>'})});
 await waitFor(()=>a.d.querySelector('[data-hitl-review]'));assert(a.d.querySelector('[value=APPROVE]').disabled);
 assert.equal(a.d.querySelectorAll('.hitl-review img').length,1);assert.match(a.d.querySelector('.hitl-review').textContent,/<img src=x/);a.close();
});
await test('Admin xuất danh sách rỗng không báo đã huấn luyện model',async()=>{
 const a=await app('learning','admin',{'/admin/learning?*':hitlQueue(queueCase),'/admin/learning/export?*':{records:[],nextPage:null,total:0}});
 await waitFor(()=>a.d.querySelector('[data-hitl-export]'));a.d.querySelector('[data-hitl-export]').click();await waitFor(()=>a.d.querySelector('.toast'));
 assert.match(a.d.querySelector('.toast').textContent,/Chưa có nhãn/);a.close();
});
console.log(`${tests.length} total frontend flows passed, including HITL.`);

await test('Admin có thể xác nhận nhãn chỉ xem hình bằng căn cứ riêng và ghi chú',async()=>{
 const a=await app('learning','admin',{'/admin/learning?*':hitlQueue({...queueCase,verificationBasis:'VISUAL_ONLY'}),'/admin/learning/case-1/review':{feedbackState:'APPROVED'}});
 await waitFor(()=>a.d.querySelector('[data-hitl-review]'));const form=a.d.querySelector('[data-hitl-review]'),button=form.querySelector('[value=APPROVE]');
 assert(button.disabled);form.elements.adminBasis.value='VISUAL_REVIEW';form.elements.adminBasis.dispatchEvent(new a.w.Event('change',{bubbles:true}));assert(button.disabled);
 form.elements.confirmedCorrect.checked=true;form.elements.confirmedCorrect.dispatchEvent(new a.w.Event('change',{bubbles:true}));assert(button.disabled);
 form.elements.note.value='Đã đối chiếu ảnh nhãn và xác nhận là nhựa';form.elements.note.dispatchEvent(new a.w.Event('input',{bubbles:true}));assert.equal(button.disabled,false);
 form.dispatchEvent(new a.w.SubmitEvent('submit',{bubbles:true,cancelable:true,submitter:button}));await waitFor(()=>a.calls.some(c=>c.path.endsWith('/review')));
 const sent=JSON.parse(a.calls.find(c=>c.path.endsWith('/review')).opts.body);assert.equal(sent.verificationBasis,'VISUAL_REVIEW');assert.equal(sent.confirmedCorrect,true);
 await waitFor(()=>a.d.querySelector('[data-hitl-review]'));a.close();
});
await test('Admin xác nhận độc lập vẫn không thay thế sự đồng ý dùng ảnh để học',async()=>{
 const a=await app('learning','admin',{'/admin/learning?*':hitlQueue({...queueCase,verificationBasis:'VISUAL_ONLY',trainingConsent:false})});
 await waitFor(()=>a.d.querySelector('[data-hitl-review]'));const form=a.d.querySelector('[data-hitl-review]');
 form.elements.adminBasis.value='PHYSICAL_CHECK';form.elements.confirmedCorrect.checked=true;form.elements.note.value='Đã kiểm tra trực tiếp';
 form.elements.note.dispatchEvent(new a.w.Event('input',{bubbles:true}));assert(form.querySelector('[value=APPROVE]').disabled);a.close();
});
console.log(`${tests.length} total frontend flows passed, including admin independent verification.`);
