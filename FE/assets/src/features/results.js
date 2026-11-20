// results: page-scoped state and behavior. No browser work runs at import time.
export function createResults(context) {
  function componentMarkup(d) {
    const parts=Array.isArray(d.components)?d.components:[];
    const state=d.componentAnalysisStatus || 'NOT_RUN';
    if(state!=='COMPLETED') {
      const messages={NOT_RUN:'Lượt quét này chưa phân tích bộ phận.',MODEL_UNAVAILABLE:'Model bộ phận chưa sẵn sàng. Kết quả hiện tại là vật liệu của cả chai.',FAILED:'Phân tích bộ phận gặp lỗi. Kết quả nhận diện chai vẫn được giữ.'};
      return `<p class="component-state small muted">${context.ui.escape(messages[state] || messages.NOT_RUN)}</p>`;
    }
    if(!parts.length)return '<p class="component-state small muted">Đã phân tích nhưng chưa tìm thấy bộ phận đủ điều kiện. Thử ảnh gần và rõ hơn.</p>';
    return `<section class="components" aria-label="Bộ phận của chai"><h4>${context.ui.number(parts.length)} bộ phận được nhận diện</h4>${parts.map(c=>`<div class="component-row"><button class="component-select" type="button" data-component-box="${context.ui.escape([c.x1,c.y1,c.x2,c.y2].join(','))}" aria-pressed="false"><span class="component-name">${context.ui.escape(c.partName || ({cap:'Nắp chai',body:'Thân/vỏ chai',label:'Nhãn dán'})[c.partType] || 'Bộ phận')}</span><span class="status ${c.status==='NEEDS_CONFIRM'?'pending':''}">${context.ui.escape(c.materialName || context.ui.materialName(c.material))}</span>${context.ui.icon('scan')}</button><div class="component-confidence small muted">Vị trí: ${context.ui.percent(c.detectionConfidence)} · Vật liệu: ${context.ui.percent(c.materialConfidence)}${c.status==='NEEDS_CONFIRM'?' · Cần kiểm tra thêm':''}</div><p class="small">${context.ui.escape(c.action || 'Kiểm tra trực tiếp vật liệu trước khi phân loại.')}</p>${context.learning.hitlMarkup(c)}</div>`).join('')}</section>`;
  }

  function detectionMarkup(d,i) {
    return `<article class="detection"><div class="detection-top">${context.ui.materialIcon(d.label)}<div><span class="eyebrow" style="font-size:9px;letter-spacing:1px">CHAI ${String(i+1).padStart(2,'0')}</span><h3>${context.ui.escape(d.labelDisplay || context.ui.materialName(d.label))}</h3></div><div class="confidence"><strong>${context.ui.percent(d.confidence)}</strong><p>Vật liệu cả chai</p></div></div><span class="status ${d.status==='NEEDS_CONFIRM'?'pending':''}">${d.status==='NEEDS_CONFIRM'?'Cần kiểm tra thêm':context.ui.escape(context.ui.materialName(d.label))}</span><div class="confidence-bar"><i style="width:${context.ui.percent(d.confidence)}"></i></div><div class="guidance"><strong>${context.ui.escape(d.binName || 'Hướng dẫn phân loại')}</strong>${context.ui.escape(d.action || 'Chưa có hướng dẫn cho vật liệu này. Hãy kiểm tra thủ công.')}</div></article>`;
  }

  function detailedParentsMarkup(parents) {
    return parents.map((parent,i)=>{
      const found=new Set((parent.components || []).map(c=>c.partType));
      const missing=[['cap','nắp'],['body','thân'],['label','nhãn']].filter(([code])=>!found.has(code)).map(([,name])=>name);
      return `<article class="detailed-bottle"><div class="detailed-bottle-title"><span class="eyebrow">CHAI ${String(i+1).padStart(2,'0')}</span><span class="small muted">${context.ui.number(parent.components?.length || 0)} bộ phận</span></div>${componentMarkup(parent)}${missing.length?`<p class="small muted">Chưa phát hiện rõ: ${missing.join(', ')}. Bộ phận có thể bị che khuất hoặc model chưa nhận ra.</p>`:''}</article>`;
    }).join('');
  }

  function resultMarkup(r, modal=false) {
    if(r.status !== 'DONE') return `<div class="notice ${r.status==='ERROR'?'error':'warning'}">${context.ui.icon('info')}<span>${context.ui.escape(r.errorMessage || (r.status==='PROCESSING'?'Lượt quét đang được phân tích. Nếu bị gián đoạn quá 5 phút, bạn có thể thử xử lý lại.':'Ảnh đã được lưu và đang chờ phân tích.'))}</span></div><div class="result-photo"><img src="${context.ui.imageUrl(r.cloudinaryUrl)}" alt="Ảnh của lượt quét"/></div>${['ERROR','UPLOADED','PROCESSING'].includes(r.status)?`<button class="btn primary" data-retry="${r.id}" style="margin-top:20px">${context.ui.icon('refresh')} Phân tích lại lượt quét này</button>`:''}`;
    if (!r.count) return `<div class="result-layout"><div class="result-photo"><img src="${context.ui.imageUrl(r.cloudinaryUrl)}" alt="Ảnh đã phân tích"/></div>${context.ui.empty('Chưa tìm thấy vật thể','Thử chụp gần hơn, đặt vật thể trên nền đơn giản và đảm bảo đủ sáng.',modal?'':`<a class="btn primary" href="index.html">${context.ui.icon('camera')} Chụp ảnh khác</a>`)}</div>`;
    return `${r.requiresConfirmation?`<div class="notice warning">${context.ui.icon('info')} Một số vật thể hoặc bộ phận cần kiểm tra thêm. Hãy đối chiếu ảnh trước khi làm theo gợi ý phân loại.</div>`:''}<div class="result-layout"><div><div class="result-photo"><div class="component-photo-stage"><img data-result-image data-original-image="${context.ui.imageUrl(r.cloudinaryUrl)}" src="${context.ui.imageUrl(r.annotatedUrl || r.cloudinaryUrl)}" alt="Ảnh nhận diện chai; chọn bộ phận để xem vị trí"/><svg data-component-overlay hidden aria-hidden="true" preserveAspectRatio="none"><rect data-component-rect/><text data-component-label/></svg><svg data-all-component-overlay hidden aria-hidden="true" preserveAspectRatio="none"></svg></div><div class="photo-caption"><span>${context.ui.icon('scan')} Ảnh từ lượt quét #${r.id}</span><div class="image-toggle"><button class="btn ghost small active" data-image="${context.ui.imageUrl(r.annotatedUrl || r.cloudinaryUrl)}">Nhận diện</button><button class="btn ghost small" data-image="${context.ui.imageUrl(r.cloudinaryUrl)}">Ảnh gốc</button><button type="button" class="btn ghost small" data-detail-tab aria-pressed="false">Nhận diện chi tiết</button></div></div></div><p class="small muted component-hint" data-highlight-hint role="status">${r.componentCount?'Chọn một bộ phận để xem vị trí trên ảnh.':''}</p><div class="notice" style="margin-top:18px">${context.ui.icon('leaf')} Hướng dẫn thu gom mang tính tham khảo. Kiểm tra quy định của điểm thu gom tại địa phương.</div></div><div><div data-standard-summary class="panel" style="margin-bottom:17px"><div class="panel-head" style="margin-bottom:0"><h2>Tổng quan kết quả</h2>${context.ui.statusBadge(r.status)}</div><div class="result-meta"><div><strong>${context.ui.number(r.count)}</strong><span>Chai được nhận diện</span></div><div><strong>${context.ui.percent(r.confidenceAvg)}</strong><span>Độ tin cậy vật liệu cả chai</span></div></div>${r.componentCount?`<p class="component-summary">${context.ui.number(r.componentCount)} bộ phận · ${r.detections.filter(d=>d.componentAnalysisStatus==='COMPLETED').length} chai đã phân tích bộ phận</p>`:''}<p class="small muted">${context.ui.date(r.createdAt,true)} · Mã lượt quét #${r.id}${r.componentModelVersion?` · Model bộ phận: ${context.ui.escape(r.componentModelVersion)}`:''}</p></div><div data-standard-detections class="detection-list">${r.detections.map(detectionMarkup).join('')}</div><section data-detail-panel class="panel detail-panel" hidden aria-label="Nhận diện chi tiết">${detailedParentsMarkup(r.detections)}</section></div></div>`;
  }

  function bindResult(target, id, reload) {
    const photo=target.querySelector('[data-result-image]'),overlay=target.querySelector('[data-component-overlay]');
    const allOverlay=target.querySelector('[data-all-component-overlay]'),panel=target.querySelector('[data-detail-panel]');
    let selection=0,mode='legacy',cache=null,pending=null,focused=false;
    context.learning.bindHitl(target,id,()=>cache);
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
        const rect=context.window.document.createElementNS(ns,'rect');rect.setAttribute('x',box[0]);rect.setAttribute('y',box[1]);rect.setAttribute('width',box[2]-box[0]);rect.setAttribute('height',box[3]-box[1]);
        const name=button.querySelector('.component-name')?.textContent || 'Bộ phận';const kind=name.startsWith('Nắp')?'cap':name.startsWith('Thân')?'body':'label';
        rect.style.stroke=colors[kind];rect.style.fill=colors[kind]+'18';allOverlay.append(rect);
        const text=context.window.document.createElementNS(ns,'text');text.textContent=name;text.setAttribute('x',box[0]+3);text.setAttribute('y',Math.max(20,box[1]-6));text.setAttribute('font-size',Math.max(14,photo.naturalWidth/45));text.style.fill=colors[kind];allOverlay.append(text);
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
      panel.innerHTML=`<div class="panel-head"><div><span class="eyebrow">NHẬN DIỆN CHI TIẾT</span><h2>Thành phần của chai</h2></div><span class="tag">Thử nghiệm</span></div><div class="notice warning small">${context.ui.icon('info')} Kiểm tra trực tiếp vật liệu trước khi phân loại.</div><p class="detail-summary">${context.ui.number(data.componentCount)} bộ phận · ${context.ui.number(data.parents.length)} chai</p>${detailedParentsMarkup(data.parents)}<div class="detail-footer"><span class="small muted">${context.ui.escape(data.modelVersion || '')}</span><button type="button" class="btn ghost small" data-detail-retry>Phân tích lại chi tiết</button></div>`;
      if(mode==='detail')drawAll();
    }
    async function loadDetails(force=false){
      if(cache&&!force){renderDetails(cache);return;}
      if(pending)return pending;
      panel.innerHTML=`<div class="loading" role="status"><span class="spinner"></span> Đang nhận diện các thành phần của chai…</div>`;
      pending=(async()=>{
        try{
          const data=await context.runtime.api(`/scans/${id}/detailed`,{method:'POST',signal:context.window.AbortSignal.timeout(180000)});
          if(data.requestId!==Number(id)||data.status!=='COMPLETED'||!Array.isArray(data.parents)||!Number.isFinite(data.componentCount))throw new Error('Dữ liệu nhận diện chi tiết chưa hợp lệ. Kết quả nhận diện cũ vẫn được giữ.');
          cache=data;renderDetails(data);
        }catch(error){
          panel.innerHTML=`<div class="notice error" role="alert">${context.ui.icon('info')}<span>${context.ui.escape(error.message)}</span></div><p class="small muted">Bạn vẫn có thể xem ảnh gốc và kết quả nhận diện đã lưu.</p><button type="button" class="btn secondary" data-detail-retry>Thử lại nhận diện chi tiết</button>`;
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
      try{await context.runtime.api(`/scans/${id}/retry`,{method:'POST'});await reload();}
      catch(error){context.ui.toast(error.message);button.disabled=false;button.innerHTML=`${context.ui.icon('refresh')} Thử lại`;}
    });
  }

  function componentStatistics(s) {
    if(!s.totalComponents)return '';
    return `<section class="panel component-statistics"><div class="panel-head"><div><h2>Vật liệu từng bộ phận</h2><p>${context.ui.number(s.totalComponents)} bộ phận · ${context.ui.number(s.componentsNeedingConfirmation)} cần kiểm tra thêm</p></div>${context.ui.icon('leaf')}</div>${context.statistics.materialBars(s.componentMaterials || []).replace('Tính theo số vật thể được nhận diện, không phải số ảnh.','Tính riêng theo số bộ phận; không cộng vào số chai hoặc vật thể.')}</section>`;
  }

  async function resultPage() {
    context.ui.shell(`${context.ui.heading('KẾT QUẢ NHẬN DIỆN','Hiểu vật liệu. Phân loại đúng.','Mỗi vật thể đều có một nơi phù hợp để bắt đầu vòng đời mới.',`<a class="btn secondary" href="index.html">${context.ui.icon('scan')} Quét ảnh mới</a>`)}<div id="result">${context.ui.loading()}</div>`);
    const id=new context.window.URLSearchParams(context.window.location.search).get('id'); const target=context.window.document.querySelector('#result');
    if(!/^\d+$/.test(id || '')) { target.innerHTML=context.ui.empty('Chưa có kết quả để hiển thị','Chọn một ảnh để bắt đầu hoặc mở lại một lượt quét từ lịch sử.',`<a class="btn primary" href="index.html">${context.ui.icon('scan')} Bắt đầu phân loại</a> <a class="btn secondary" href="history.html">Xem lịch sử</a>`); return; }
    const load=async()=>{target.innerHTML=context.ui.loading();try{const r=await context.runtime.api(`/scans/${id}`);target.innerHTML=resultMarkup(r);bindResult(target,id,load);}catch(e){context.ui.showError(target,e,load);}};
    await load();
  }

  async function detailDialog(id) {
    let dialog=context.window.document.querySelector('#detail-dialog'); if(dialog) dialog.remove();
    dialog=context.window.document.createElement('dialog'); dialog.id='detail-dialog'; dialog.setAttribute('aria-labelledby','detail-title');
    dialog.innerHTML=`<div class="dialog-head"><h2 id="detail-title">Chi tiết lượt quét #${id}</h2><button class="btn ghost" data-close aria-label="Đóng">${context.ui.icon('close')}</button></div><div id="dialog-content">${context.ui.loading()}</div>`;
    context.window.document.body.append(dialog); dialog.querySelector('[data-close]').onclick=()=>dialog.close(); dialog.showModal();
    const target=dialog.querySelector('#dialog-content');
    const load=async()=>{try{const r=await context.runtime.api(`/scans/${id}`);target.innerHTML=resultMarkup(r,true);bindResult(target,id,load);}catch(e){context.ui.showError(target,e,load);}};
    await load();
  }

  function bindDetails(target) { target.querySelectorAll('[data-detail]').forEach(b=>b.addEventListener('click',()=>detailDialog(b.dataset.detail))); }

  return {bindDetails, componentStatistics, resultPage};
}
