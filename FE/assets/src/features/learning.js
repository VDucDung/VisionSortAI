// learning: page-scoped state and behavior. No browser work runs at import time.
export function createLearning(context) {
  const partNames={cap:'Nắp chai',body:'Thân/vỏ chai',label:'Nhãn dán'};

  const feedbackStates={OPEN:'Chưa xác nhận',PENDING:'Chờ admin duyệt',APPROVED:'Đã duyệt để học',REJECTED:'Không đưa vào dữ liệu học'};

  function hitlMarkup(c) {
    if(!c.learningCaseId)return '';
    if(context.runtime.admin)return `<p class="small muted">${context.ui.escape(feedbackStates[c.feedbackState] || 'Chưa xác nhận')} · <a href="${context.runtime.pageUrl('learning.html')}">Mở hàng đợi duyệt nhãn</a></p>`;
    if(c.feedbackState&&c.feedbackState!=='OPEN')return `<div class="hitl-feedback"><strong>${context.ui.escape(feedbackStates[c.feedbackState] || 'Đã gửi xác nhận')}</strong><p class="small">Bạn xác nhận: ${context.ui.escape(context.ui.materialName(c.humanMaterial))}. Dự đoán AI ở trên được giữ nguyên.</p></div>`;
    return `<details class="hitl-feedback" ${c.queryRecommended?'open':''}><summary>${c.queryRecommended?'AI chưa chắc chắn · Bạn giúp xác nhận nhé':'Bạn muốn xác nhận hoặc sửa vật liệu?'}</summary><form data-hitl-form data-case-id="${context.ui.escape(c.learningCaseId)}" data-revision="${context.ui.escape(c.feedbackRevision ?? 0)}"><fieldset><legend>Vật liệu thực tế của ${context.ui.escape((partNames[c.partType] || 'bộ phận').toLowerCase())} là gì?</legend>${[...Object.entries(context.ui.materials).map(([code,m])=>[code,m.name]),['unknown','Không chắc chắn']].map(([code,name])=>`<label class="hitl-option"><input type="radio" name="material" value="${code}" required/> ${context.ui.escape(name)}</label>`).join('')}</fieldset><div class="field"><label>Cách bạn kiểm chứng<select name="verificationBasis" required><option value="">Chọn cách kiểm chứng</option><option value="PHYSICAL_CHECK">Đã kiểm tra trực tiếp vật liệu</option><option value="PACKAGING_MARK">Đã đọc ký hiệu vật liệu trên bao bì</option><option value="VISUAL_ONLY">Chỉ xem hình ảnh</option><option value="UNSURE">Chưa kiểm chứng / không chắc</option></select></label></div><label class="hitl-option"><input type="checkbox" name="regionCorrect"/> Khung ảnh đánh dấu đúng bộ phận này</label><label class="hitl-option"><input type="checkbox" name="trainingConsent"/> Tôi đồng ý dùng ảnh và xác nhận này để cải thiện model</label><div class="field"><label>Ghi chú (không bắt buộc)<textarea name="note" maxlength="1000" rows="2" placeholder="Ví dụ: tháo nhãn và kiểm tra mặt sau"></textarea></label></div><p class="small muted">Xác nhận được admin kiểm tra trước khi dùng trong đợt huấn luyện mới.</p><p class="error-text" data-hitl-error role="alert"></p><button type="submit" class="btn secondary small">${context.ui.icon('check')} Gửi xác nhận</button></form></details>`;
  }

  function bindHitl(target,scanId,getCache) {
    target.addEventListener('submit',async event=>{
      const form=event.target.closest('[data-hitl-form]');if(!form||!target.contains(form))return;
      event.preventDefault();const button=form.querySelector('[type=submit]');if(button.disabled)return;
      const fields=new context.window.FormData(form),error=form.querySelector('[data-hitl-error]');error.textContent='';
      if(!fields.get('material')||!fields.get('verificationBasis')){error.textContent='Chọn vật liệu và cách kiểm chứng trước khi gửi.';return;}
      button.disabled=true;
      try {
        const response=await context.runtime.api(`/scans/${scanId}/learning/${encodeURIComponent(form.dataset.caseId)}/feedback`,{method:'POST',body:JSON.stringify({
          material:fields.get('material'),verificationBasis:fields.get('verificationBasis'),regionCorrect:fields.has('regionCorrect'),
          trainingConsent:fields.has('trainingConsent'),note:fields.get('note').trim(),revision:Number(form.dataset.revision)
        })});
        const component=getCache()?.parents.flatMap(p=>p.components).find(c=>c.learningCaseId===form.dataset.caseId);
        const next={...(component || {}),learningCaseId:form.dataset.caseId,feedbackState:response.feedbackState,humanMaterial:response.humanMaterial,feedbackRevision:response.revision};
        if(component)Object.assign(component,next);
        form.closest('.hitl-feedback').outerHTML=hitlMarkup(next);
        context.ui.toast('Đã gửi xác nhận. Cảm ơn bạn đã giúp cải thiện dữ liệu!');
      }catch(problem){error.textContent=problem.message;button.disabled=false;}
    });
  }

  async function learningPage() {
    context.ui.shell(context.ui.heading('CON NGƯỜI & AI','Duyệt xác nhận vật liệu','Ưu tiên các dự đoán chưa chắc chắn. Chỉ nhãn đã kiểm chứng và được đồng ý mới dùng để học.',
      '<button class="btn secondary" data-hitl-export>Xuất nhãn đã duyệt</button>')+
      '<div class="notice small">Xác nhận và duyệt nhãn chưa thay đổi model đang chạy. Model mới được huấn luyện và đánh giá theo từng phiên bản.</div><div class="filters" style="margin-top:20px"><label>Trạng thái <select data-hitl-state><option value="PENDING">Chờ duyệt</option><option value="OPEN">Chưa có xác nhận</option><option value="APPROVED">Đã duyệt để học</option><option value="REJECTED">Không dùng để học</option></select></label></div><div id="learning-list"></div>');
    const target=context.window.document.querySelector('#learning-list'),state=context.window.document.querySelector('[data-hitl-state]');let currentPage=0;
    async function load(p=0){
      currentPage=p;target.innerHTML=context.ui.loading();
      try{
        const data=await context.runtime.api(`/admin/learning?state=${encodeURIComponent(state.value)}&page=${p}&size=12`);
        target.innerHTML=`<p class="small muted">${context.ui.number(data.pending)} chờ duyệt · ${context.ui.number(data.approved)} đã duyệt · ${context.ui.number(data.rejected)} không dùng để học</p><div class="hitl-queue">${data.items.map(c=>{
          const baseEligible=c.regionCorrect&&c.trainingConsent&&Object.hasOwn(context.ui.materials,c.humanMaterial);
          const userVerified=['PHYSICAL_CHECK','PACKAGING_MARK'].includes(c.verificationBasis),eligible=baseEligible&&userVerified;
          return `<article class="panel hitl-review" data-hitl-case="${context.ui.escape(c.id)}"><div class="hitl-review-photo"><img src="${context.ui.imageUrl(c.imageUrl)}" alt="Ảnh bộ phận cần duyệt"/><svg viewBox="0 0 ${Number(c.imageWidth)} ${Number(c.imageHeight)}" preserveAspectRatio="none" aria-hidden="true"><rect x="${Number(c.x1)}" y="${Number(c.y1)}" width="${Number(c.x2)-Number(c.x1)}" height="${Number(c.y2)-Number(c.y1)}"/></svg></div><div><div class="panel-head"><h2>${context.ui.escape(partNames[c.partType] || 'Bộ phận')} · Lượt #${Number(c.scanId)}</h2><span class="tag">${context.ui.escape(feedbackStates[c.feedbackState])}</span></div><p>AI: <strong>${context.ui.escape(context.ui.materialName(c.predictedMaterial))}</strong> · ${context.ui.percent(c.materialConfidence)}</p><p>Người dùng: <strong>${context.ui.escape(context.ui.materialName(c.humanMaterial))}</strong></p><p class="small muted">${context.ui.escape(({PHYSICAL_CHECK:'Đã kiểm tra trực tiếp',PACKAGING_MARK:'Đọc ký hiệu trên bao bì',VISUAL_ONLY:'Chỉ xem hình',UNSURE:'Chưa kiểm chứng'})[c.verificationBasis] || 'Chưa trả lời')} · ${c.regionCorrect?'Vùng đúng':'Chưa xác nhận vùng đúng'} · ${c.trainingConsent?'Đồng ý dùng để học':'Chưa đồng ý dùng để học'}</p><p class="small">${context.ui.escape(c.humanNote || '')}</p><p class="small muted">Model: ${context.ui.escape(c.modelVersion)}</p>${c.feedbackState==='PENDING'?`<form data-hitl-review data-id="${context.ui.escape(c.id)}" data-revision="${Number(c.revision)}" data-base-eligible="${Boolean(baseEligible)}" data-user-verified="${userVerified}"><div class="field"><label>Căn cứ xác nhận của admin<select name="adminBasis"><option value="">Dùng căn cứ của người dùng (nếu đủ)</option><option value="VISUAL_REVIEW">Đã đối chiếu hình ảnh và xác nhận</option><option value="PHYSICAL_CHECK">Đã kiểm tra trực tiếp vật liệu</option><option value="PACKAGING_MARK">Đã đọc ký hiệu vật liệu trên bao bì</option></select></label></div><label class="hitl-option"><input type="checkbox" name="confirmedCorrect"/> Tôi xác nhận vật liệu người dùng chọn là đúng</label><div class="field"><label>Ghi chú / lý do loại<textarea name="note" maxlength="1000" rows="2"></textarea></label></div><p class="error-text" role="alert" data-hitl-review-error></p>${!baseEligible?'<p class="small muted">Cần vật liệu xác định, vùng đúng và người dùng đồng ý dùng để học.</p>':!userVerified?'<p class="small muted">Chọn căn cứ, tích xác nhận đúng và ghi chú để admin duyệt bằng kiểm chứng riêng.</p>':''}<div class="hitl-review-actions"><button type="submit" class="btn primary small" name="decision" value="APPROVE" ${eligible?'':'disabled'}>Duyệt để học</button><button type="submit" class="btn secondary small" name="decision" value="REJECT">Không dùng để học</button></div></form>`:`<p class="small">${context.ui.escape(c.reviewNote || '')}</p><p class="small muted">${c.adminVerificationBasis?'Admin xác nhận: '+context.ui.escape(({VISUAL_REVIEW:'Đối chiếu hình ảnh',PHYSICAL_CHECK:'Kiểm tra trực tiếp',PACKAGING_MARK:'Ký hiệu bao bì'})[c.adminVerificationBasis] || c.adminVerificationBasis):''}</p>`}</div></article>`;
        }).join('') || context.ui.empty('Chưa có xác nhận','Các phản hồi phù hợp sẽ xuất hiện tại đây. Hãy chọn trạng thái khác để xem thêm.')}</div><div class="pagination"><span>${context.ui.number(data.total)} bộ phận</span><div class="pagination-controls"><button class="btn secondary small" data-hitl-page="${p-1}" ${p===0?'disabled':''}>Trước</button><span>Trang ${data.totalPages?p+1:0} / ${context.ui.number(data.totalPages)}</span><button class="btn secondary small" data-hitl-page="${p+1}" ${p+1>=data.totalPages?'disabled':''}>Sau</button></div></div>`;
        target.querySelectorAll('[data-hitl-page]').forEach(b=>b.onclick=()=>load(Number(b.dataset.hitlPage)));
      }catch(problem){context.ui.showError(target,problem,()=>load(p));}
    }
    function refreshApproval(form){
      const fields=new context.window.FormData(form),basis=fields.get('adminBasis'),independent=Boolean(basis)&&fields.has('confirmedCorrect')&&Boolean(fields.get('note').trim());
      form.querySelector('[value=APPROVE]').disabled=form.dataset.baseEligible!=='true'||!(form.dataset.userVerified==='true'||independent)||Boolean(basis)&&!independent;
    }
    for(const name of ['input','change'])target.addEventListener(name,event=>{const form=event.target.closest('[data-hitl-review]');if(form)refreshApproval(form);});
    state.onchange=()=>load(0);
    target.addEventListener('submit',async event=>{
      const form=event.target.closest('[data-hitl-review]');if(!form)return;event.preventDefault();
      const decision=event.submitter?.value;if(!['APPROVE','REJECT'].includes(decision))return;
      const error=form.querySelector('[data-hitl-review-error]');error.textContent='';const fields=new context.window.FormData(form),note=fields.get('note').trim();
      const verificationBasis=fields.get('adminBasis'),confirmedCorrect=fields.has('confirmedCorrect');
      if(decision==='APPROVE'&&verificationBasis&&(!confirmedCorrect||!note)){error.textContent='Tích xác nhận đúng và ghi căn cứ của admin.';return;}
      if(decision==='REJECT'&&!note){error.textContent='Ghi lý do không dùng xác nhận này để học.';return;}
      const buttons=[...form.querySelectorAll('button')],previous=buttons.map(b=>b.disabled);buttons.forEach(b=>b.disabled=true);
      try{await context.runtime.api(`/admin/learning/${encodeURIComponent(form.dataset.id)}/review`,{method:'POST',body:JSON.stringify({decision,note,revision:Number(form.dataset.revision),...(decision==='APPROVE'&&verificationBasis?{verificationBasis,confirmedCorrect}:{})})});await load(currentPage);}
      catch(problem){error.textContent=problem.message;buttons.forEach((b,i)=>b.disabled=previous[i]);}
    });
    context.window.document.querySelector('[data-hitl-export]').onclick=async event=>{
      const button=event.currentTarget;button.disabled=true;
      try{
        const records=[];let p=0;
        do{const data=await context.runtime.api(`/admin/learning/export?page=${p}&size=100`);records.push(...data.records);p=data.nextPage;
          if(p!==null&&(!Number.isSafeInteger(p)||p>1000))throw Error('Có quá nhiều nhãn. Hãy xuất từng phần qua API.');
        }while(p!==null);
        if(!records.length){context.ui.toast('Chưa có nhãn đủ điều kiện đã được duyệt.');return;}
        const blob=new context.window.Blob([JSON.stringify({schemaVersion:1,records},null,2)],{type:'application/json'}),url=context.window.URL.createObjectURL(blob),link=context.window.document.createElement('a');
        link.href=url;link.download='hitl-approved-materials.json';link.click();context.window.setTimeout(()=>context.window.URL.revokeObjectURL(url),1000);
        context.ui.toast(`Đã xuất ${records.length} nhãn đã duyệt.`);
      }catch(problem){context.ui.toast(problem.message);}finally{button.disabled=false;}
    };
    await load();
  }

  return {hitlMarkup, bindHitl, learningPage};
}
