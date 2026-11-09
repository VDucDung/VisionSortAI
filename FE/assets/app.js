const area = document.body.dataset.area || 'user';
const page = document.body.dataset.page || 'home';
const admin = area === 'admin';
const root = document.querySelector('#app');
const config = window.TRASHSMART_CONFIG || {};
const API = (config.apiBase || 'http://localhost:8080').replace(/\/+$/, '') + '/api/v1';
const sessionKey = `trashsmart.${area}.session`;
const release = '20261107-hitl-adminverify';
const pageUrl = value => {
  const url = new URL(value, location.href);
  url.searchParams.set('v', release);
  return url.pathname + url.search + url.hash;
};
const paths = {
  leaf:'M20 4C8 3 3 9 5 17c8 4 16-2 15-13ZM4 21 16 9',
  home:'m3 10 9-7 9 7M5 9v12h5v-7h4v7h5V9',
  scan:'M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M7 12h10',
  history:'M3 11a9 9 0 1 1 2 7M3 4v7h7m2-4v6l4 2',
  arrow:'M5 12h14m-5-5 5 5-5 5',
  back:'M19 12H5m5-5-5 5 5 5',
  upload:'M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5',
  camera:'M4 6h4l2-3h4l2 3h4v15H4V6Zm12 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
  check:'m5 12 4 4L19 6',
  shield:'m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Zm-4 9 3 3 5-6',
  users:'M16 21v-3a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v3m20 0v-3a4 4 0 0 0-3-4M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm8 0a4 4 0 0 1 0 8',
  chart:'M4 3v18h17M8 16v-4m5 4V7m5 9v-7',
  grid:'M3 3h7v7H3V3Zm11 0h7v7h-7V3ZM3 14h7v7H3v-7Zm11 0h7v7h-7v-7Z',
  logout:'M9 3H3v18h6m-1-9h13m-5-5 5 5-5 5',
  chevron:'m9 5 7 7-7 7',
  close:'m6 6 12 12M6 18 18 6',
  refresh:'M20 7A9 9 0 0 0 4 6L2 9m0-6v6h6m-4 8a9 9 0 0 0 16 1l2-3m0 6v-6h-6',
  bottle:'M9 2h6v5l3 4v10H6V11l3-4V2Zm0 3h6M6 14h12',
  paper:'M5 3h10l4 4v14H5V3Zm10 0v5h4M8 12h8m-8 4h8',
  metal:'M6 5c0-3 12-3 12 0v15c0 3-12 3-12 0V5Zm0 0c0 3 12 3 12 0M6 18c0 3 12 3 12 0',
  glass:'M7 3h10l-1 9-4 4-4-4-1-9Zm5 13v5m-4 0h8',
  eye:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Zm13 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z',
  info:'M12 16v-5m0-4v1m9 4a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  edit:'m15 4 5 5M4 20l5-1L21 7l-5-5L4 14v6Z',
  calendar:'M4 5h16v16H4V5Zm0 5h16M8 2v6m8-6v6',
};
const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.leaf}"/></svg>`;
const materials = {
  plastic:{name:'Nhựa', color:'#278566', icon:'bottle', hint:'Chai, hộp nhựa'},
  paper:{name:'Giấy', color:'#b18a4f', icon:'paper', hint:'Giấy, bìa carton'},
  metal:{name:'Kim loại', color:'#718096', icon:'metal', hint:'Lon, hộp kim loại'},
  glass:{name:'Thủy tinh', color:'#5586a8', icon:'glass', hint:'Chai, lọ thủy tinh'},
};
const escape = (value = '') => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = (value = 0) => new Intl.NumberFormat('vi-VN').format(value || 0);
const percent = (value) => `${Math.round(Math.max(0, Math.min(1, Number(value) || 0)) * 100)}%`;
const date = (value, withTime = false) => {
  if (!value) return '—';
  const parsed = new Date(/^\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d(?:\.\d+)?)?$/.test(value) ? value + '+07:00' : value);
  if (!Number.isFinite(parsed.getTime())) return '—';
  return new Intl.DateTimeFormat('vi-VN', {timeZone:'Asia/Bangkok', day:'2-digit',month:'2-digit',year:'numeric',...(withTime ? {hour:'2-digit',minute:'2-digit'} : {})}).format(parsed);
};
const imageUrl = (url) => { try { const u = new URL(url); return ['http:','https:'].includes(u.protocol) ? escape(u.href) : '../assets/logo.svg'; } catch { return '../assets/logo.svg'; } };
const materialName = code => materials[code]?.name || 'Chưa xác định';
const brand = () => `<a class="brand" href="${admin ? 'home.html' : 'index.html'}" aria-label="TrashSmart — Trang chủ"><img src="../assets/logo.svg" alt=""/><div><strong>Trash<span>Smart</span></strong><small class="brand-sub">${admin ? 'Không gian quản trị' : 'Phân loại hôm nay · Xanh ngày mai'}</small></div></a>`;
function readSession() { try { return JSON.parse(sessionStorage.getItem(sessionKey) || 'null'); } catch { return null; } }
let session = readSession();
let account = null;
let toastTimer;
function toast(message) {
  document.querySelector('.toast')?.remove();
  const el = document.createElement('div'); el.className='toast'; el.setAttribute('role','status'); el.textContent=message;
  document.body.append(el); clearTimeout(toastTimer); toastTimer=setTimeout(() => el.remove(), 4500);
}
const loginUrl = () => `login.html?next=${encodeURIComponent(location.pathname.split('/').pop() + location.search)}`;
function logout() { sessionStorage.removeItem(sessionKey); location.href = pageUrl('login.html'); }
function saveSession(result) {
  if (!result?.token || result.account?.role !== (admin ? 'ADMIN' : 'USER'))
    throw new Error('Tài khoản không có quyền truy cập khu vực này.');
  sessionStorage.setItem(sessionKey, JSON.stringify(result));
  session = result;
  account = result.account;
}
async function api(path, options = {}) {
  const {publicRequest = false, ...fetchOptions} = options;
  const headers = new Headers(fetchOptions.headers || {});
  if (!publicRequest && session?.token) headers.set('Authorization', `Bearer ${session.token}`);
  if (fetchOptions.body && !(fetchOptions.body instanceof FormData)) headers.set('Content-Type','application/json');
  let response;
  try {
    response = await fetch(API + path, {...fetchOptions, headers, signal:fetchOptions.signal || AbortSignal.timeout(path === '/scans' && fetchOptions.method === 'POST' || path.endsWith('/retry') ? 240000 : 20000)});
  } catch (error) {
    throw new Error(error.name === 'TimeoutError' ? 'Yêu cầu mất quá nhiều thời gian. Kiểm tra lịch sử trước khi thử lại.' : 'Không thể kết nối máy chủ. Hãy kiểm tra backend và kết nối mạng.');
  }
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401 && !publicRequest) {
    // Older servers can turn an internal /error dispatch into 401. Check the
    // session separately before discarding a valid token or asking for login.
    if (path !== '/auth/me' && session?.token) {
      let check;
      try { check = await fetch(API + '/auth/me', {headers: {Authorization: `Bearer ${session.token}`}, signal: AbortSignal.timeout(15000)}); }
      catch { throw new Error('Chưa thể kiểm tra phiên đăng nhập do lỗi kết nối. Ảnh đã chọn vẫn được giữ; hãy thử lại.'); }
      if (check.ok) throw new Error('Máy chủ không xử lý được yêu cầu dù phiên đăng nhập vẫn hợp lệ. Hãy khởi động lại BE sau khi cập nhật và thử lại.');
      if (check.status !== 401) throw new Error('Máy chủ đang gặp lỗi khi kiểm tra phiên đăng nhập. Ảnh đã chọn vẫn được giữ; hãy thử lại.');
    }
    sessionStorage.removeItem(sessionKey);
    session = null; account = null;
    const error = new Error(payload.message && payload.message !== 'Unauthorized' ? payload.message : 'Phiên đăng nhập không còn hợp lệ. Vui lòng đăng nhập lại.');
    error.authRequired = true;
    throw error;
  }
  if (!response.ok) {
    const fallback = response.status === 404 ? 'Không tìm thấy API. Hãy cập nhật và khởi động lại BE.'
      : response.status === 403 ? 'Tài khoản không có quyền thực hiện yêu cầu này.'
      : response.status >= 500 ? `Máy chủ gặp lỗi xử lý (${response.status}). Hãy thử lại hoặc kiểm tra log BE.`
      : `Không thể xử lý yêu cầu (${response.status})`;
    throw new Error(payload.message || payload.detail || fallback);
  }
  return Object.prototype.hasOwnProperty.call(payload,'data') ? payload.data : payload;
}
let signInPending;
function requestSignIn(reason = 'Đăng nhập để tiếp tục. Ảnh đã chọn vẫn được giữ trên trang.') {
  if (signInPending) return signInPending;
  signInPending = new Promise(resolve => {
    const dialog = document.createElement('dialog');
    dialog.className = 'edit-dialog signin-dialog';
    dialog.setAttribute('aria-labelledby', 'signin-title');
    let accepted = false, registering = false;
    dialog.addEventListener('close', () => { dialog.remove(); resolve(accepted); }, {once:true});
    function render() {
      dialog.innerHTML = `<div class="dialog-head"><h2 id="signin-title">${registering?'Tạo tài khoản':'Đăng nhập để tiếp tục'}</h2><button class="btn ghost" data-close aria-label="Đóng">${icon('close')}</button></div><p class="signin-reason">${escape(reason)}</p><form id="signin-form">${registering?'<div class="field"><label for="signin-name">Họ và tên</label><input id="signin-name" name="fullName" required maxlength="120" autocomplete="name"/></div>':''}<div class="field"><label for="signin-id">${admin?'Email quản trị':'Số điện thoại'}</label><input id="signin-id" name="identifier" type="${admin?'email':'tel'}" ${admin?'':'pattern="0[0-9]{9,10}" maxlength="11"'} required autocomplete="username"/></div><div class="field"><label for="signin-password">Mật khẩu</label><input id="signin-password" name="password" type="password" ${registering?'minlength="8" maxlength="72"':''} required autocomplete="${registering?'new-password':'current-password'}"/></div><p id="signin-error" class="error-text" role="alert"></p><button class="btn primary" type="submit">${registering?'Tạo tài khoản':'Đăng nhập'} ${icon('arrow')}</button></form>${admin?'':`<button class="btn ghost signin-switch" data-switch>${registering?'Đã có tài khoản? Đăng nhập':'Chưa có tài khoản? Đăng ký'}</button>`}`;
      dialog.querySelector('[data-close]').onclick = () => dialog.close();
      dialog.querySelector('[data-switch]')?.addEventListener('click', () => { registering = !registering; render(); });
      dialog.querySelector('form').onsubmit = async event => {
        event.preventDefault();
        const form = event.currentTarget, fields = new FormData(form), button = form.querySelector('[type=submit]');
        button.disabled = true; dialog.querySelector('#signin-error').textContent = '';
        const body = registering ? {phone:fields.get('identifier').trim(), password:fields.get('password'), fullName:fields.get('fullName').trim()}
          : {identifier:fields.get('identifier').trim(), password:fields.get('password')};
        try {
          saveSession(await api(registering?'/auth/register':`/auth/login/${area}`, {method:'POST',body:JSON.stringify(body),publicRequest:true}));
          const actions = document.querySelector('.topbar-inner > .account-actions, .admin-topbar > .account-actions');
          if (actions) { actions.outerHTML = accountActions(); document.querySelector('[data-logout]')?.addEventListener('click',logout); }
          accepted = true; dialog.close();
        } catch(error) { dialog.querySelector('#signin-error').textContent = error.message; button.disabled = false; }
      };
    }
    document.body.append(dialog); render(); dialog.showModal();
  }).finally(() => { signInPending = null; });
  return signInPending;
}
const userNav = () => [['home','index.html','Trang chủ'],['result','result_analys.html','Kết quả'],['history','history.html','Lịch sử']].map(([key,href,label]) => `<a href="${href}" class="${page===key?'active':''}" ${page===key?'aria-current="page"':''}>${label}</a>`).join('');
const adminNav = () => [['home','home.html','grid','Bảng điều khiển'],['history','history.html','history','Lịch sử quét'],['statistics','report.html','chart','Thống kê'],['users','user_managerment.html','users','Quản lý người dùng'],['learning','learning.html','check','Duyệt xác nhận'],['profile','profile.html','shield','Tài khoản của tôi']].map(([key,href,i,label]) => `<a href="${href}" class="${page===key?'active':''}" ${page===key?'aria-current="page"':''}>${icon(i)}${label}</a>`).join('');
function accountActions() {
  const identity = account ? `<span class="avatar" aria-hidden="true">${escape((account.fullName || 'U').trim().slice(0,1).toUpperCase())}</span><span class="account-name">${escape(account.fullName || account.phone || 'Quản trị viên')}</span>` : '';
  return account ? `<div class="account-actions">${admin?`<a class="account-profile-link" href="${pageUrl('profile.html')}" aria-label="Tài khoản của tôi">${identity}</a>`:identity}<button class="btn ghost" data-logout title="Đăng xuất" aria-label="Đăng xuất">${icon('logout')}</button></div>` : `<div class="account-actions"><a class="btn secondary" href="login.html">Đăng nhập ${icon('arrow')}</a></div>`;
}
const footer = () => `<footer class="footer"><div class="footer-inner"><span>© ${new Date().getFullYear()} TrashSmart · Mỗi hành động nhỏ, một thay đổi xanh.</span><span>HAUI · Phân loại rác cùng AI <a href="../Admin/login.html">&nbsp;↗ Quản trị</a></span></div></footer>`;
function shell(content) {
  root.innerHTML = admin ? `<div class="admin-shell"><aside class="sidebar">${brand()}<p class="sidebar-label">Quản lý hệ thống</p><nav class="nav" aria-label="Điều hướng quản trị">${adminNav()}</nav><div class="sidebar-bottom"><a href="../User/index.html">${icon('back')} Về trang người dùng</a><p style="margin-top:13px">TrashSmart / Admin workspace</p></div></aside><div class="admin-main"><header class="admin-topbar"><div class="workspace">${icon('shield')} Khu vực quản trị <span class="tag">ADMIN</span></div>${accountActions()}</header><main class="container" id="main">${content}</main>${footer()}</div></div>` : `<header class="topbar"><div class="topbar-inner">${brand()}<nav class="nav" aria-label="Điều hướng chính">${userNav()}</nav>${accountActions()}</div></header><main class="container" id="main">${content}</main>${footer()}`;
  document.querySelector('[data-logout]')?.addEventListener('click',logout);
  document.querySelector('.account-actions a[href="login.html"]')?.addEventListener('click', async event => { event.preventDefault(); await requestSignIn(); });
  root.querySelectorAll('a[href]').forEach(link => {
    const target = new URL(link.getAttribute('href'), location.href);
    if(target.origin === location.origin && target.pathname.endsWith('.html')) link.href=pageUrl(target.href);
  });
}
function heading(eyebrow, title, description, action='') { return `<div class="page-head"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div>${action}</div>`; }
const loading = () => `<div class="loading" role="status"><span class="spinner"></span>Đang tải dữ liệu…</div>`;
function empty(title, message, link='') { return `<div class="empty"><div class="empty-icon">${icon('scan')}</div><h2>${escape(title)}</h2><p>${escape(message)}</p>${link}</div>`; }
function errorView(error) { return `<div class="notice error" role="alert">${icon('info')}<span>${escape(error.message)}</span></div><button class="btn secondary" data-reload>${icon('refresh')} Thử lại</button>`; }
function showError(target, error, retry) {
  target.innerHTML=errorView(error);
  const button=target.querySelector('[data-reload]');
  if(error.authRequired) button.textContent='Đăng nhập lại';
  button?.addEventListener('click', async () => { if(!error.authRequired || await requestSignIn(error.message)) await retry(); });
}
const statuses = {DONE:['Hoàn tất',''],ERROR:['Xử lý lỗi','error'],PROCESSING:['Đang phân tích','pending'],UPLOADED:['Chờ phân tích','pending']};
function statusBadge(status) { const [name,cl] = statuses[status] || ['Chờ phân tích','pending']; return `<span class="status ${cl}">${status==='DONE' ? icon('check'):''}${name}</span>`; }
function materialIcon(code) { const m=materials[code]; return `<span class="material-icon" style="--material:${m?.color || '#718096'}">${icon(m?.icon || 'scan')}</span>`; }

function home() {
  shell(`<section class="hero"><div class="hero-copy"><span class="tag dot">MỘT THÓI QUEN NHỎ. MỘT TƯƠNG LAI XANH.</span><h1>Phân loại đúng.<br>Bắt đầu <em>từ bạn.</em></h1><p>Chụp một bức ảnh, để AI giúp bạn nhận diện vật liệu và tìm cách phân loại phù hợp. Đơn giản hơn mỗi ngày.</p><div class="hero-note">${icon('leaf')} Cùng tạo nên một vòng đời mới cho rác thải.</div></div><div class="upload-card"><div class="upload-top"><h2>Hôm nay bạn muốn phân loại gì?</h2><span class="tag">AI SCAN</span></div><label class="dropzone" id="dropzone" tabindex="0" for="file"><img class="illustration" src="../assets/scan-illustration.svg" alt="Chai nhựa và lon trong khung nhận diện"/><h3>Kéo thả ảnh vào đây</h3><p class="muted">hoặc nhấn để chọn ảnh từ thiết bị</p></label><input class="sr-only" type="file" id="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"/><input hidden type="file" id="camera" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" capture="environment"/><div class="upload-actions"><button class="btn primary" id="scan">${icon('scan')} Phân tích ảnh ${icon('arrow')}</button><button class="btn secondary" id="camera-button" aria-label="Chụp ảnh bằng camera" title="Chụp ảnh">${icon('camera')}</button></div><div id="upload-error" class="error-text" role="alert" style="margin-top:10px"></div><p class="fineprint">JPG, PNG, WebP · Tối đa 10 MB / 12 MP · Một ảnh mỗi lượt</p></div></section><section class="material-strip" aria-label="Vật liệu được hỗ trợ"><div class="intro"><strong>Nhận diện 4 nhóm vật liệu</strong>Phân loại từ những thứ quen thuộc.</div>${Object.entries(materials).map(([code,m])=>`<div class="material-item">${materialIcon(code)}<div><strong>${m.name}</strong><p>${m.hint}</p></div></div>`).join('')}</section><section><div class="section-title"><h2>Ba bước, một thay đổi nhỏ.</h2><span class="eyebrow">DỄ BẮT ĐẦU · DỄ DUY TRÌ</span></div><div class="steps">${[['Chọn hoặc chụp ảnh','Đặt vật thể rõ nét trong khung hình, đủ ánh sáng.'],['Để AI nhận diện','Xem vật liệu, độ tin cậy và gợi ý thu gom.'],['Phân loại & lưu lại','Làm theo hướng dẫn, xem lại mọi lượt quét trong lịch sử.']].map(([t,d],i)=>`<div class="step"><span class="step-number">0${i+1}</span><div><h3>${t}</h3><p>${d}</p></div></div>`).join('')}</div></section>`);
  const drop = document.querySelector('#dropzone'), input=document.querySelector('#file'), camera=document.querySelector('#camera');
  const button=document.querySelector('#scan'), error=document.querySelector('#upload-error');
  let selected, preview, busy = false;
  async function choose(file) {
    if (!file || busy) return;
    error.textContent='';
    const mime=(file.type || '').toLowerCase();
    const recognizedType=['image/jpeg','image/png','image/webp'].includes(mime);
    const unknownType=!mime || mime==='application/octet-stream';
    const recognizedExtension=/\.(jpe?g|png|webp)$/i.test(file.name);
    if ((!recognizedType && !(unknownType && recognizedExtension)) || file.size > 10*1024*1024) { error.textContent='Chọn ảnh JPG, PNG hoặc WebP, tối đa 10 MB.'; input.value=''; camera.value=''; return; }
    const url=URL.createObjectURL(file);
    try {
      const img=new Image(); img.src=url; await img.decode();
      if (img.width>8192 || img.height>8192 || img.width*img.height>12000000) throw new Error('Ảnh vượt giới hạn 12 megapixel hoặc cạnh dài nhất 8192 px. Hãy giảm kích thước ảnh.');
      if(preview) URL.revokeObjectURL(preview); preview=url; selected=file;
      drop.innerHTML=`<img class="preview" src="${url}" alt="Ảnh bạn chọn để phân loại"/><h3 class="upload-filename" title="${escape(file.name)}">${escape(file.name)}</h3><p class="muted">${(file.size/1024/1024).toFixed(2)} MB · Nhấn để đổi ảnh</p>`;
    } catch(e) { URL.revokeObjectURL(url); error.textContent=e.message || 'Không thể mở ảnh này.'; }
  }
  input.addEventListener('change',()=>choose(input.files[0])); camera.addEventListener('change',()=>choose(camera.files[0]));
  drop.addEventListener('keydown', e=>{ if(['Enter',' '].includes(e.key)){e.preventDefault();input.click();} });
  for(const event of ['dragenter','dragover']) drop.addEventListener(event,e=>{e.preventDefault();drop.classList.add('dragging');});
  for(const event of ['dragleave','drop']) drop.addEventListener(event,e=>{e.preventDefault();drop.classList.remove('dragging');});
  drop.addEventListener('drop',e=>choose(e.dataTransfer.files[0]));
  document.querySelector('#camera-button').addEventListener('click',()=>camera.click());
  button.addEventListener('click',async()=>{
    if(busy)return;
    if(!selected){error.textContent='Bạn cần chọn hoặc chụp một ảnh trước khi phân tích.';input.focus();return;}
    busy=true; button.disabled=true; input.disabled=true; camera.disabled=true;
    document.querySelector('#camera-button').disabled=true; drop.setAttribute('aria-disabled','true'); error.textContent='';
    try {
      if(!account || !session?.token) {
        if(!await requestSignIn('Bạn cần đăng nhập để phân tích và lưu kết quả. Ảnh đã chọn vẫn được giữ; đăng nhập xong sẽ tiếp tục gửi ảnh.')) {
          error.textContent='Bạn chưa đăng nhập. Ảnh vẫn được giữ; nhấn Phân tích ảnh khi muốn tiếp tục.'; return;
        }
      }
      for(let attempt=0;attempt<2;attempt++) {
        button.innerHTML='<span class="spinner"></span> Đang phân tích ảnh…';
        try {
          await ensureScanApi();
          const form=new FormData();form.append('file',selected);
          const result=await api('/scans',{method:'POST',body:form}); location.href=pageUrl(`result_analys.html?id=${result.id}`); return;
        } catch(e) {
          if(!e.authRequired || attempt!==0)throw e;
          if(!await requestSignIn(e.message+' Ảnh vẫn được giữ; đăng nhập xong sẽ tiếp tục gửi ảnh.')) {
            error.textContent=e.message+' Ảnh đã chọn vẫn được giữ.'; return;
          }
        }
      }
    } catch(e){error.textContent=e.message;}
    finally {
      busy=false; button.disabled=false; input.disabled=false; camera.disabled=false;
      document.querySelector('#camera-button').disabled=false;drop.removeAttribute('aria-disabled');
      button.innerHTML=`${icon('scan')} Phân tích ảnh ${icon('arrow')}`;
    }
  });
}

let scanApiChecked = false;
async function ensureScanApi() {
  if(scanApiChecked)return;
  let response;
  try { response=await fetch(API+'/system/info',{cache:'no-store',signal:AbortSignal.timeout(10000)}); }
  catch { throw new Error('Không kết nối được BE. Kiểm tra backend trên cổng đã cấu hình; ảnh vẫn được giữ.'); }
  if(!response.ok)throw new Error('BE đang chạy bản cũ hoặc sai project, chưa có API phân tích mới. Cần khởi động lại BE từ thư mục BE/hauiTrash. Ảnh vẫn được giữ.');
  const info=await response.json();
  if(info.scanApiVersion!==1)throw new Error('Phiên bản BE chưa tương thích với trang phân tích. Hãy cập nhật và khởi động lại BE.');
  scanApiChecked=true;
}

const partNames={cap:'Nắp chai',body:'Thân/vỏ chai',label:'Nhãn dán'};
const feedbackStates={OPEN:'Chưa xác nhận',PENDING:'Chờ admin duyệt',APPROVED:'Đã duyệt để học',REJECTED:'Không đưa vào dữ liệu học'};
function hitlMarkup(c) {
  if(!c.learningCaseId)return '';
  if(admin)return `<p class="small muted">${escape(feedbackStates[c.feedbackState] || 'Chưa xác nhận')} · <a href="${pageUrl('learning.html')}">Mở hàng đợi duyệt nhãn</a></p>`;
  if(c.feedbackState&&c.feedbackState!=='OPEN')return `<div class="hitl-feedback"><strong>${escape(feedbackStates[c.feedbackState] || 'Đã gửi xác nhận')}</strong><p class="small">Bạn xác nhận: ${escape(materialName(c.humanMaterial))}. Dự đoán AI ở trên được giữ nguyên.</p></div>`;
  return `<details class="hitl-feedback" ${c.queryRecommended?'open':''}><summary>${c.queryRecommended?'AI chưa chắc chắn · Bạn giúp xác nhận nhé':'Bạn muốn xác nhận hoặc sửa vật liệu?'}</summary><form data-hitl-form data-case-id="${escape(c.learningCaseId)}" data-revision="${escape(c.feedbackRevision ?? 0)}"><fieldset><legend>Vật liệu thực tế của ${escape((partNames[c.partType] || 'bộ phận').toLowerCase())} là gì?</legend>${[...Object.entries(materials).map(([code,m])=>[code,m.name]),['unknown','Không chắc chắn']].map(([code,name])=>`<label class="hitl-option"><input type="radio" name="material" value="${code}" required/> ${escape(name)}</label>`).join('')}</fieldset><div class="field"><label>Cách bạn kiểm chứng<select name="verificationBasis" required><option value="">Chọn cách kiểm chứng</option><option value="PHYSICAL_CHECK">Đã kiểm tra trực tiếp vật liệu</option><option value="PACKAGING_MARK">Đã đọc ký hiệu vật liệu trên bao bì</option><option value="VISUAL_ONLY">Chỉ xem hình ảnh</option><option value="UNSURE">Chưa kiểm chứng / không chắc</option></select></label></div><label class="hitl-option"><input type="checkbox" name="regionCorrect"/> Khung ảnh đánh dấu đúng bộ phận này</label><label class="hitl-option"><input type="checkbox" name="trainingConsent"/> Tôi đồng ý dùng ảnh và xác nhận này để cải thiện model</label><div class="field"><label>Ghi chú (không bắt buộc)<textarea name="note" maxlength="1000" rows="2" placeholder="Ví dụ: tháo nhãn và kiểm tra mặt sau"></textarea></label></div><p class="small muted">Xác nhận được admin kiểm tra trước khi dùng trong đợt huấn luyện mới.</p><p class="error-text" data-hitl-error role="alert"></p><button type="submit" class="btn secondary small">${icon('check')} Gửi xác nhận</button></form></details>`;
}
function bindHitl(target,scanId,getCache) {
  target.addEventListener('submit',async event=>{
    const form=event.target.closest('[data-hitl-form]');if(!form||!target.contains(form))return;
    event.preventDefault();const button=form.querySelector('[type=submit]');if(button.disabled)return;
    const fields=new FormData(form),error=form.querySelector('[data-hitl-error]');error.textContent='';
    if(!fields.get('material')||!fields.get('verificationBasis')){error.textContent='Chọn vật liệu và cách kiểm chứng trước khi gửi.';return;}
    button.disabled=true;
    try {
      const response=await api(`/scans/${scanId}/learning/${encodeURIComponent(form.dataset.caseId)}/feedback`,{method:'POST',body:JSON.stringify({
        material:fields.get('material'),verificationBasis:fields.get('verificationBasis'),regionCorrect:fields.has('regionCorrect'),
        trainingConsent:fields.has('trainingConsent'),note:fields.get('note').trim(),revision:Number(form.dataset.revision)
      })});
      const component=getCache()?.parents.flatMap(p=>p.components).find(c=>c.learningCaseId===form.dataset.caseId);
      const next={...(component || {}),learningCaseId:form.dataset.caseId,feedbackState:response.feedbackState,humanMaterial:response.humanMaterial,feedbackRevision:response.revision};
      if(component)Object.assign(component,next);
      form.closest('.hitl-feedback').outerHTML=hitlMarkup(next);
      toast('Đã gửi xác nhận. Cảm ơn bạn đã giúp cải thiện dữ liệu!');
    }catch(problem){error.textContent=problem.message;button.disabled=false;}
  });
}

async function learningPage() {
  shell(heading('CON NGƯỜI & AI','Duyệt xác nhận vật liệu','Ưu tiên các dự đoán chưa chắc chắn. Chỉ nhãn đã kiểm chứng và được đồng ý mới dùng để học.',
    '<button class="btn secondary" data-hitl-export>Xuất nhãn đã duyệt</button>')+
    '<div class="notice small">Xác nhận và duyệt nhãn chưa thay đổi model đang chạy. Model mới được huấn luyện và đánh giá theo từng phiên bản.</div><div class="filters" style="margin-top:20px"><label>Trạng thái <select data-hitl-state><option value="PENDING">Chờ duyệt</option><option value="OPEN">Chưa có xác nhận</option><option value="APPROVED">Đã duyệt để học</option><option value="REJECTED">Không dùng để học</option></select></label></div><div id="learning-list"></div>');
  const target=document.querySelector('#learning-list'),state=document.querySelector('[data-hitl-state]');let currentPage=0;
  async function load(p=0){
    currentPage=p;target.innerHTML=loading();
    try{
      const data=await api(`/admin/learning?state=${encodeURIComponent(state.value)}&page=${p}&size=12`);
      target.innerHTML=`<p class="small muted">${number(data.pending)} chờ duyệt · ${number(data.approved)} đã duyệt · ${number(data.rejected)} không dùng để học</p><div class="hitl-queue">${data.items.map(c=>{
        const baseEligible=c.regionCorrect&&c.trainingConsent&&Object.hasOwn(materials,c.humanMaterial);
        const userVerified=['PHYSICAL_CHECK','PACKAGING_MARK'].includes(c.verificationBasis),eligible=baseEligible&&userVerified;
        return `<article class="panel hitl-review" data-hitl-case="${escape(c.id)}"><div class="hitl-review-photo"><img src="${imageUrl(c.imageUrl)}" alt="Ảnh bộ phận cần duyệt"/><svg viewBox="0 0 ${Number(c.imageWidth)} ${Number(c.imageHeight)}" preserveAspectRatio="none" aria-hidden="true"><rect x="${Number(c.x1)}" y="${Number(c.y1)}" width="${Number(c.x2)-Number(c.x1)}" height="${Number(c.y2)-Number(c.y1)}"/></svg></div><div><div class="panel-head"><h2>${escape(partNames[c.partType] || 'Bộ phận')} · Lượt #${Number(c.scanId)}</h2><span class="tag">${escape(feedbackStates[c.feedbackState])}</span></div><p>AI: <strong>${escape(materialName(c.predictedMaterial))}</strong> · ${percent(c.materialConfidence)}</p><p>Người dùng: <strong>${escape(materialName(c.humanMaterial))}</strong></p><p class="small muted">${escape(({PHYSICAL_CHECK:'Đã kiểm tra trực tiếp',PACKAGING_MARK:'Đọc ký hiệu trên bao bì',VISUAL_ONLY:'Chỉ xem hình',UNSURE:'Chưa kiểm chứng'})[c.verificationBasis] || 'Chưa trả lời')} · ${c.regionCorrect?'Vùng đúng':'Chưa xác nhận vùng đúng'} · ${c.trainingConsent?'Đồng ý dùng để học':'Chưa đồng ý dùng để học'}</p><p class="small">${escape(c.humanNote || '')}</p><p class="small muted">Model: ${escape(c.modelVersion)}</p>${c.feedbackState==='PENDING'?`<form data-hitl-review data-id="${escape(c.id)}" data-revision="${Number(c.revision)}" data-base-eligible="${Boolean(baseEligible)}" data-user-verified="${userVerified}"><div class="field"><label>Căn cứ xác nhận của admin<select name="adminBasis"><option value="">Dùng căn cứ của người dùng (nếu đủ)</option><option value="VISUAL_REVIEW">Đã đối chiếu hình ảnh và xác nhận</option><option value="PHYSICAL_CHECK">Đã kiểm tra trực tiếp vật liệu</option><option value="PACKAGING_MARK">Đã đọc ký hiệu vật liệu trên bao bì</option></select></label></div><label class="hitl-option"><input type="checkbox" name="confirmedCorrect"/> Tôi xác nhận vật liệu người dùng chọn là đúng</label><div class="field"><label>Ghi chú / lý do loại<textarea name="note" maxlength="1000" rows="2"></textarea></label></div><p class="error-text" role="alert" data-hitl-review-error></p>${!baseEligible?'<p class="small muted">Cần vật liệu xác định, vùng đúng và người dùng đồng ý dùng để học.</p>':!userVerified?'<p class="small muted">Chọn căn cứ, tích xác nhận đúng và ghi chú để admin duyệt bằng kiểm chứng riêng.</p>':''}<div class="hitl-review-actions"><button type="submit" class="btn primary small" name="decision" value="APPROVE" ${eligible?'':'disabled'}>Duyệt để học</button><button type="submit" class="btn secondary small" name="decision" value="REJECT">Không dùng để học</button></div></form>`:`<p class="small">${escape(c.reviewNote || '')}</p><p class="small muted">${c.adminVerificationBasis?'Admin xác nhận: '+escape(({VISUAL_REVIEW:'Đối chiếu hình ảnh',PHYSICAL_CHECK:'Kiểm tra trực tiếp',PACKAGING_MARK:'Ký hiệu bao bì'})[c.adminVerificationBasis] || c.adminVerificationBasis):''}</p>`}</div></article>`;
      }).join('') || empty('Chưa có xác nhận','Các phản hồi phù hợp sẽ xuất hiện tại đây. Hãy chọn trạng thái khác để xem thêm.')}</div><div class="pagination"><span>${number(data.total)} bộ phận</span><div class="pagination-controls"><button class="btn secondary small" data-hitl-page="${p-1}" ${p===0?'disabled':''}>Trước</button><span>Trang ${data.totalPages?p+1:0} / ${number(data.totalPages)}</span><button class="btn secondary small" data-hitl-page="${p+1}" ${p+1>=data.totalPages?'disabled':''}>Sau</button></div></div>`;
      target.querySelectorAll('[data-hitl-page]').forEach(b=>b.onclick=()=>load(Number(b.dataset.hitlPage)));
    }catch(problem){showError(target,problem,()=>load(p));}
  }
  function refreshApproval(form){
    const fields=new FormData(form),basis=fields.get('adminBasis'),independent=Boolean(basis)&&fields.has('confirmedCorrect')&&Boolean(fields.get('note').trim());
    form.querySelector('[value=APPROVE]').disabled=form.dataset.baseEligible!=='true'||!(form.dataset.userVerified==='true'||independent)||Boolean(basis)&&!independent;
  }
  for(const name of ['input','change'])target.addEventListener(name,event=>{const form=event.target.closest('[data-hitl-review]');if(form)refreshApproval(form);});
  state.onchange=()=>load(0);
  target.addEventListener('submit',async event=>{
    const form=event.target.closest('[data-hitl-review]');if(!form)return;event.preventDefault();
    const decision=event.submitter?.value;if(!['APPROVE','REJECT'].includes(decision))return;
    const error=form.querySelector('[data-hitl-review-error]');error.textContent='';const fields=new FormData(form),note=fields.get('note').trim();
    const verificationBasis=fields.get('adminBasis'),confirmedCorrect=fields.has('confirmedCorrect');
    if(decision==='APPROVE'&&verificationBasis&&(!confirmedCorrect||!note)){error.textContent='Tích xác nhận đúng và ghi căn cứ của admin.';return;}
    if(decision==='REJECT'&&!note){error.textContent='Ghi lý do không dùng xác nhận này để học.';return;}
    const buttons=[...form.querySelectorAll('button')],previous=buttons.map(b=>b.disabled);buttons.forEach(b=>b.disabled=true);
    try{await api(`/admin/learning/${encodeURIComponent(form.dataset.id)}/review`,{method:'POST',body:JSON.stringify({decision,note,revision:Number(form.dataset.revision),...(decision==='APPROVE'&&verificationBasis?{verificationBasis,confirmedCorrect}:{})})});await load(currentPage);}
    catch(problem){error.textContent=problem.message;buttons.forEach((b,i)=>b.disabled=previous[i]);}
  });
  document.querySelector('[data-hitl-export]').onclick=async event=>{
    const button=event.currentTarget;button.disabled=true;
    try{
      const records=[];let p=0;
      do{const data=await api(`/admin/learning/export?page=${p}&size=100`);records.push(...data.records);p=data.nextPage;
        if(p!==null&&(!Number.isSafeInteger(p)||p>1000))throw Error('Có quá nhiều nhãn. Hãy xuất từng phần qua API.');
      }while(p!==null);
      if(!records.length){toast('Chưa có nhãn đủ điều kiện đã được duyệt.');return;}
      const blob=new Blob([JSON.stringify({schemaVersion:1,records},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');
      link.href=url;link.download='hitl-approved-materials.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      toast(`Đã xuất ${records.length} nhãn đã duyệt.`);
    }catch(problem){toast(problem.message);}finally{button.disabled=false;}
  };
  await load();
}

function componentMarkup(d) {
  const parts=Array.isArray(d.components)?d.components:[];
  const state=d.componentAnalysisStatus || 'NOT_RUN';
  if(state!=='COMPLETED') {
    const messages={NOT_RUN:'Lượt quét này chưa phân tích bộ phận.',MODEL_UNAVAILABLE:'Model bộ phận chưa sẵn sàng. Kết quả hiện tại là vật liệu của cả chai.',FAILED:'Phân tích bộ phận gặp lỗi. Kết quả nhận diện chai vẫn được giữ.'};
    return `<p class="component-state small muted">${escape(messages[state] || messages.NOT_RUN)}</p>`;
  }
  if(!parts.length)return '<p class="component-state small muted">Đã phân tích nhưng chưa tìm thấy bộ phận đủ điều kiện. Thử ảnh gần và rõ hơn.</p>';
  return `<section class="components" aria-label="Bộ phận của chai"><h4>${number(parts.length)} bộ phận được nhận diện</h4>${parts.map(c=>`<div class="component-row"><button class="component-select" type="button" data-component-box="${escape([c.x1,c.y1,c.x2,c.y2].join(','))}" aria-pressed="false"><span class="component-name">${escape(c.partName || ({cap:'Nắp chai',body:'Thân/vỏ chai',label:'Nhãn dán'})[c.partType] || 'Bộ phận')}</span><span class="status ${c.status==='NEEDS_CONFIRM'?'pending':''}">${escape(c.materialName || materialName(c.material))}</span>${icon('scan')}</button><div class="component-confidence small muted">Vị trí: ${percent(c.detectionConfidence)} · Vật liệu: ${percent(c.materialConfidence)}${c.status==='NEEDS_CONFIRM'?' · Cần kiểm tra thêm':''}</div><p class="small">${escape(c.action || 'Kiểm tra trực tiếp vật liệu trước khi phân loại.')}</p>${hitlMarkup(c)}</div>`).join('')}</section>`;
}
function detectionMarkup(d,i) {
  return `<article class="detection"><div class="detection-top">${materialIcon(d.label)}<div><span class="eyebrow" style="font-size:9px;letter-spacing:1px">CHAI ${String(i+1).padStart(2,'0')}</span><h3>${escape(d.labelDisplay || materialName(d.label))}</h3></div><div class="confidence"><strong>${percent(d.confidence)}</strong><p>Vật liệu cả chai</p></div></div><span class="status ${d.status==='NEEDS_CONFIRM'?'pending':''}">${d.status==='NEEDS_CONFIRM'?'Cần kiểm tra thêm':escape(materialName(d.label))}</span><div class="confidence-bar"><i style="width:${percent(d.confidence)}"></i></div><div class="guidance"><strong>${escape(d.binName || 'Hướng dẫn phân loại')}</strong>${escape(d.action || 'Chưa có hướng dẫn cho vật liệu này. Hãy kiểm tra thủ công.')}</div></article>`;
}
function detailedParentsMarkup(parents) {
  return parents.map((parent,i)=>{
    const found=new Set((parent.components || []).map(c=>c.partType));
    const missing=[['cap','nắp'],['body','thân'],['label','nhãn']].filter(([code])=>!found.has(code)).map(([,name])=>name);
    return `<article class="detailed-bottle"><div class="detailed-bottle-title"><span class="eyebrow">CHAI ${String(i+1).padStart(2,'0')}</span><span class="small muted">${number(parent.components?.length || 0)} bộ phận</span></div>${componentMarkup(parent)}${missing.length?`<p class="small muted">Chưa phát hiện rõ: ${missing.join(', ')}. Bộ phận có thể bị che khuất hoặc model chưa nhận ra.</p>`:''}</article>`;
  }).join('');
}

function resultMarkup(r, modal=false) {
  if(r.status !== 'DONE') return `<div class="notice ${r.status==='ERROR'?'error':'warning'}">${icon('info')}<span>${escape(r.errorMessage || (r.status==='PROCESSING'?'Lượt quét đang được phân tích. Nếu bị gián đoạn quá 5 phút, bạn có thể thử xử lý lại.':'Ảnh đã được lưu và đang chờ phân tích.'))}</span></div><div class="result-photo"><img src="${imageUrl(r.cloudinaryUrl)}" alt="Ảnh của lượt quét"/></div>${['ERROR','UPLOADED','PROCESSING'].includes(r.status)?`<button class="btn primary" data-retry="${r.id}" style="margin-top:20px">${icon('refresh')} Phân tích lại lượt quét này</button>`:''}`;
  if (!r.count) return `<div class="result-layout"><div class="result-photo"><img src="${imageUrl(r.cloudinaryUrl)}" alt="Ảnh đã phân tích"/></div>${empty('Chưa tìm thấy vật thể','Thử chụp gần hơn, đặt vật thể trên nền đơn giản và đảm bảo đủ sáng.',modal?'':`<a class="btn primary" href="index.html">${icon('camera')} Chụp ảnh khác</a>`)}</div>`;
  return `${r.requiresConfirmation?`<div class="notice warning">${icon('info')} Một số vật thể hoặc bộ phận cần kiểm tra thêm. Hãy đối chiếu ảnh trước khi làm theo gợi ý phân loại.</div>`:''}<div class="result-layout"><div><div class="result-photo"><div class="component-photo-stage"><img data-result-image data-original-image="${imageUrl(r.cloudinaryUrl)}" src="${imageUrl(r.annotatedUrl || r.cloudinaryUrl)}" alt="Ảnh nhận diện chai; chọn bộ phận để xem vị trí"/><svg data-component-overlay hidden aria-hidden="true" preserveAspectRatio="none"><rect data-component-rect/><text data-component-label/></svg><svg data-all-component-overlay hidden aria-hidden="true" preserveAspectRatio="none"></svg></div><div class="photo-caption"><span>${icon('scan')} Ảnh từ lượt quét #${r.id}</span><div class="image-toggle"><button class="btn ghost small active" data-image="${imageUrl(r.annotatedUrl || r.cloudinaryUrl)}">Nhận diện</button><button class="btn ghost small" data-image="${imageUrl(r.cloudinaryUrl)}">Ảnh gốc</button><button type="button" class="btn ghost small" data-detail-tab aria-pressed="false">Nhận diện chi tiết</button></div></div></div><p class="small muted component-hint" data-highlight-hint role="status">${r.componentCount?'Chọn một bộ phận để xem vị trí trên ảnh.':''}</p><div class="notice" style="margin-top:18px">${icon('leaf')} Hướng dẫn thu gom mang tính tham khảo. Kiểm tra quy định của điểm thu gom tại địa phương.</div></div><div><div data-standard-summary class="panel" style="margin-bottom:17px"><div class="panel-head" style="margin-bottom:0"><h2>Tổng quan kết quả</h2>${statusBadge(r.status)}</div><div class="result-meta"><div><strong>${number(r.count)}</strong><span>Chai được nhận diện</span></div><div><strong>${percent(r.confidenceAvg)}</strong><span>Độ tin cậy vật liệu cả chai</span></div></div>${r.componentCount?`<p class="component-summary">${number(r.componentCount)} bộ phận · ${r.detections.filter(d=>d.componentAnalysisStatus==='COMPLETED').length} chai đã phân tích bộ phận</p>`:''}<p class="small muted">${date(r.createdAt,true)} · Mã lượt quét #${r.id}${r.componentModelVersion?` · Model bộ phận: ${escape(r.componentModelVersion)}`:''}</p></div><div data-standard-detections class="detection-list">${r.detections.map(detectionMarkup).join('')}</div><section data-detail-panel class="panel detail-panel" hidden aria-label="Nhận diện chi tiết">${detailedParentsMarkup(r.detections)}</section></div></div>`;
}
function bindResult(target, id, reload) {
  const photo=target.querySelector('[data-result-image]'),overlay=target.querySelector('[data-component-overlay]');
  const allOverlay=target.querySelector('[data-all-component-overlay]'),panel=target.querySelector('[data-detail-panel]');
  let selection=0,mode='legacy',cache=null,pending=null,focused=false;
  bindHitl(target,id,()=>cache);
  const clearHighlight=()=>{overlay?.setAttribute('hidden','');allOverlay?.setAttribute('hidden','');target.querySelectorAll('[data-component-box]').forEach(b=>b.setAttribute('aria-pressed','false'));};
  function buttons(active){target.querySelectorAll('[data-image],[data-detail-tab]').forEach(b=>{const selected=b===active;b.classList.toggle('active',selected);b.setAttribute('aria-pressed',String(selected));});}
  async function drawAll(){
    if(!photo||!allOverlay||mode!=='detail'||focused)return;
    const ticket=++selection;try{await photo.decode();}catch{return;}
    if(ticket!==selection||mode!=='detail'||focused||!photo.naturalWidth||!photo.naturalHeight)return;
    allOverlay.replaceChildren();allOverlay.setAttribute('viewBox',`0 0 ${photo.naturalWidth} ${photo.naturalHeight}`);
    const ns='http://www.w3.org/2000/svg',colors={cap:'#c47b20',body:'#266cb4',label:'#9a4fac'};
    panel.querySelectorAll('[data-component-box]').forEach(button=>{
      const box=button.dataset.componentBox.split(',').map(Number);
      if(box.length!==4||box.some(n=>!Number.isFinite(n))||box[0]<0||box[1]<0||box[2]>photo.naturalWidth||box[3]>photo.naturalHeight||box[2]<=box[0]||box[3]<=box[1])return;
      const rect=document.createElementNS(ns,'rect');rect.setAttribute('x',box[0]);rect.setAttribute('y',box[1]);rect.setAttribute('width',box[2]-box[0]);rect.setAttribute('height',box[3]-box[1]);
      const name=button.querySelector('.component-name')?.textContent || 'Bộ phận';const kind=name.startsWith('Nắp')?'cap':name.startsWith('Thân')?'body':'label';
      rect.style.stroke=colors[kind];rect.style.fill=colors[kind]+'18';allOverlay.append(rect);
      const text=document.createElementNS(ns,'text');text.textContent=name;text.setAttribute('x',box[0]+3);text.setAttribute('y',Math.max(20,box[1]-6));text.setAttribute('font-size',Math.max(14,photo.naturalWidth/45));text.style.fill=colors[kind];allOverlay.append(text);
    });
    allOverlay.removeAttribute('hidden');
  }
  function selectMode(next,active){
    ++selection;mode=next;focused=false;clearHighlight();buttons(active);
    const detailed=next==='detail';if(panel)panel.hidden=!detailed;
    target.querySelectorAll('[data-standard-summary],[data-standard-detections]').forEach(el=>el.hidden=detailed);
    if(photo)photo.src=detailed?photo.dataset.originalImage:active.dataset.image;
    const hint=target.querySelector('[data-highlight-hint]');if(hint)hint.textContent=detailed?'Chọn một bộ phận để xem rõ vị trí trên ảnh.':'';
    if(detailed)drawAll();
  }
  function renderDetails(data){
    if(!panel)return;
    panel.innerHTML=`<div class="panel-head"><div><span class="eyebrow">NHẬN DIỆN CHI TIẾT</span><h2>Thành phần của chai</h2></div><span class="tag">Thử nghiệm</span></div><div class="notice warning small">${icon('info')} Kiểm tra trực tiếp vật liệu trước khi phân loại.</div><p class="detail-summary">${number(data.componentCount)} bộ phận · ${number(data.parents.length)} chai</p>${detailedParentsMarkup(data.parents)}<div class="detail-footer"><span class="small muted">${escape(data.modelVersion || '')}</span><button type="button" class="btn ghost small" data-detail-retry>Phân tích lại chi tiết</button></div>`;
    if(mode==='detail')drawAll();
  }
  async function loadDetails(force=false){
    if(cache&&!force){renderDetails(cache);return;}
    if(pending)return pending;
    panel.innerHTML=`<div class="loading" role="status"><span class="spinner"></span> Đang nhận diện các thành phần của chai…</div>`;
    pending=(async()=>{
      try{
        const data=await api(`/scans/${id}/detailed`,{method:'POST',signal:AbortSignal.timeout(180000)});
        if(data.requestId!==Number(id)||data.status!=='COMPLETED'||!Array.isArray(data.parents)||!Number.isFinite(data.componentCount))throw new Error('Dữ liệu nhận diện chi tiết chưa hợp lệ. Kết quả nhận diện cũ vẫn được giữ.');
        cache=data;renderDetails(data);
      }catch(error){
        panel.innerHTML=`<div class="notice error" role="alert">${icon('info')}<span>${escape(error.message)}</span></div><p class="small muted">Bạn vẫn có thể xem ảnh gốc và kết quả nhận diện đã lưu.</p><button type="button" class="btn secondary" data-detail-retry>Thử lại nhận diện chi tiết</button>`;
      }finally{pending=null;}
    })();return pending;
  }
  target.querySelectorAll('[data-image]').forEach(button=>button.addEventListener('click',()=>selectMode(button===target.querySelector('[data-image]')?'legacy':'original',button)));
  target.querySelector('[data-detail-tab]')?.addEventListener('click',()=>{selectMode('detail',target.querySelector('[data-detail-tab]'));loadDetails();});
  if(photo){const size=()=>{if(photo.naturalWidth&&photo.naturalHeight)photo.parentElement.style.setProperty('--photo-ratio',photo.naturalWidth/photo.naturalHeight);};photo.addEventListener('load',()=>{size();if(mode==='detail'&&!focused)drawAll();});size();}
  target.addEventListener('click',async event=>{
    const retry=event.target.closest('[data-detail-retry]');if(retry&&target.contains(retry)){retry.disabled=true;await loadDetails(true);return;}
    const button=event.target.closest('[data-component-box]');if(!button||!target.contains(button)||!photo)return;
    selectMode('detail',target.querySelector('[data-detail-tab]'));focused=true;const ticket=++selection;clearHighlight();
    const box=button.dataset.componentBox.split(',').map(Number);if(box.length!==4||box.some(n=>!Number.isFinite(n))||box[2]<=box[0]||box[3]<=box[1])return;
    photo.src=photo.dataset.originalImage;try{await photo.decode();}catch{return;}
    if(ticket!==selection||!photo.naturalWidth||!photo.naturalHeight)return;
    overlay.setAttribute('viewBox',`0 0 ${photo.naturalWidth} ${photo.naturalHeight}`);
    const rect=overlay.querySelector('rect');rect.setAttribute('x',box[0]);rect.setAttribute('y',box[1]);rect.setAttribute('width',box[2]-box[0]);rect.setAttribute('height',box[3]-box[1]);
    const text=overlay.querySelector('text');text.textContent=button.querySelector('.component-name').textContent;text.setAttribute('x',box[0]+4);text.setAttribute('y',Math.max(20,box[1]-6));text.setAttribute('font-size',Math.max(14,photo.naturalWidth/40));
    overlay.removeAttribute('hidden');button.setAttribute('aria-pressed','true');target.querySelector('[data-highlight-hint]').textContent=`Đang đánh dấu: ${text.textContent}.`;
  });
  target.querySelector('[data-retry]')?.addEventListener('click',async e=>{
    const button=e.currentTarget;button.disabled=true;button.innerHTML='<span class="spinner"></span> Đang phân tích…';
    try{await api(`/scans/${id}/retry`,{method:'POST'});await reload();}
    catch(error){toast(error.message);button.disabled=false;button.innerHTML=`${icon('refresh')} Thử lại`;}
  });
}

function componentStatistics(s) {
  if(!s.totalComponents)return '';
  return `<section class="panel component-statistics"><div class="panel-head"><div><h2>Vật liệu từng bộ phận</h2><p>${number(s.totalComponents)} bộ phận · ${number(s.componentsNeedingConfirmation)} cần kiểm tra thêm</p></div>${icon('leaf')}</div>${materialBars(s.componentMaterials || []).replace('Tính theo số vật thể được nhận diện, không phải số ảnh.','Tính riêng theo số bộ phận; không cộng vào số chai hoặc vật thể.')}</section>`;
}

async function resultPage() {
  shell(`${heading('KẾT QUẢ NHẬN DIỆN','Hiểu vật liệu. Phân loại đúng.','Mỗi vật thể đều có một nơi phù hợp để bắt đầu vòng đời mới.',`<a class="btn secondary" href="index.html">${icon('scan')} Quét ảnh mới</a>`)}<div id="result">${loading()}</div>`);
  const id=new URLSearchParams(location.search).get('id'); const target=document.querySelector('#result');
  if(!/^\d+$/.test(id || '')) { target.innerHTML=empty('Chưa có kết quả để hiển thị','Chọn một ảnh để bắt đầu hoặc mở lại một lượt quét từ lịch sử.',`<a class="btn primary" href="index.html">${icon('scan')} Bắt đầu phân loại</a> <a class="btn secondary" href="history.html">Xem lịch sử</a>`); return; }
  const load=async()=>{target.innerHTML=loading();try{const r=await api(`/scans/${id}`);target.innerHTML=resultMarkup(r);bindResult(target,id,load);}catch(e){showError(target,e,load);}};
  await load();
}

function filtersMarkup(withSearch=true, dates=true, material=true) {
  return `<form class="filters" id="filters">${withSearch?'<div class="field search-field"><label for="search">Tìm kiếm</label><input id="search" name="q" placeholder="'+(page==='users'?'Tên, điện thoại hoặc email':'Mã lượt quét'+(admin?', tên hoặc điện thoại':''))+'" maxlength="120"/></div>':''}${material?`<div class="field"><label for="material">Vật liệu</label><select id="material" name="material"><option value="">Tất cả vật liệu</option>${Object.entries(materials).map(([code,m])=>`<option value="${code}">${m.name}</option>`).join('')}</select></div>`:''}${dates?'<div class="field"><label for="from">Từ ngày</label><input type="date" id="from" name="from"/></div><div class="field"><label for="to">Đến ngày</label><input type="date" id="to" name="to"/></div>':''}<button class="btn primary" type="submit">Áp dụng ${icon('arrow')}</button><button class="btn secondary" type="reset" aria-label="Xóa bộ lọc" title="Xóa bộ lọc">${icon('refresh')}</button></form><div class="error-text" id="filter-error" role="alert"></div>`;
}
function filterValues(form) {
  const data=new FormData(form); const params=new URLSearchParams();
  for(const [key,value] of data) if(value.trim()) params.set(key,value.trim());
  if(params.get('from') && params.get('to') && params.get('from')>params.get('to')) throw new Error('Ngày bắt đầu cần trước hoặc trùng ngày kết thúc.');
  return params;
}
function pagination(data) {
  return `<div class="pagination"><span>${number(data.total)} ${page==='users'?'người dùng':'lượt quét'}${data.total?` · Hiển thị ${number(data.page*data.size+1)}–${number(Math.min((data.page+1)*data.size,data.total))}`:''}</span><div class="pagination-controls"><button class="btn secondary small" data-page="${data.page-1}" ${data.page===0?'disabled':''}>${icon('back')} Trước</button><span>Trang ${data.totalPages?data.page+1:0} / ${data.totalPages}</span><button class="btn secondary small" data-page="${data.page+1}" ${data.page+1>=data.totalPages?'disabled':''}>Sau ${icon('arrow')}</button></div></div>`;
}
function componentHistory(r){return r.componentCount?'<small class="muted">Bộ phận: '+escape((r.componentMaterials || []).map(materialName).join(', ') || 'Chưa xác định')+'</small>':'';}
function scanTable(items, recent=false) {
  return `<div class="table-wrap"><table class="table"><thead><tr><th>Lượt quét</th><th>Người dùng</th><th>Vật liệu</th><th>Trạng thái</th><th>Thời gian</th><th><span class="sr-only">Thao tác</span></th></tr></thead><tbody>${items.map(r=>`<tr><td><div class="table-person"><img class="thumb" src="${imageUrl(r.imageUrl)}" alt="" loading="lazy"/><div><strong>#${r.id}</strong><small>${number(r.count)} chai${r.componentCount?` · ${number(r.componentCount)} bộ phận`:""}</small></div></div></td><td><strong>${escape(r.fullName || 'Người dùng')}</strong><br><small class="muted">${escape(r.phone || '—')}</small></td><td>${escape(r.materials.map(materialName).join(', ') || 'Chưa xác định')}<br/>${componentHistory(r)}</td><td>${statusBadge(r.status)}</td><td>${date(r.createdAt,true)}</td><td><button class="btn ghost small" data-detail="${r.id}" aria-label="Xem chi tiết lượt quét ${r.id}">${icon('eye')}</button></td></tr>`).join('')}</tbody></table></div>`;
}
function scanCards(items) {
  return `<div class="history-grid">${items.map(r=>`<a class="scan-card" href="result_analys.html?id=${r.id}" aria-label="Xem lượt quét ${r.id}"><div class="scan-image"><img src="${imageUrl(r.imageUrl)}" alt="Ảnh lượt quét ${r.id}" loading="lazy"/>${statusBadge(r.status)}</div><div class="scan-body"><span class="small muted">${date(r.createdAt,true)} · #${r.id}</span><h3>${escape(r.materials.map(materialName).join(' · ') || (r.status==='ERROR'?'Chưa có kết quả':'Chờ nhận diện'))}</h3><div class="small muted">${number(r.count)} chai${r.componentCount?` · ${number(r.componentCount)} bộ phận`:""}${r.requiresConfirmation?' · Cần kiểm tra thêm':''}</div>${componentHistory(r)}<div class="scan-foot"><span>${r.status==='DONE'?percent(r.confidenceAvg)+' độ tin cậy':'Xem trạng thái xử lý'}</span><span style="color:var(--green)">Xem kết quả ${icon('arrow')}</span></div></div></a>`).join('')}</div>`;
}
async function detailDialog(id) {
  let dialog=document.querySelector('#detail-dialog'); if(dialog) dialog.remove();
  dialog=document.createElement('dialog'); dialog.id='detail-dialog'; dialog.setAttribute('aria-labelledby','detail-title');
  dialog.innerHTML=`<div class="dialog-head"><h2 id="detail-title">Chi tiết lượt quét #${id}</h2><button class="btn ghost" data-close aria-label="Đóng">${icon('close')}</button></div><div id="dialog-content">${loading()}</div>`;
  document.body.append(dialog); dialog.querySelector('[data-close]').onclick=()=>dialog.close(); dialog.showModal();
  const target=dialog.querySelector('#dialog-content');
  const load=async()=>{try{const r=await api(`/scans/${id}`);target.innerHTML=resultMarkup(r,true);bindResult(target,id,load);}catch(e){showError(target,e,load);}};
  await load();
}
function bindDetails(target) { target.querySelectorAll('[data-detail]').forEach(b=>b.addEventListener('click',()=>detailDialog(b.dataset.detail))); }
async function historyPage() {
  shell(`${heading(admin?'JOURNAL / LỊCH SỬ QUÉT':'NHẬT KÝ XANH',admin?'Mọi lượt quét, một nơi quản lý.':'Nhìn lại những hành động xanh.',admin?'Theo dõi ảnh, kết quả và trạng thái xử lý của toàn bộ hệ thống.':'Ảnh và kết quả phân loại của bạn được lưu tại đây để dễ dàng xem lại.',admin?'':`<a class="btn primary" href="index.html">${icon('scan')} Quét ảnh mới</a>`)}${filtersMarkup()}<section id="history">${loading()}</section>`);
  const target=document.querySelector('#history'), form=document.querySelector('#filters');
  let params=new URLSearchParams(); let request=0;
  const load=async(p=0)=>{
    const order=++request;target.innerHTML=loading();params.set('page',p);params.set('size',admin?'12':'9');
    try { const data=await api(`${admin?'/admin':''}/scans?${params}`); if(order!==request)return;
      target.innerHTML=data.items.length ? (admin?`<div class="panel table-panel">${scanTable(data.items)}</div>`:scanCards(data.items))+pagination(data) : empty('Chưa có lượt quét nào','Lịch sử sẽ hiển thị tại đây. Nếu đang dùng bộ lọc, hãy thử mở rộng khoảng tìm kiếm.',admin?'':`<a class="btn primary" href="index.html">${icon('scan')} Phân loại ảnh đầu tiên</a>`);
      target.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>load(Number(b.dataset.page))));bindDetails(target);
    } catch(e){if(order===request)showError(target,e,()=>load(p));}
  };
  form.onsubmit=e=>{e.preventDefault();try{params=filterValues(form);document.querySelector('#filter-error').textContent='';load();}catch(error){document.querySelector('#filter-error').textContent=error.message;}};
  form.onreset=()=>{params=new URLSearchParams();document.querySelector('#filter-error').textContent='';load();};
  await load();
}

function stat(label,value,hint,i) { return `<div class="stat"><div class="stat-top"><span>${label}</span>${icon(i)}</div><strong class="stat-value">${value}</strong><small>${hint}</small></div>`; }
function chart(data) {
  if(!data.some(b=>b.count))return empty('Chưa có dữ liệu','Biểu đồ sẽ xuất hiện khi có lượt quét trong khoảng ngày đã chọn.');
  const width=640,height=220,left=37,top=16,bottom=34,plotH=height-top-bottom,max=Math.max(1,...data.map(d=>d.count)), step=(width-left-15)/data.length;
  return `<svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Biểu đồ số lượt quét theo ngày"><title>Lượt quét theo ngày</title>${[0,.5,1].map(f=>`<line x1="${left}" y1="${top+plotH*(1-f)}" x2="${width-10}" y2="${top+plotH*(1-f)}" stroke="#e7ece1" stroke-dasharray="3 4"/><text x="${left-9}" y="${top+plotH*(1-f)+4}" text-anchor="end">${Math.round(max*f)}</text>`).join('')}${data.map((d,i)=>`<rect x="${left+i*step+step*.2}" y="${top+plotH*(1-d.count/max)}" width="${Math.max(1,step*.6)}" height="${plotH*d.count/max}" rx="${Math.min(4,step*.15)}" fill="${i===data.length-1?'#a7c588':'#2b7054'}"><title>${escape(d.label)}: ${d.count} lượt quét</title></rect>${i===0||i===data.length-1||i%Math.max(1,Math.ceil(data.length/6))===0?`<text x="${left+i*step+step/2}" y="${height-10}" text-anchor="middle">${d.label.slice(8)}/${d.label.slice(5,7)}</text>`:''}`).join('')}</svg><details class="small muted"><summary>Xem dữ liệu theo ngày</summary><div class="table-wrap" style="max-height:200px"><table class="table"><thead><tr><th>Ngày</th><th>Lượt quét</th></tr></thead><tbody>${data.map(d=>`<tr><td>${escape(d.label)}</td><td>${number(d.count)}</td></tr>`).join('')}</tbody></table></div></details>`;
}
function materialBars(buckets) {
  const total=buckets.reduce((s,b)=>s+b.count,0);
  return `<div class="material-bars">${Object.entries(materials).map(([code,m])=>{const count=buckets.find(b=>b.label===code)?.count||0;return `<div style="--material:${m.color}"><div class="bar-label"><span>${m.name}</span><span>${number(count)} <span class="muted">· ${total?Math.round(count/total*100):0}%</span></span></div><div class="bar-track"><i style="width:${total?count/total*100:0}%"></i></div></div>`;}).join('')}</div>${buckets.some(b=>!materials[b.label])?'<p class="small muted" style="margin-top:18px">Có vật liệu cũ/chưa xác định ngoài bốn nhóm hiện tại.</p>':''}<p class="small muted" style="margin-top:23px">Tính theo số vật thể được nhận diện, không phải số ảnh.</p>`;
}
async function dashboard(statistics=false) {
  shell(`${heading(statistics?'INSIGHTS / THỐNG KÊ':'OVERVIEW / TỔNG QUAN',statistics?'Từ dữ liệu đến góc nhìn xanh.':'Một góc nhìn, toàn bộ hệ thống.',statistics?'Theo dõi hoạt động nhận diện và phân bố vật liệu trong khoảng thời gian bạn chọn.':'Nắm bắt hoạt động phân loại và những lượt quét mới nhất.')} ${statistics?filtersMarkup(false,true,false):'<div class="notice">'+icon('calendar')+' Tổng quan hoạt động trong 30 ngày gần nhất · Múi giờ Việt Nam (UTC+7)</div>'}<section id="dashboard">${loading()}</section>`);
  const target=document.querySelector('#dashboard'); let params=new URLSearchParams(); let request=0;
  const load=async()=>{const order=++request;target.innerHTML=loading();try{
    const s=await api(`/admin/statistics?${params}`);
    const recent=statistics?null:await api('/admin/scans?size=5'); if(order!==request)return;
    target.innerHTML=`<div class="stats">${stat('Tổng lượt quét',number(s.totalScans),'Trong khoảng ngày đã chọn','scan')}${stat('Người dùng',number(s.totalUsers),number(s.activeUsers)+' tài khoản đang hoạt động','users')}${stat('Chai nhận diện',number(s.totalObjects),'Số chai, không cộng bộ phận','leaf')}${stat('Độ tin cậy TB',percent(s.confidenceAvg),'Điểm model · Không phải độ chính xác','chart')}</div><div class="two-col"><section class="panel"><div class="panel-head"><div><h2>Nhịp hoạt động</h2><p>${date(s.from)} — ${date(s.to)}</p></div><span class="tag">LƯỢT QUÉT</span></div>${chart(s.daily)}<div class="chart-summary"><span><i class="legend-dot"></i>Lượt quét mỗi ngày</span><span>${number(s.completedScans)} hoàn tất · ${number(s.failedScans)} lỗi</span></div></section><section class="panel"><div class="panel-head"><div><h2>Vật liệu cả chai</h2><p>Kết quả phân loại trên vùng ảnh cả chai</p></div>${icon('leaf')}</div>${materialBars(s.materials)}</section></div>${statistics?`<div class="panel"><div class="panel-head"><div><h2>Trạng thái xử lý</h2><p>Dữ liệu thực tế trong khoảng ngày đã chọn</p></div></div><div class="split-metrics"><div class="mini-metric"><strong>${number(s.completedScans)}</strong><span>Lượt quét hoàn tất</span></div><div class="mini-metric"><strong>${number(s.failedScans)}</strong><span>Lượt xử lý lỗi</span></div><div class="mini-metric"><strong>${number(s.needsConfirmation)}</strong><span>Vật thể cần kiểm tra thêm</span></div></div></div>`:`<section class="panel table-panel"><div class="panel-head"><div><h2>Lượt quét gần đây</h2><p>Những hoạt động mới nhất trên hệ thống</p></div><a class="btn ghost small" href="history.html">Xem tất cả ${icon('arrow')}</a></div>${recent.items.length?scanTable(recent.items,true):empty('Hệ thống chưa có lượt quét','Lượt quét mới sẽ hiển thị tại đây ngay sau khi được tạo.')}</section>`}`;
    target.insertAdjacentHTML('beforeend',componentStatistics(s));
    bindDetails(target);
  }catch(e){if(order===request)showError(target,e,load);}};
  if(statistics){const form=document.querySelector('#filters');form.onsubmit=e=>{e.preventDefault();try{params=filterValues(form);document.querySelector('#filter-error').textContent='';load();}catch(e){document.querySelector('#filter-error').textContent=e.message;}};form.onreset=()=>{params=new URLSearchParams();document.querySelector('#filter-error').textContent='';load();};}
  await load();
}

async function editUser(user,reload) {
  document.querySelector('#user-dialog')?.remove();const dialog=document.createElement('dialog');dialog.id='user-dialog';dialog.className='edit-dialog';dialog.setAttribute('aria-labelledby','edit-title');
  dialog.innerHTML=`<div class="dialog-head"><div><span class="eyebrow">TÀI KHOẢN #${user.id}</span><h2 id="edit-title">Chỉnh sửa người dùng</h2></div><button class="btn ghost" data-close aria-label="Đóng">${icon('close')}</button></div><form id="edit-form"><div class="field"><label for="edit-name">Họ và tên</label><input id="edit-name" name="fullName" value="${escape(user.fullName)}" required maxlength="120"/></div><div class="field"><label for="edit-phone">Số điện thoại</label><input id="edit-phone" name="phone" type="tel" value="${escape(user.phone)}" required pattern="0[0-9]{9,10}" maxlength="11"/></div><div class="field"><label for="edit-email">Email (không bắt buộc)</label><input id="edit-email" name="email" type="email" value="${escape(user.email)}" maxlength="120"/></div><label class="check-label"><input type="checkbox" name="active" ${user.active?'checked':''}/> Cho phép tài khoản hoạt động</label><p class="small muted">Khi bị khóa, người dùng sẽ không thể tiếp tục truy cập API, kể cả với phiên đăng nhập hiện có.</p><p class="error-text" id="edit-error" role="alert"></p><div class="dialog-actions"><button type="button" class="btn secondary" data-cancel>Hủy</button><button class="btn primary" type="submit">Lưu thay đổi ${icon('check')}</button></div></form>`;
  document.body.append(dialog);dialog.querySelector('[data-close]').onclick=()=>dialog.close();dialog.querySelector('[data-cancel]').onclick=()=>dialog.close();dialog.showModal();
  dialog.querySelector('form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget;const values=new FormData(form);const button=form.querySelector('[type=submit]');button.disabled=true;dialog.querySelector('#edit-error').textContent='';
    try{await api(`/admin/users/${user.id}`,{method:'PATCH',body:JSON.stringify({fullName:values.get('fullName').trim(),phone:values.get('phone').trim(),email:values.get('email').trim(),active:values.has('active')})});dialog.close();toast('Đã cập nhật người dùng.');await reload();}
    catch(error){dialog.querySelector('#edit-error').textContent=error.message;button.disabled=false;}
  };
}
async function usersPage() {
  shell(`${heading('PEOPLE / NGƯỜI DÙNG','Những người cùng tạo thay đổi.','Tìm kiếm, cập nhật thông tin và quản lý quyền truy cập của tài khoản người dùng.')} ${filtersMarkup(true,false,false)}<section id="users">${loading()}</section>`);
  const target=document.querySelector('#users'), form=document.querySelector('#filters');let params=new URLSearchParams();let request=0;
  const load=async(p=0)=>{const order=++request;target.innerHTML=loading();params.set('page',p);params.set('size','12');try{const data=await api(`/admin/users?${params}`);if(order!==request)return;
    target.innerHTML=data.items.length?`<div class="panel table-panel"><div class="table-wrap"><table class="table"><thead><tr><th>Người dùng</th><th>Số điện thoại</th><th>Email</th><th>Trạng thái</th><th>Ngày tham gia</th><th>Thao tác</th></tr></thead><tbody>${data.items.map(u=>`<tr><td><div class="table-person"><span class="avatar">${escape((u.fullName || 'U').slice(0,1).toUpperCase())}</span><div><strong>${escape(u.fullName || 'Người dùng')}</strong><small>#${u.id} · USER</small></div></div></td><td>${escape(u.phone)}</td><td>${escape(u.email || '—')}</td><td><span class="status ${u.active?'':'error'}">${u.active?'Đang hoạt động':'Đã khóa'}</span></td><td>${date(u.createdAt)}</td><td><button class="btn secondary small" data-edit="${u.id}">${icon('edit')} Chỉnh sửa</button></td></tr>`).join('')}</tbody></table></div></div>${pagination(data)}`:empty('Chưa tìm thấy người dùng','Thử tìm theo tên, số điện thoại hoặc email khác.');
    target.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>editUser(data.items.find(u=>u.id===Number(b.dataset.edit)),()=>load(p)));
    target.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>load(Number(b.dataset.page)));
  }catch(e){if(order===request)showError(target,e,()=>load(p));}};
  form.onsubmit=e=>{e.preventDefault();params=filterValues(form);load();};form.onreset=()=>{params=new URLSearchParams();load();};await load();
}

function authPage(register=false) {
  const title=register?'Bắt đầu hành trình xanh.':admin?'Chào mừng trở lại.':'Rất vui được gặp lại bạn.';
  root.innerHTML=`<div class="auth-layout"><aside class="auth-story">${brand()}<div><span class="eyebrow">MỖI NGÀY MỘT CHÚT XANH HƠN</span><h1 style="margin-top:16px">Một bức ảnh.<br>Một lựa chọn đúng.<br>Một tương lai xanh.</h1><p>Nhận diện vật liệu, phân loại có trách nhiệm và theo dõi hành trình thay đổi của bạn.</p><img class="illustration" src="../assets/scan-illustration.svg" alt="Chai nhựa và lon được nhận diện để tái chế"/></div><small>TRASHSMART · HAUI · PHÂN LOẠI CÙNG AI</small></aside><main class="auth-main" id="main"><div class="auth-form"><div class="mobile-brand">${brand()}</div><a class="back" href="../User/index.html">${icon('back')} Về trang chủ</a><div class="eyebrow">${admin?'ADMIN WORKSPACE':register?'THAM GIA TRASHSMART':'CHÀO BẠN ĐẾN TRASHSMART'}</div><h1>${title}</h1><p>${admin?'Đăng nhập bằng tài khoản quản trị đã được cấp.':register?'Tạo tài khoản để lưu kết quả và lịch sử phân loại.':'Đăng nhập để tiếp tục phân loại và xem lại lịch sử của bạn.'}</p><form id="auth-form">${register?'<div class="field"><label for="fullName">Họ và tên</label><input id="fullName" name="fullName" required maxlength="120" autocomplete="name" placeholder="Nguyễn Văn An"/></div>':''}<div class="field"><label for="identifier">${admin?'Email quản trị':'Số điện thoại'}</label><input id="identifier" name="identifier" type="${admin?'email':'tel'}" ${admin?'':'pattern="0[0-9]{9,10}" maxlength="11"'} required autocomplete="username" placeholder="${admin?'admin@example.com':'Nhập số điện thoại'}"/></div><div class="field"><label for="password">Mật khẩu</label><div class="password-wrap"><input id="password" name="password" type="password" required ${register?'minlength="8" maxlength="72"':''} autocomplete="${register?'new-password':'current-password'}" placeholder="${register?'Ít nhất 8 ký tự':'Nhập mật khẩu'}"/><button type="button" id="toggle-password" aria-label="Hiện mật khẩu" aria-pressed="false">${icon('eye')}</button></div></div><div id="auth-error" class="error-text" role="alert"></div><button type="submit" class="btn primary">${register?'Tạo tài khoản':'Đăng nhập'} ${icon('arrow')}</button></form>${admin?'<p class="switch">Tài khoản được cấp bởi người vận hành hệ thống.</p>':`<p class="switch">${register?'Đã có tài khoản?':'Chưa có tài khoản?'} <a href="${register?'login':'register'}.html${location.search}">${register?'Đăng nhập':'Đăng ký ngay'}</a></p>`}<p class="fineprint" style="margin-top:30px">${icon('shield')} Thông tin đăng nhập được bảo vệ bằng mã hóa mật khẩu.</p></div></main></div>`;
  document.querySelector('#toggle-password').onclick=e=>{const input=document.querySelector('#password');const show=input.type==='password';input.type=show?'text':'password';e.currentTarget.setAttribute('aria-pressed',String(show));e.currentTarget.setAttribute('aria-label',show?'Ẩn mật khẩu':'Hiện mật khẩu');};
  document.querySelector('#auth-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget;const data=new FormData(form);const button=form.querySelector('[type=submit]');const error=document.querySelector('#auth-error');error.textContent='';button.disabled=true;
    try { const body=register?{phone:data.get('identifier').trim(),password:data.get('password'),fullName:data.get('fullName').trim()}:{identifier:data.get('identifier').trim(),password:data.get('password')};
      const result=await api(register?'/auth/register':`/auth/login/${area}`,{method:'POST',body:JSON.stringify(body),publicRequest:true});
      saveSession(result);
      const next=new URLSearchParams(location.search).get('next');const allowed=admin?['home.html','history.html','report.html','user_managerment.html','profile.html']:['index.html','history.html','result_analys.html'];
      location.href=pageUrl(next && allowed.includes(next.split('?')[0]) && !next.includes('#') ? next : admin?'home.html':'index.html');
    } catch(err){error.textContent=err.message;button.disabled=false;}
  };
}

async function profilePage() {
  shell(`${heading('MY ACCOUNT / TÀI KHOẢN CỦA TÔI','Thông tin của bạn.','Cập nhật hồ sơ và bảo mật tài khoản quản trị đang đăng nhập.')}<section id="profile-content">${loading()}</section>`);
  const target=document.querySelector('#profile-content');
  const load=async()=>{
    target.innerHTML=loading();
    try {
      const capability=await api('/system/info',{publicRequest:true});
      if(capability.adminProfileApiVersion!==1)throw new Error('BE đang chạy bản chưa có chức năng hồ sơ admin. Hãy khởi động lại BE sau khi cập nhật.');
      let profile=await api('/admin/profile');
      target.innerHTML=`<div class="profile-layout"><aside class="panel profile-summary"><span class="avatar profile-avatar" data-profile-avatar>${escape((profile.fullName || 'A').slice(0,1).toUpperCase())}</span><h2 data-profile-name>${escape(profile.fullName || 'Quản trị viên')}</h2><p class="muted small" data-profile-email>${escape(profile.email)}</p><span class="tag">${icon('shield')} QUẢN TRỊ VIÊN</span><div class="profile-id"><span>Mã tài khoản</span><strong>#${profile.id}</strong></div><p class="small muted">Thông tin và lịch sử hoạt động được gắn với tài khoản này.</p></aside><div class="profile-forms"><section class="panel"><div class="panel-head"><div><h2>Thông tin cá nhân</h2><p>Email được dùng để đăng nhập vào trang quản trị.</p></div>${icon('edit')}</div><form id="profile-form"><div class="field"><label for="profile-name">Họ và tên</label><input id="profile-name" name="fullName" required maxlength="120" autocomplete="name" value="${escape(profile.fullName)}"/></div><div class="profile-fields"><div class="field"><label for="profile-phone">Số điện thoại</label><input id="profile-phone" name="phone" type="tel" required pattern="0[0-9]{9,10}" maxlength="11" autocomplete="tel" value="${escape(profile.phone)}"/></div><div class="field"><label for="profile-email">Email đăng nhập</label><input id="profile-email" name="email" type="email" required maxlength="120" autocomplete="email" value="${escape(profile.email)}"/></div></div><div class="field"><label for="profile-confirm-password">Mật khẩu hiện tại khi đổi email</label><input id="profile-confirm-password" name="currentPassword" type="password" maxlength="72" autocomplete="current-password" placeholder="Chỉ cần nhập khi đổi email"/><span class="small muted">Đổi email cần xác nhận mật khẩu; các phiên cũ sẽ hết hiệu lực sau khi lưu.</span></div><p class="error-text" id="profile-error" role="alert"></p><p class="profile-success" id="profile-success" role="status"></p><div class="profile-actions"><button class="btn secondary" type="reset">Hoàn tác</button><button class="btn primary" type="submit">${icon('check')} Lưu thông tin</button></div></form></section><section class="panel"><div class="panel-head"><div><h2>Đổi mật khẩu</h2><p>Xác nhận bằng mật khẩu hiện tại để bảo vệ tài khoản của bạn.</p></div>${icon('shield')}</div><form id="password-form"><div class="field"><label for="password-current">Mật khẩu hiện tại</label><input id="password-current" name="currentPassword" type="password" required maxlength="72" autocomplete="current-password"/></div><div class="profile-fields"><div class="field"><label for="password-new">Mật khẩu mới</label><input id="password-new" name="newPassword" type="password" required minlength="8" maxlength="72" autocomplete="new-password"/></div><div class="field"><label for="password-confirm">Nhập lại mật khẩu mới</label><input id="password-confirm" name="confirmation" type="password" required minlength="8" maxlength="72" autocomplete="new-password"/></div></div><p class="small muted">Ít nhất 8 ký tự, tối đa 72 byte UTF-8. Các phiên đăng nhập trước sẽ hết hiệu lực; trang này tiếp tục bằng phiên mới.</p><p class="error-text" id="password-error" role="alert"></p><p class="profile-success" id="password-success" role="status"></p><div class="profile-actions"><button class="btn primary" type="submit">${icon('shield')} Cập nhật mật khẩu</button></div></form></section></div></div>`;
      function refreshIdentity(result) {
        saveSession(result);profile=result.account;
        const actions=document.querySelector('.admin-topbar > .account-actions');
        actions.outerHTML=accountActions();document.querySelector('[data-logout]').addEventListener('click',logout);
        target.querySelector('[data-profile-name]').textContent=profile.fullName || 'Quản trị viên';
        target.querySelector('[data-profile-email]').textContent=profile.email;
        target.querySelector('[data-profile-avatar]').textContent=(profile.fullName || 'A').slice(0,1).toUpperCase();
      }
      const form=target.querySelector('#profile-form'), email=target.querySelector('#profile-email'), confirm=target.querySelector('#profile-confirm-password');
      email.addEventListener('input',()=>{confirm.required=email.value.trim().toLowerCase()!==(profile.email || '').toLowerCase();});
      form.addEventListener('reset',()=>{
        setTimeout(()=>{
          form.elements.fullName.value=profile.fullName || '';form.elements.phone.value=profile.phone || '';form.elements.email.value=profile.email || '';
          confirm.value='';confirm.required=false;target.querySelector('#profile-error').textContent='';target.querySelector('#profile-success').textContent='';
        },0);
      });
      form.onsubmit=async event=>{
        event.preventDefault();const fields=new FormData(form), button=form.querySelector('[type=submit]');
        target.querySelector('#profile-error').textContent='';target.querySelector('#profile-success').textContent='';button.disabled=true;
        try {
          refreshIdentity(await api('/admin/profile',{method:'PATCH',body:JSON.stringify({fullName:fields.get('fullName').trim(),phone:fields.get('phone').trim(),email:fields.get('email').trim(),currentPassword:fields.get('currentPassword')})}));
          confirm.value='';confirm.required=false;
          form.elements.fullName.value=profile.fullName;form.elements.phone.value=profile.phone;email.value=profile.email;
          target.querySelector('#profile-success').textContent='Đã cập nhật thông tin tài khoản.';
        }catch(error){target.querySelector('#profile-error').textContent=error.message;}
        finally{button.disabled=false;}
      };
      const passwordForm=target.querySelector('#password-form');
      passwordForm.onsubmit=async event=>{
        event.preventDefault();const fields=new FormData(passwordForm), button=passwordForm.querySelector('[type=submit]');
        target.querySelector('#password-error').textContent='';target.querySelector('#password-success').textContent='';
        if(fields.get('newPassword')!==fields.get('confirmation')){target.querySelector('#password-error').textContent='Mật khẩu nhập lại chưa khớp.';return;}
        button.disabled=true;
        try {
          refreshIdentity(await api('/admin/profile/password',{method:'POST',body:JSON.stringify({currentPassword:fields.get('currentPassword'),newPassword:fields.get('newPassword')})}));
          passwordForm.reset();confirm.value='';
          target.querySelector('#password-success').textContent='Đã đổi mật khẩu. Các phiên đăng nhập cũ đã hết hiệu lực.';
        }catch(error){target.querySelector('#password-error').textContent=error.message;}
        finally{button.disabled=false;}
      };
    }catch(error){showError(target,error,load);}
  };
  await load();
}

async function boot() {
  if(['login','register'].includes(page)){authPage(page==='register'&&!admin);return;}
  shell(loading());
  let authIssue;
  if(session?.token){
    try {
      account=await api('/auth/me');
      if(account.role!==(admin?'ADMIN':'USER')) {
        sessionStorage.removeItem(sessionKey);session=null;account=null;
        authIssue='Tài khoản không có quyền truy cập khu vực này. Vui lòng đăng nhập bằng tài khoản phù hợp.';
      }
    } catch(e) {
      if(e.authRequired)authIssue=e.message;
      else {showError(document.querySelector('#main'),e,boot);return;}
    }
  }
  if((admin || page!=='home') && !session?.token) {
    shell(empty('Đăng nhập để tiếp tục',authIssue || 'Bạn cần đăng nhập để xem dữ liệu của mình.', '<button class="btn primary" data-signin>Đăng nhập</button>'));
    document.querySelector('[data-signin]').onclick=async()=>{if(await requestSignIn(authIssue || 'Đăng nhập để tiếp tục xem trang này.'))await boot();};
    return;
  }
  if(authIssue)toast(authIssue);
  if(page==='home')return admin?dashboard():home();
  if(page==='history')return historyPage();
  if(page==='result')return resultPage();
  if(page==='statistics')return dashboard(true);
  if(page==='users')return usersPage();
  if(page==='profile' && admin)return profilePage();
  if(page==='learning' && admin)return learningPage();
}
boot().catch(error=>{if(!document.querySelector('#main'))shell('');showError(document.querySelector('#main'),error,boot);});
document.addEventListener('error',e=>{if(e.target instanceof HTMLImageElement && !e.target.src.endsWith('/assets/logo.svg')){e.target.src='../assets/logo.svg';e.target.style.objectFit='contain';}},true);
document.addEventListener('click',event=>{
  const link=event.target.closest?.('a[href]');
  if(!link)return;
  const target=new URL(link.getAttribute('href'),location.href);
  if(target.origin===location.origin && target.pathname.endsWith('.html'))link.href=pageUrl(target.href);
},true);
