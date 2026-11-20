import {createRuntime} from './core/runtime.js';
import {createUi} from './ui/ui.js';
import {createAuth} from './features/auth.js';
import {createScan} from './features/scan.js';
import {createLearning} from './features/learning.js';
import {createResults} from './features/results.js';
import {createHistory} from './features/history.js';
import {createStatistics} from './features/statistics.js';
import {createUsers} from './features/users.js';
import {createProfile} from './features/profile.js';

// Each page owns its state; factories receive the same explicit application context.
export function mountApplication(window) {
  const context = {window, runtime: {}, ui: {}, auth: {}, scan: {}, learning: {}, results: {}, history: {}, statistics: {}, users: {}, profile: {}};
  Object.assign(context.runtime, createRuntime(context));
  Object.assign(context.ui, createUi(context));
  Object.assign(context.auth, createAuth(context));
  Object.assign(context.scan, createScan(context));
  Object.assign(context.learning, createLearning(context));
  Object.assign(context.results, createResults(context));
  Object.assign(context.history, createHistory(context));
  Object.assign(context.statistics, createStatistics(context));
  Object.assign(context.users, createUsers(context));
  Object.assign(context.profile, createProfile(context));

  async function boot() {
    if(['login','register'].includes(context.runtime.page)){context.auth.authPage(context.runtime.page==='register'&&!context.runtime.admin);return;}
    context.ui.shell(context.ui.loading());
    let authIssue;
    if(context.runtime.session?.token){
      try {
        context.runtime.account=await context.runtime.api('/auth/me');
        if(context.runtime.account.role!==(context.runtime.admin?'ADMIN':'USER')) {
          context.window.sessionStorage.removeItem(context.runtime.sessionKey);context.runtime.session=null;context.runtime.account=null;
          authIssue='Tài khoản không có quyền truy cập khu vực này. Vui lòng đăng nhập bằng tài khoản phù hợp.';
        }
      } catch(e) {
        if(e.authRequired)authIssue=e.message;
        else {context.ui.showError(context.window.document.querySelector('#main'),e,boot);return;}
      }
    }
    if((context.runtime.admin || context.runtime.page!=='home') && !context.runtime.session?.token) {
      context.ui.shell(context.ui.empty('Đăng nhập để tiếp tục',authIssue || 'Bạn cần đăng nhập để xem dữ liệu của mình.', '<button class="btn primary" data-signin>Đăng nhập</button>'));
      context.window.document.querySelector('[data-signin]').onclick=async()=>{if(await context.auth.requestSignIn(authIssue || 'Đăng nhập để tiếp tục xem trang này.'))await boot();};
      return;
    }
    if(authIssue)context.ui.toast(authIssue);
    if(context.runtime.page==='home')return context.runtime.admin?context.statistics.dashboard():context.scan.home();
    if(context.runtime.page==='history')return context.history.historyPage();
    if(context.runtime.page==='result')return context.results.resultPage();
    if(context.runtime.page==='statistics')return context.statistics.dashboard(true);
    if(context.runtime.page==='users')return context.users.usersPage();
    if(context.runtime.page==='profile' && context.runtime.admin)return context.profile.profilePage();
    if(context.runtime.page==='learning' && context.runtime.admin)return context.learning.learningPage();
  }

  boot().catch(error=>{if(!context.window.document.querySelector('#main'))context.ui.shell('');context.ui.showError(context.window.document.querySelector('#main'),error,boot);});
  context.window.document.addEventListener('error',e=>{if(e.target instanceof context.window.HTMLImageElement && !e.target.src.endsWith('/assets/logo.svg')){e.target.src='../assets/logo.svg';e.target.style.objectFit='contain';}},true);
  context.window.document.addEventListener('click',event=>{
    const link=event.target.closest?.('a[href]');
    if(!link)return;
    const target=new context.window.URL(link.getAttribute('href'),context.window.location.href);
    if(target.origin===context.window.location.origin && target.pathname.endsWith('.html'))link.href=context.runtime.pageUrl(target.href);
  },true);
}
