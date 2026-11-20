// history: page-scoped state and behavior. No browser work runs at import time.
export function createHistory(context) {
  function filtersMarkup(withSearch=true, dates=true, material=true) {
    return `<form class="filters" id="filters">${withSearch?'<div class="field search-field"><label for="search">Tìm kiếm</label><input id="search" name="q" placeholder="'+(context.runtime.page==='users'?'Tên, điện thoại hoặc email':'Mã lượt quét'+(context.runtime.admin?', tên hoặc điện thoại':''))+'" maxlength="120"/></div>':''}${material?`<div class="field"><label for="material">Vật liệu</label><select id="material" name="material"><option value="">Tất cả vật liệu</option>${Object.entries(context.ui.materials).map(([code,m])=>`<option value="${code}">${m.name}</option>`).join('')}</select></div>`:''}${dates?'<div class="field"><label for="from">Từ ngày</label><input type="date" id="from" name="from"/></div><div class="field"><label for="to">Đến ngày</label><input type="date" id="to" name="to"/></div>':''}<button class="btn primary" type="submit">Áp dụng ${context.ui.icon('arrow')}</button><button class="btn secondary" type="reset" aria-label="Xóa bộ lọc" title="Xóa bộ lọc">${context.ui.icon('refresh')}</button></form><div class="error-text" id="filter-error" role="alert"></div>`;
  }

  function filterValues(form) {
    const data=new context.window.FormData(form); const params=new context.window.URLSearchParams();
    for(const [key,value] of data) if(value.trim()) params.set(key,value.trim());
    if(params.get('from') && params.get('to') && params.get('from')>params.get('to')) throw new Error('Ngày bắt đầu cần trước hoặc trùng ngày kết thúc.');
    return params;
  }

  function pagination(data) {
    return `<div class="pagination"><span>${context.ui.number(data.total)} ${context.runtime.page==='users'?'người dùng':'lượt quét'}${data.total?` · Hiển thị ${context.ui.number(data.page*data.size+1)}–${context.ui.number(Math.min((data.page+1)*data.size,data.total))}`:''}</span><div class="pagination-controls"><button class="btn secondary small" data-page="${data.page-1}" ${data.page===0?'disabled':''}>${context.ui.icon('back')} Trước</button><span>Trang ${data.totalPages?data.page+1:0} / ${data.totalPages}</span><button class="btn secondary small" data-page="${data.page+1}" ${data.page+1>=data.totalPages?'disabled':''}>Sau ${context.ui.icon('arrow')}</button></div></div>`;
  }

  function componentHistory(r){return r.componentCount?'<small class="muted">Bộ phận: '+context.ui.escape((r.componentMaterials || []).map(context.ui.materialName).join(', ') || 'Chưa xác định')+'</small>':'';}

  function scanTable(items, recent=false) {
    return `<div class="table-wrap"><table class="table"><thead><tr><th>Lượt quét</th><th>Người dùng</th><th>Vật liệu</th><th>Trạng thái</th><th>Thời gian</th><th><span class="sr-only">Thao tác</span></th></tr></thead><tbody>${items.map(r=>`<tr><td><div class="table-person"><img class="thumb" src="${context.ui.imageUrl(r.imageUrl)}" alt="" loading="lazy"/><div><strong>#${r.id}</strong><small>${context.ui.number(r.count)} chai${r.componentCount?` · ${context.ui.number(r.componentCount)} bộ phận`:""}</small></div></div></td><td><strong>${context.ui.escape(r.fullName || 'Người dùng')}</strong><br><small class="muted">${context.ui.escape(r.phone || '—')}</small></td><td>${context.ui.escape(r.materials.map(context.ui.materialName).join(', ') || 'Chưa xác định')}<br/>${componentHistory(r)}</td><td>${context.ui.statusBadge(r.status)}</td><td>${context.ui.date(r.createdAt,true)}</td><td><button class="btn ghost small" data-detail="${r.id}" aria-label="Xem chi tiết lượt quét ${r.id}">${context.ui.icon('eye')}</button></td></tr>`).join('')}</tbody></table></div>`;
  }

  function scanCards(items) {
    return `<div class="history-grid">${items.map(r=>`<a class="scan-card" href="result_analys.html?id=${r.id}" aria-label="Xem lượt quét ${r.id}"><div class="scan-image"><img src="${context.ui.imageUrl(r.imageUrl)}" alt="Ảnh lượt quét ${r.id}" loading="lazy"/>${context.ui.statusBadge(r.status)}</div><div class="scan-body"><span class="small muted">${context.ui.date(r.createdAt,true)} · #${r.id}</span><h3>${context.ui.escape(r.materials.map(context.ui.materialName).join(' · ') || (r.status==='ERROR'?'Chưa có kết quả':'Chờ nhận diện'))}</h3><div class="small muted">${context.ui.number(r.count)} chai${r.componentCount?` · ${context.ui.number(r.componentCount)} bộ phận`:""}${r.requiresConfirmation?' · Cần kiểm tra thêm':''}</div>${componentHistory(r)}<div class="scan-foot"><span>${r.status==='DONE'?context.ui.percent(r.confidenceAvg)+' độ tin cậy':'Xem trạng thái xử lý'}</span><span style="color:var(--green)">Xem kết quả ${context.ui.icon('arrow')}</span></div></div></a>`).join('')}</div>`;
  }

  async function historyPage() {
    context.ui.shell(`${context.ui.heading(context.runtime.admin?'JOURNAL / LỊCH SỬ QUÉT':'NHẬT KÝ XANH',context.runtime.admin?'Mọi lượt quét, một nơi quản lý.':'Nhìn lại những hành động xanh.',context.runtime.admin?'Theo dõi ảnh, kết quả và trạng thái xử lý của toàn bộ hệ thống.':'Ảnh và kết quả phân loại của bạn được lưu tại đây để dễ dàng xem lại.',context.runtime.admin?'':`<a class="btn primary" href="index.html">${context.ui.icon('scan')} Quét ảnh mới</a>`)}${filtersMarkup()}<section id="history">${context.ui.loading()}</section>`);
    const target=context.window.document.querySelector('#history'), form=context.window.document.querySelector('#filters');
    let params=new context.window.URLSearchParams(); let request=0;
    const load=async(p=0)=>{
      const order=++request;target.innerHTML=context.ui.loading();params.set('page',p);params.set('size',context.runtime.admin?'12':'9');
      try { const data=await context.runtime.api(`${context.runtime.admin?'/admin':''}/scans?${params}`); if(order!==request)return;
        target.innerHTML=data.items.length ? (context.runtime.admin?`<div class="panel table-panel">${scanTable(data.items)}</div>`:scanCards(data.items))+pagination(data) : context.ui.empty('Chưa có lượt quét nào','Lịch sử sẽ hiển thị tại đây. Nếu đang dùng bộ lọc, hãy thử mở rộng khoảng tìm kiếm.',context.runtime.admin?'':`<a class="btn primary" href="index.html">${context.ui.icon('scan')} Phân loại ảnh đầu tiên</a>`);
        target.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>load(Number(b.dataset.page))));context.results.bindDetails(target);
      } catch(e){if(order===request)context.ui.showError(target,e,()=>load(p));}
    };
    form.onsubmit=e=>{e.preventDefault();try{params=filterValues(form);context.window.document.querySelector('#filter-error').textContent='';load();}catch(error){context.window.document.querySelector('#filter-error').textContent=error.message;}};
    form.onreset=()=>{params=new context.window.URLSearchParams();context.window.document.querySelector('#filter-error').textContent='';load();};
    await load();
  }

  return {filtersMarkup, scanTable, filterValues, pagination, historyPage};
}
