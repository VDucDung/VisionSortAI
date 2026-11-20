// users: page-scoped state and behavior. No browser work runs at import time.
export function createUsers(context) {
  async function editUser(user,reload) {
    context.window.document.querySelector('#user-dialog')?.remove();const dialog=context.window.document.createElement('dialog');dialog.id='user-dialog';dialog.className='edit-dialog';dialog.setAttribute('aria-labelledby','edit-title');
    dialog.innerHTML=`<div class="dialog-head"><div><span class="eyebrow">TÀI KHOẢN #${user.id}</span><h2 id="edit-title">Chỉnh sửa người dùng</h2></div><button class="btn ghost" data-close aria-label="Đóng">${context.ui.icon('close')}</button></div><form id="edit-form"><div class="field"><label for="edit-name">Họ và tên</label><input id="edit-name" name="fullName" value="${context.ui.escape(user.fullName)}" required maxlength="120"/></div><div class="field"><label for="edit-phone">Số điện thoại</label><input id="edit-phone" name="phone" type="tel" value="${context.ui.escape(user.phone)}" required pattern="0[0-9]{9,10}" maxlength="11"/></div><div class="field"><label for="edit-email">Email (không bắt buộc)</label><input id="edit-email" name="email" type="email" value="${context.ui.escape(user.email)}" maxlength="120"/></div><label class="check-label"><input type="checkbox" name="active" ${user.active?'checked':''}/> Cho phép tài khoản hoạt động</label><p class="small muted">Khi bị khóa, người dùng sẽ không thể tiếp tục truy cập API, kể cả với phiên đăng nhập hiện có.</p><p class="error-text" id="edit-error" role="alert"></p><div class="dialog-actions"><button type="button" class="btn secondary" data-cancel>Hủy</button><button class="btn primary" type="submit">Lưu thay đổi ${context.ui.icon('check')}</button></div></form>`;
    context.window.document.body.append(dialog);dialog.querySelector('[data-close]').onclick=()=>dialog.close();dialog.querySelector('[data-cancel]').onclick=()=>dialog.close();dialog.showModal();
    dialog.querySelector('form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget;const values=new context.window.FormData(form);const button=form.querySelector('[type=submit]');button.disabled=true;dialog.querySelector('#edit-error').textContent='';
      try{await context.runtime.api(`/admin/users/${user.id}`,{method:'PATCH',body:JSON.stringify({fullName:values.get('fullName').trim(),phone:values.get('phone').trim(),email:values.get('email').trim(),active:values.has('active')})});dialog.close();context.ui.toast('Đã cập nhật người dùng.');await reload();}
      catch(error){dialog.querySelector('#edit-error').textContent=error.message;button.disabled=false;}
    };
  }

  async function usersPage() {
    context.ui.shell(`${context.ui.heading('PEOPLE / NGƯỜI DÙNG','Những người cùng tạo thay đổi.','Tìm kiếm, cập nhật thông tin và quản lý quyền truy cập của tài khoản người dùng.')} ${context.history.filtersMarkup(true,false,false)}<section id="users">${context.ui.loading()}</section>`);
    const target=context.window.document.querySelector('#users'), form=context.window.document.querySelector('#filters');let params=new context.window.URLSearchParams();let request=0;
    const load=async(p=0)=>{const order=++request;target.innerHTML=context.ui.loading();params.set('page',p);params.set('size','12');try{const data=await context.runtime.api(`/admin/users?${params}`);if(order!==request)return;
      target.innerHTML=data.items.length?`<div class="panel table-panel"><div class="table-wrap"><table class="table"><thead><tr><th>Người dùng</th><th>Số điện thoại</th><th>Email</th><th>Trạng thái</th><th>Ngày tham gia</th><th>Thao tác</th></tr></thead><tbody>${data.items.map(u=>`<tr><td><div class="table-person"><span class="avatar">${context.ui.escape((u.fullName || 'U').slice(0,1).toUpperCase())}</span><div><strong>${context.ui.escape(u.fullName || 'Người dùng')}</strong><small>#${u.id} · USER</small></div></div></td><td>${context.ui.escape(u.phone)}</td><td>${context.ui.escape(u.email || '—')}</td><td><span class="status ${u.active?'':'error'}">${u.active?'Đang hoạt động':'Đã khóa'}</span></td><td>${context.ui.date(u.createdAt)}</td><td><button class="btn secondary small" data-edit="${u.id}">${context.ui.icon('edit')} Chỉnh sửa</button></td></tr>`).join('')}</tbody></table></div></div>${context.history.pagination(data)}`:context.ui.empty('Chưa tìm thấy người dùng','Thử tìm theo tên, số điện thoại hoặc email khác.');
      target.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>editUser(data.items.find(u=>u.id===Number(b.dataset.edit)),()=>load(p)));
      target.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>load(Number(b.dataset.page)));
    }catch(e){if(order===request)context.ui.showError(target,e,()=>load(p));}};
    form.onsubmit=e=>{e.preventDefault();params=context.history.filterValues(form);load();};form.onreset=()=>{params=new context.window.URLSearchParams();load();};await load();
  }

  return {usersPage};
}
