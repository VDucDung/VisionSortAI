// auth: page-scoped state and behavior. No browser work runs at import time.
export function createAuth(context) {
  let signInPending;

  function requestSignIn(reason = 'Đăng nhập để tiếp tục. Ảnh đã chọn vẫn được giữ trên trang.') {
    if (signInPending) return signInPending;
    signInPending = new Promise(resolve => {
      const dialog = context.window.document.createElement('dialog');
      dialog.className = 'edit-dialog signin-dialog';
      dialog.setAttribute('aria-labelledby', 'signin-title');
      let accepted = false, registering = false;
      dialog.addEventListener('close', () => { dialog.remove(); resolve(accepted); }, {once:true});
      function render() {
        dialog.innerHTML = `<div class="dialog-head"><h2 id="signin-title">${registering?'Tạo tài khoản':'Đăng nhập để tiếp tục'}</h2><button class="btn ghost" data-close aria-label="Đóng">${context.ui.icon('close')}</button></div><p class="signin-reason">${context.ui.escape(reason)}</p><form id="signin-form">${registering?'<div class="field"><label for="signin-name">Họ và tên</label><input id="signin-name" name="fullName" required maxlength="120" autocomplete="name"/></div>':''}<div class="field"><label for="signin-id">${context.runtime.admin?'Email quản trị':'Số điện thoại'}</label><input id="signin-id" name="identifier" type="${context.runtime.admin?'email':'tel'}" ${context.runtime.admin?'':'pattern="0[0-9]{9,10}" maxlength="11"'} required autocomplete="username"/></div><div class="field"><label for="signin-password">Mật khẩu</label><input id="signin-password" name="password" type="password" ${registering?'minlength="8" maxlength="72"':''} required autocomplete="${registering?'new-password':'current-password'}"/></div><p id="signin-error" class="error-text" role="alert"></p><button class="btn primary" type="submit">${registering?'Tạo tài khoản':'Đăng nhập'} ${context.ui.icon('arrow')}</button></form>${context.runtime.admin?'':`<button class="btn ghost signin-switch" data-switch>${registering?'Đã có tài khoản? Đăng nhập':'Chưa có tài khoản? Đăng ký'}</button>`}`;
        dialog.querySelector('[data-close]').onclick = () => dialog.close();
        dialog.querySelector('[data-switch]')?.addEventListener('click', () => { registering = !registering; render(); });
        dialog.querySelector('form').onsubmit = async event => {
          event.preventDefault();
          const form = event.currentTarget, fields = new context.window.FormData(form), button = form.querySelector('[type=submit]');
          button.disabled = true; dialog.querySelector('#signin-error').textContent = '';
          const body = registering ? {phone:fields.get('identifier').trim(), password:fields.get('password'), fullName:fields.get('fullName').trim()}
            : {identifier:fields.get('identifier').trim(), password:fields.get('password')};
          try {
            context.runtime.saveSession(await context.runtime.api(registering?'/auth/register':`/auth/login/${context.runtime.area}`, {method:'POST',body:JSON.stringify(body),publicRequest:true}));
            const actions = context.window.document.querySelector('.topbar-inner > .account-actions, .admin-topbar > .account-actions');
            if (actions) { actions.outerHTML = context.ui.accountActions(); context.window.document.querySelector('[data-logout]')?.addEventListener('click',context.runtime.logout); }
            accepted = true; dialog.close();
          } catch(error) { dialog.querySelector('#signin-error').textContent = error.message; button.disabled = false; }
        };
      }
      context.window.document.body.append(dialog); render(); dialog.showModal();
    }).finally(() => { signInPending = null; });
    return signInPending;
  }

  function authPage(register=false) {
    const title=register?'Bắt đầu hành trình xanh.':context.runtime.admin?'Chào mừng trở lại.':'Rất vui được gặp lại bạn.';
    context.runtime.root.innerHTML=`<div class="auth-layout"><aside class="auth-story">${context.ui.brand()}<div><span class="eyebrow">MỖI NGÀY MỘT CHÚT XANH HƠN</span><h1 style="margin-top:16px">Một bức ảnh.<br>Một lựa chọn đúng.<br>Một tương lai xanh.</h1><p>Nhận diện vật liệu, phân loại có trách nhiệm và theo dõi hành trình thay đổi của bạn.</p><img class="illustration" src="../assets/scan-illustration.svg" alt="Chai nhựa và lon được nhận diện để tái chế"/></div><small>TRASHSMART · HAUI · PHÂN LOẠI CÙNG AI</small></aside><main class="auth-main" id="main"><div class="auth-form"><div class="mobile-brand">${context.ui.brand()}</div><a class="back" href="../User/index.html">${context.ui.icon('back')} Về trang chủ</a><div class="eyebrow">${context.runtime.admin?'ADMIN WORKSPACE':register?'THAM GIA TRASHSMART':'CHÀO BẠN ĐẾN TRASHSMART'}</div><h1>${title}</h1><p>${context.runtime.admin?'Đăng nhập bằng tài khoản quản trị đã được cấp.':register?'Tạo tài khoản để lưu kết quả và lịch sử phân loại.':'Đăng nhập để tiếp tục phân loại và xem lại lịch sử của bạn.'}</p><form id="auth-form">${register?'<div class="field"><label for="fullName">Họ và tên</label><input id="fullName" name="fullName" required maxlength="120" autocomplete="name" placeholder="Nguyễn Văn An"/></div>':''}<div class="field"><label for="identifier">${context.runtime.admin?'Email quản trị':'Số điện thoại'}</label><input id="identifier" name="identifier" type="${context.runtime.admin?'email':'tel'}" ${context.runtime.admin?'':'pattern="0[0-9]{9,10}" maxlength="11"'} required autocomplete="username" placeholder="${context.runtime.admin?'admin@example.com':'Nhập số điện thoại'}"/></div><div class="field"><label for="password">Mật khẩu</label><div class="password-wrap"><input id="password" name="password" type="password" required ${register?'minlength="8" maxlength="72"':''} autocomplete="${register?'new-password':'current-password'}" placeholder="${register?'Ít nhất 8 ký tự':'Nhập mật khẩu'}"/><button type="button" id="toggle-password" aria-label="Hiện mật khẩu" aria-pressed="false">${context.ui.icon('eye')}</button></div></div><div id="auth-error" class="error-text" role="alert"></div><button type="submit" class="btn primary">${register?'Tạo tài khoản':'Đăng nhập'} ${context.ui.icon('arrow')}</button></form>${context.runtime.admin?'<p class="switch">Tài khoản được cấp bởi người vận hành hệ thống.</p>':`<p class="switch">${register?'Đã có tài khoản?':'Chưa có tài khoản?'} <a href="${register?'login':'register'}.html${context.window.location.search}">${register?'Đăng nhập':'Đăng ký ngay'}</a></p>`}<p class="fineprint" style="margin-top:30px">${context.ui.icon('shield')} Thông tin đăng nhập được bảo vệ bằng mã hóa mật khẩu.</p></div></main></div>`;
    context.window.document.querySelector('#toggle-password').onclick=e=>{const input=context.window.document.querySelector('#password');const show=input.type==='password';input.type=show?'text':'password';e.currentTarget.setAttribute('aria-pressed',String(show));e.currentTarget.setAttribute('aria-label',show?'Ẩn mật khẩu':'Hiện mật khẩu');};
    context.window.document.querySelector('#auth-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget;const data=new context.window.FormData(form);const button=form.querySelector('[type=submit]');const error=context.window.document.querySelector('#auth-error');error.textContent='';button.disabled=true;
      try { const body=register?{phone:data.get('identifier').trim(),password:data.get('password'),fullName:data.get('fullName').trim()}:{identifier:data.get('identifier').trim(),password:data.get('password')};
        const result=await context.runtime.api(register?'/auth/register':`/auth/login/${context.runtime.area}`,{method:'POST',body:JSON.stringify(body),publicRequest:true});
        context.runtime.saveSession(result);
        const next=new context.window.URLSearchParams(context.window.location.search).get('next');const allowed=context.runtime.admin?['home.html','history.html','report.html','user_managerment.html','profile.html']:['index.html','history.html','result_analys.html'];
        context.window.location.href=context.runtime.pageUrl(next && allowed.includes(next.split('?')[0]) && !next.includes('#') ? next : context.runtime.admin?'home.html':'index.html');
      } catch(err){error.textContent=err.message;button.disabled=false;}
    };
  }

  return {requestSignIn, authPage};
}
