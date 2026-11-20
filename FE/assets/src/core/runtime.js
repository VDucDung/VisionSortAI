// runtime: page-scoped state and behavior. No browser work runs at import time.
export function createRuntime(context) {
  const area = context.window.document.body.dataset.area || 'user';

  const page = context.window.document.body.dataset.page || 'home';

  const admin = area === 'admin';

  const root = context.window.document.querySelector('#app');

  const config = context.window.TRASHSMART_CONFIG || {};

  const API = (config.apiBase || 'http://localhost:8080').replace(/\/+$/, '') + '/api/v1';

  const sessionKey = `trashsmart.${area}.session`;

  const release = '20261107-hitl-adminverify';

  const pageUrl = value => {
    const url = new context.window.URL(value, context.window.location.href);
    url.searchParams.set('v', release);
    return url.pathname + url.search + url.hash;
  };

  function readSession() { try { return JSON.parse(context.window.sessionStorage.getItem(sessionKey) || 'null'); } catch { return null; } }

  context.runtime.session = readSession();

  context.runtime.account = null;

  const loginUrl = () => `login.html?next=${encodeURIComponent(context.window.location.pathname.split('/').pop() + context.window.location.search)}`;

  function logout() { context.window.sessionStorage.removeItem(sessionKey); context.window.location.href = pageUrl('login.html'); }

  function saveSession(result) {
    if (!result?.token || result.account?.role !== (admin ? 'ADMIN' : 'USER'))
      throw new Error('Tài khoản không có quyền truy cập khu vực này.');
    context.window.sessionStorage.setItem(sessionKey, JSON.stringify(result));
    context.runtime.session = result;
    context.runtime.account = result.account;
  }

  async function api(path, options = {}) {
    const {publicRequest = false, ...fetchOptions} = options;
    const headers = new context.window.Headers(fetchOptions.headers || {});
    if (!publicRequest && context.runtime.session?.token) headers.set('Authorization', `Bearer ${context.runtime.session.token}`);
    if (fetchOptions.body && !(fetchOptions.body instanceof context.window.FormData)) headers.set('Content-Type','application/json');
    let response;
    try {
      response = await context.window.fetch(API + path, {...fetchOptions, headers, signal:fetchOptions.signal || context.window.AbortSignal.timeout(path === '/scans' && fetchOptions.method === 'POST' || path.endsWith('/retry') ? 240000 : 20000)});
    } catch (error) {
      throw new Error(error.name === 'TimeoutError' ? 'Yêu cầu mất quá nhiều thời gian. Kiểm tra lịch sử trước khi thử lại.' : 'Không thể kết nối máy chủ. Hãy kiểm tra backend và kết nối mạng.');
    }
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401 && !publicRequest) {
      // Older servers can turn an internal /error dispatch into 401. Check the
      // session separately before discarding a valid token or asking for login.
      if (path !== '/auth/me' && context.runtime.session?.token) {
        let check;
        try { check = await context.window.fetch(API + '/auth/me', {headers: {Authorization: `Bearer ${context.runtime.session.token}`}, signal: context.window.AbortSignal.timeout(15000)}); }
        catch { throw new Error('Chưa thể kiểm tra phiên đăng nhập do lỗi kết nối. Ảnh đã chọn vẫn được giữ; hãy thử lại.'); }
        if (check.ok) throw new Error('Máy chủ không xử lý được yêu cầu dù phiên đăng nhập vẫn hợp lệ. Hãy khởi động lại BE sau khi cập nhật và thử lại.');
        if (check.status !== 401) throw new Error('Máy chủ đang gặp lỗi khi kiểm tra phiên đăng nhập. Ảnh đã chọn vẫn được giữ; hãy thử lại.');
      }
      context.window.sessionStorage.removeItem(sessionKey);
      context.runtime.session = null; context.runtime.account = null;
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

  return {admin, saveSession, api, area, logout, page, pageUrl, root, API, sessionKey};
}
