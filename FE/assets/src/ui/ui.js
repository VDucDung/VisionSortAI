// ui: page-scoped state and behavior. No browser work runs at import time.
export function createUi(context) {
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

  const imageUrl = (url) => { try { const u = new context.window.URL(url); return ['http:','https:'].includes(u.protocol) ? escape(u.href) : '../assets/logo.svg'; } catch { return '../assets/logo.svg'; } };

  const materialName = code => materials[code]?.name || 'Chưa xác định';

  const brand = () => `<a class="brand" href="${context.runtime.admin ? 'home.html' : 'index.html'}" aria-label="TrashSmart — Trang chủ"><img src="../assets/logo.svg" alt=""/><div><strong>Trash<span>Smart</span></strong><small class="brand-sub">${context.runtime.admin ? 'Không gian quản trị' : 'Phân loại hôm nay · Xanh ngày mai'}</small></div></a>`;

  let toastTimer;

  function toast(message) {
    context.window.document.querySelector('.toast')?.remove();
    const el = context.window.document.createElement('div'); el.className='toast'; el.setAttribute('role','status'); el.textContent=message;
    context.window.document.body.append(el); context.window.clearTimeout(toastTimer); toastTimer=context.window.setTimeout(() => el.remove(), 4500);
  }

  const userNav = () => [['home','index.html','Trang chủ'],['result','result_analys.html','Kết quả'],['history','history.html','Lịch sử']].map(([key,href,label]) => `<a href="${href}" class="${context.runtime.page===key?'active':''}" ${context.runtime.page===key?'aria-current="page"':''}>${label}</a>`).join('');

  const adminNav = () => [['home','home.html','grid','Bảng điều khiển'],['history','history.html','history','Lịch sử quét'],['statistics','report.html','chart','Thống kê'],['users','user_managerment.html','users','Quản lý người dùng'],['learning','learning.html','check','Duyệt xác nhận'],['profile','profile.html','shield','Tài khoản của tôi']].map(([key,href,i,label]) => `<a href="${href}" class="${context.runtime.page===key?'active':''}" ${context.runtime.page===key?'aria-current="page"':''}>${icon(i)}${label}</a>`).join('');

  function accountActions() {
    const identity = context.runtime.account ? `<span class="avatar" aria-hidden="true">${escape((context.runtime.account.fullName || 'U').trim().slice(0,1).toUpperCase())}</span><span class="account-name">${escape(context.runtime.account.fullName || context.runtime.account.phone || 'Quản trị viên')}</span>` : '';
    return context.runtime.account ? `<div class="account-actions">${context.runtime.admin?`<a class="account-profile-link" href="${context.runtime.pageUrl('profile.html')}" aria-label="Tài khoản của tôi">${identity}</a>`:identity}<button class="btn ghost" data-logout title="Đăng xuất" aria-label="Đăng xuất">${icon('logout')}</button></div>` : `<div class="account-actions"><a class="btn secondary" href="login.html">Đăng nhập ${icon('arrow')}</a></div>`;
  }

  const footer = () => `<footer class="footer"><div class="footer-inner"><span>© ${new Date().getFullYear()} TrashSmart · Mỗi hành động nhỏ, một thay đổi xanh.</span><span>HAUI · Phân loại rác cùng AI <a href="../Admin/login.html">&nbsp;↗ Quản trị</a></span></div></footer>`;

  function shell(content) {
    context.runtime.root.innerHTML = context.runtime.admin ? `<div class="admin-shell"><aside class="sidebar">${brand()}<p class="sidebar-label">Quản lý hệ thống</p><nav class="nav" aria-label="Điều hướng quản trị">${adminNav()}</nav><div class="sidebar-bottom"><a href="../User/index.html">${icon('back')} Về trang người dùng</a><p style="margin-top:13px">TrashSmart / Admin workspace</p></div></aside><div class="admin-main"><header class="admin-topbar"><div class="workspace">${icon('shield')} Khu vực quản trị <span class="tag">ADMIN</span></div>${accountActions()}</header><main class="container" id="main">${content}</main>${footer()}</div></div>` : `<header class="topbar"><div class="topbar-inner">${brand()}<nav class="nav" aria-label="Điều hướng chính">${userNav()}</nav>${accountActions()}</div></header><main class="container" id="main">${content}</main>${footer()}`;
    context.window.document.querySelector('[data-logout]')?.addEventListener('click',context.runtime.logout);
    context.window.document.querySelector('.account-actions a[href="login.html"]')?.addEventListener('click', async event => { event.preventDefault(); await context.auth.requestSignIn(); });
    context.runtime.root.querySelectorAll('a[href]').forEach(link => {
      const target = new context.window.URL(link.getAttribute('href'), context.window.location.href);
      if(target.origin === context.window.location.origin && target.pathname.endsWith('.html')) link.href=context.runtime.pageUrl(target.href);
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
    button?.addEventListener('click', async () => { if(!error.authRequired || await context.auth.requestSignIn(error.message)) await retry(); });
  }

  const statuses = {DONE:['Hoàn tất',''],ERROR:['Xử lý lỗi','error'],PROCESSING:['Đang phân tích','pending'],UPLOADED:['Chờ phân tích','pending']};

  function statusBadge(status) { const [name,cl] = statuses[status] || ['Chờ phân tích','pending']; return `<span class="status ${cl}">${status==='DONE' ? icon('check'):''}${name}</span>`; }

  function materialIcon(code) { const m=materials[code]; return `<span class="material-icon" style="--material:${m?.color || '#718096'}">${icon(m?.icon || 'scan')}</span>`; }

  return {icon, escape, accountActions, shell, materials, materialIcon, materialName, toast, heading, loading, number, imageUrl, percent, empty, showError, statusBadge, date, brand};
}
