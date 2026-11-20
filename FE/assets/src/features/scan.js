// scan: page-scoped state and behavior. No browser work runs at import time.
export function createScan(context) {
  function home() {
    context.ui.shell(`<section class="hero"><div class="hero-copy"><span class="tag dot">MỘT THÓI QUEN NHỎ. MỘT TƯƠNG LAI XANH.</span><h1>Phân loại đúng.<br>Bắt đầu <em>từ bạn.</em></h1><p>Chụp một bức ảnh, để AI giúp bạn nhận diện vật liệu và tìm cách phân loại phù hợp. Đơn giản hơn mỗi ngày.</p><div class="hero-note">${context.ui.icon('leaf')} Cùng tạo nên một vòng đời mới cho rác thải.</div></div><div class="upload-card"><div class="upload-top"><h2>Hôm nay bạn muốn phân loại gì?</h2><span class="tag">AI SCAN</span></div><label class="dropzone" id="dropzone" tabindex="0" for="file"><img class="illustration" src="../assets/scan-illustration.svg" alt="Chai nhựa và lon trong khung nhận diện"/><h3>Kéo thả ảnh vào đây</h3><p class="muted">hoặc nhấn để chọn ảnh từ thiết bị</p></label><input class="sr-only" type="file" id="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"/><input hidden type="file" id="camera" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" capture="environment"/><div class="upload-actions"><button class="btn primary" id="scan">${context.ui.icon('scan')} Phân tích ảnh ${context.ui.icon('arrow')}</button><button class="btn secondary" id="camera-button" aria-label="Chụp ảnh bằng camera" title="Chụp ảnh">${context.ui.icon('camera')}</button></div><div id="upload-error" class="error-text" role="alert" style="margin-top:10px"></div><p class="fineprint">JPG, PNG, WebP · Tối đa 10 MB / 12 MP · Một ảnh mỗi lượt</p></div></section><section class="material-strip" aria-label="Vật liệu được hỗ trợ"><div class="intro"><strong>Nhận diện 4 nhóm vật liệu</strong>Phân loại từ những thứ quen thuộc.</div>${Object.entries(context.ui.materials).map(([code,m])=>`<div class="material-item">${context.ui.materialIcon(code)}<div><strong>${m.name}</strong><p>${m.hint}</p></div></div>`).join('')}</section><section><div class="section-title"><h2>Ba bước, một thay đổi nhỏ.</h2><span class="eyebrow">DỄ BẮT ĐẦU · DỄ DUY TRÌ</span></div><div class="steps">${[['Chọn hoặc chụp ảnh','Đặt vật thể rõ nét trong khung hình, đủ ánh sáng.'],['Để AI nhận diện','Xem vật liệu, độ tin cậy và gợi ý thu gom.'],['Phân loại & lưu lại','Làm theo hướng dẫn, xem lại mọi lượt quét trong lịch sử.']].map(([t,d],i)=>`<div class="step"><span class="step-number">0${i+1}</span><div><h3>${t}</h3><p>${d}</p></div></div>`).join('')}</div></section>`);
    const drop = context.window.document.querySelector('#dropzone'), input=context.window.document.querySelector('#file'), camera=context.window.document.querySelector('#camera');
    const button=context.window.document.querySelector('#scan'), error=context.window.document.querySelector('#upload-error');
    let selected, preview, busy = false;
    async function choose(file) {
      if (!file || busy) return;
      error.textContent='';
      const mime=(file.type || '').toLowerCase();
      const recognizedType=['image/jpeg','image/png','image/webp'].includes(mime);
      const unknownType=!mime || mime==='application/octet-stream';
      const recognizedExtension=/\.(jpe?g|png|webp)$/i.test(file.name);
      if ((!recognizedType && !(unknownType && recognizedExtension)) || file.size > 10*1024*1024) { error.textContent='Chọn ảnh JPG, PNG hoặc WebP, tối đa 10 MB.'; input.value=''; camera.value=''; return; }
      const url=context.window.URL.createObjectURL(file);
      try {
        const img=new context.window.Image(); img.src=url; await img.decode();
        if (img.width>8192 || img.height>8192 || img.width*img.height>12000000) throw new Error('Ảnh vượt giới hạn 12 megapixel hoặc cạnh dài nhất 8192 px. Hãy giảm kích thước ảnh.');
        if(preview) context.window.URL.revokeObjectURL(preview); preview=url; selected=file;
        drop.innerHTML=`<img class="preview" src="${url}" alt="Ảnh bạn chọn để phân loại"/><h3 class="upload-filename" title="${context.ui.escape(file.name)}">${context.ui.escape(file.name)}</h3><p class="muted">${(file.size/1024/1024).toFixed(2)} MB · Nhấn để đổi ảnh</p>`;
      } catch(e) { context.window.URL.revokeObjectURL(url); error.textContent=e.message || 'Không thể mở ảnh này.'; }
    }
    input.addEventListener('change',()=>choose(input.files[0])); camera.addEventListener('change',()=>choose(camera.files[0]));
    drop.addEventListener('keydown', e=>{ if(['Enter',' '].includes(e.key)){e.preventDefault();input.click();} });
    for(const event of ['dragenter','dragover']) drop.addEventListener(event,e=>{e.preventDefault();drop.classList.add('dragging');});
    for(const event of ['dragleave','drop']) drop.addEventListener(event,e=>{e.preventDefault();drop.classList.remove('dragging');});
    drop.addEventListener('drop',e=>choose(e.dataTransfer.files[0]));
    context.window.document.querySelector('#camera-button').addEventListener('click',()=>camera.click());
    button.addEventListener('click',async()=>{
      if(busy)return;
      if(!selected){error.textContent='Bạn cần chọn hoặc chụp một ảnh trước khi phân tích.';input.focus();return;}
      busy=true; button.disabled=true; input.disabled=true; camera.disabled=true;
      context.window.document.querySelector('#camera-button').disabled=true; drop.setAttribute('aria-disabled','true'); error.textContent='';
      try {
        if(!context.runtime.account || !context.runtime.session?.token) {
          if(!await context.auth.requestSignIn('Bạn cần đăng nhập để phân tích và lưu kết quả. Ảnh đã chọn vẫn được giữ; đăng nhập xong sẽ tiếp tục gửi ảnh.')) {
            error.textContent='Bạn chưa đăng nhập. Ảnh vẫn được giữ; nhấn Phân tích ảnh khi muốn tiếp tục.'; return;
          }
        }
        for(let attempt=0;attempt<2;attempt++) {
          button.innerHTML='<span class="spinner"></span> Đang phân tích ảnh…';
          try {
            await ensureScanApi();
            const form=new context.window.FormData();form.append('file',selected);
            const result=await context.runtime.api('/scans',{method:'POST',body:form}); context.window.location.href=context.runtime.pageUrl(`result_analys.html?id=${result.id}`); return;
          } catch(e) {
            if(!e.authRequired || attempt!==0)throw e;
            if(!await context.auth.requestSignIn(e.message+' Ảnh vẫn được giữ; đăng nhập xong sẽ tiếp tục gửi ảnh.')) {
              error.textContent=e.message+' Ảnh đã chọn vẫn được giữ.'; return;
            }
          }
        }
      } catch(e){error.textContent=e.message;}
      finally {
        busy=false; button.disabled=false; input.disabled=false; camera.disabled=false;
        context.window.document.querySelector('#camera-button').disabled=false;drop.removeAttribute('aria-disabled');
        button.innerHTML=`${context.ui.icon('scan')} Phân tích ảnh ${context.ui.icon('arrow')}`;
      }
    });
  }

  let scanApiChecked = false;

  async function ensureScanApi() {
    if(scanApiChecked)return;
    let response;
    try { response=await context.window.fetch(context.runtime.API+'/system/info',{cache:'no-store',signal:context.window.AbortSignal.timeout(10000)}); }
    catch { throw new Error('Không kết nối được BE. Kiểm tra backend trên cổng đã cấu hình; ảnh vẫn được giữ.'); }
    if(!response.ok)throw new Error('BE đang chạy bản cũ hoặc sai project, chưa có API phân tích mới. Cần khởi động lại BE từ thư mục BE/hauiTrash. Ảnh vẫn được giữ.');
    const info=await response.json();
    if(info.scanApiVersion!==1)throw new Error('Phiên bản BE chưa tương thích với trang phân tích. Hãy cập nhật và khởi động lại BE.');
    scanApiChecked=true;
  }

  return {home};
}
