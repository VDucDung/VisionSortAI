// profile: page-scoped state and behavior. No browser work runs at import time.
export function createProfile(context) {
  async function profilePage() {
    context.ui.shell(`${context.ui.heading('MY ACCOUNT / TÀI KHOẢN CỦA TÔI','Thông tin của bạn.','Cập nhật hồ sơ và bảo mật tài khoản quản trị đang đăng nhập.')}<section id="profile-content">${context.ui.loading()}</section>`);
    const target=context.window.document.querySelector('#profile-content');
    const load=async()=>{
      target.innerHTML=context.ui.loading();
      try {
        const capability=await context.runtime.api('/system/info',{publicRequest:true});
        if(capability.adminProfileApiVersion!==1)throw new Error('BE đang chạy bản chưa có chức năng hồ sơ admin. Hãy khởi động lại BE sau khi cập nhật.');
        let profile=await context.runtime.api('/admin/profile');
        target.innerHTML=`<div class="profile-layout"><aside class="panel profile-summary"><span class="avatar profile-avatar" data-profile-avatar>${context.ui.escape((profile.fullName || 'A').slice(0,1).toUpperCase())}</span><h2 data-profile-name>${context.ui.escape(profile.fullName || 'Quản trị viên')}</h2><p class="muted small" data-profile-email>${context.ui.escape(profile.email)}</p><span class="tag">${context.ui.icon('shield')} QUẢN TRỊ VIÊN</span><div class="profile-id"><span>Mã tài khoản</span><strong>#${profile.id}</strong></div><p class="small muted">Thông tin và lịch sử hoạt động được gắn với tài khoản này.</p></aside><div class="profile-forms"><section class="panel"><div class="panel-head"><div><h2>Thông tin cá nhân</h2><p>Email được dùng để đăng nhập vào trang quản trị.</p></div>${context.ui.icon('edit')}</div><form id="profile-form"><div class="field"><label for="profile-name">Họ và tên</label><input id="profile-name" name="fullName" required maxlength="120" autocomplete="name" value="${context.ui.escape(profile.fullName)}"/></div><div class="profile-fields"><div class="field"><label for="profile-phone">Số điện thoại</label><input id="profile-phone" name="phone" type="tel" required pattern="0[0-9]{9,10}" maxlength="11" autocomplete="tel" value="${context.ui.escape(profile.phone)}"/></div><div class="field"><label for="profile-email">Email đăng nhập</label><input id="profile-email" name="email" type="email" required maxlength="120" autocomplete="email" value="${context.ui.escape(profile.email)}"/></div></div><div class="field"><label for="profile-confirm-password">Mật khẩu hiện tại khi đổi email</label><input id="profile-confirm-password" name="currentPassword" type="password" maxlength="72" autocomplete="current-password" placeholder="Chỉ cần nhập khi đổi email"/><span class="small muted">Đổi email cần xác nhận mật khẩu; các phiên cũ sẽ hết hiệu lực sau khi lưu.</span></div><p class="error-text" id="profile-error" role="alert"></p><p class="profile-success" id="profile-success" role="status"></p><div class="profile-actions"><button class="btn secondary" type="reset">Hoàn tác</button><button class="btn primary" type="submit">${context.ui.icon('check')} Lưu thông tin</button></div></form></section><section class="panel"><div class="panel-head"><div><h2>Đổi mật khẩu</h2><p>Xác nhận bằng mật khẩu hiện tại để bảo vệ tài khoản của bạn.</p></div>${context.ui.icon('shield')}</div><form id="password-form"><div class="field"><label for="password-current">Mật khẩu hiện tại</label><input id="password-current" name="currentPassword" type="password" required maxlength="72" autocomplete="current-password"/></div><div class="profile-fields"><div class="field"><label for="password-new">Mật khẩu mới</label><input id="password-new" name="newPassword" type="password" required minlength="8" maxlength="72" autocomplete="new-password"/></div><div class="field"><label for="password-confirm">Nhập lại mật khẩu mới</label><input id="password-confirm" name="confirmation" type="password" required minlength="8" maxlength="72" autocomplete="new-password"/></div></div><p class="small muted">Ít nhất 8 ký tự, tối đa 72 byte UTF-8. Các phiên đăng nhập trước sẽ hết hiệu lực; trang này tiếp tục bằng phiên mới.</p><p class="error-text" id="password-error" role="alert"></p><p class="profile-success" id="password-success" role="status"></p><div class="profile-actions"><button class="btn primary" type="submit">${context.ui.icon('shield')} Cập nhật mật khẩu</button></div></form></section></div></div>`;
        function refreshIdentity(result) {
          context.runtime.saveSession(result);profile=result.account;
          const actions=context.window.document.querySelector('.admin-topbar > .account-actions');
          actions.outerHTML=context.ui.accountActions();context.window.document.querySelector('[data-logout]').addEventListener('click',context.runtime.logout);
          target.querySelector('[data-profile-name]').textContent=profile.fullName || 'Quản trị viên';
          target.querySelector('[data-profile-email]').textContent=profile.email;
          target.querySelector('[data-profile-avatar]').textContent=(profile.fullName || 'A').slice(0,1).toUpperCase();
        }
        const form=target.querySelector('#profile-form'), email=target.querySelector('#profile-email'), confirm=target.querySelector('#profile-confirm-password');
        email.addEventListener('input',()=>{confirm.required=email.value.trim().toLowerCase()!==(profile.email || '').toLowerCase();});
        form.addEventListener('reset',()=>{
          context.window.setTimeout(()=>{
            form.elements.fullName.value=profile.fullName || '';form.elements.phone.value=profile.phone || '';form.elements.email.value=profile.email || '';
            confirm.value='';confirm.required=false;target.querySelector('#profile-error').textContent='';target.querySelector('#profile-success').textContent='';
          },0);
        });
        form.onsubmit=async event=>{
          event.preventDefault();const fields=new context.window.FormData(form), button=form.querySelector('[type=submit]');
          target.querySelector('#profile-error').textContent='';target.querySelector('#profile-success').textContent='';button.disabled=true;
          try {
            refreshIdentity(await context.runtime.api('/admin/profile',{method:'PATCH',body:JSON.stringify({fullName:fields.get('fullName').trim(),phone:fields.get('phone').trim(),email:fields.get('email').trim(),currentPassword:fields.get('currentPassword')})}));
            confirm.value='';confirm.required=false;
            form.elements.fullName.value=profile.fullName;form.elements.phone.value=profile.phone;email.value=profile.email;
            target.querySelector('#profile-success').textContent='Đã cập nhật thông tin tài khoản.';
          }catch(error){target.querySelector('#profile-error').textContent=error.message;}
          finally{button.disabled=false;}
        };
        const passwordForm=target.querySelector('#password-form');
        passwordForm.onsubmit=async event=>{
          event.preventDefault();const fields=new context.window.FormData(passwordForm), button=passwordForm.querySelector('[type=submit]');
          target.querySelector('#password-error').textContent='';target.querySelector('#password-success').textContent='';
          if(fields.get('newPassword')!==fields.get('confirmation')){target.querySelector('#password-error').textContent='Mật khẩu nhập lại chưa khớp.';return;}
          button.disabled=true;
          try {
            refreshIdentity(await context.runtime.api('/admin/profile/password',{method:'POST',body:JSON.stringify({currentPassword:fields.get('currentPassword'),newPassword:fields.get('newPassword')})}));
            passwordForm.reset();confirm.value='';
            target.querySelector('#password-success').textContent='Đã đổi mật khẩu. Các phiên đăng nhập cũ đã hết hiệu lực.';
          }catch(error){target.querySelector('#password-error').textContent=error.message;}
          finally{button.disabled=false;}
        };
      }catch(error){context.ui.showError(target,error,load);}
    };
    await load();
  }

  return {profilePage};
}
