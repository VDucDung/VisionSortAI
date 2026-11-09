"""Separate experimental component service (8011); no legacy model or cloud uploads."""
import json,logging,os,threading
from pathlib import Path
import anyio
import numpy as np
from fastapi import FastAPI,File,Form,UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field,HttpUrl,model_validator
from .inference import ComponentEngine
from . import PARTS,MATERIALS
from trashsmart.pipeline.input_limits import download_image,read_upload,ImageInputError
from trashsmart.pipeline.admission import PredictionAdmission

app=FastAPI(title='TrashSmart Detailed Recognition Experiment')
app.add_middleware(PredictionAdmission,limit=1,max_body=11*1024*1024)
_engine=None;_signature=None;_lock=threading.Lock()

class Parent(BaseModel):
    id:int=Field(ge=1)
    x1:int=Field(ge=0,le=8192);y1:int=Field(ge=0,le=8192)
    x2:int=Field(ge=1,le=8192);y2:int=Field(ge=1,le=8192)
    @model_validator(mode='after')
    def positive_box(self):
        if self.x2<=self.x1 or self.y2<=self.y1:raise ValueError('Empty parent box')
        return self

class ParentRequest(BaseModel):
    request_id:int=Field(ge=1)
    parents:list[Parent]=Field(min_length=1,max_length=30)
    @model_validator(mode='after')
    def unique_parents(self):
        if len({p.id for p in self.parents})!=len(self.parents):raise ValueError('Repeated detection ID')
        return self

class UrlRequest(ParentRequest):
    image_url:HttpUrl

def config():
    path=Path(os.getenv('DETAILS_RELEASE_PATH',str(Path(__file__).resolve().parents[1]/'models/components-experimental-v1/experimental-release.json'))).resolve()
    release=json.loads(path.read_text(encoding='utf8'))
    if release.get('experimental') is not True or release.get('trainingScope')!='bottle-components':raise ValueError('Not an experimental component release')
    for key in ('detector','materialClassifier'):
        weight=(path.parent/release[key]['file']).resolve()
        if not weight.is_relative_to(path.parent) or not weight.is_file():raise ValueError('Missing experimental checkpoint')
    evaluation=(path.parent/release['evaluationReport']).resolve()
    if not evaluation.is_relative_to(path.parent):raise ValueError('Invalid evaluation path')
    report=json.loads(evaluation.read_text(encoding='utf8'))
    if report.get('split')!='test' or report.get('materialSha256')!=release['materialClassifier']['sha256'] or report.get('detectorSha256')!=release['detector']['sha256']:
        raise ValueError('Evaluation/checkpoint mismatch')
    return release,path

def inverse_box(box,k,width,height):
    a,b,c,d=box
    return ([a,b,c,d],[width-d,a,width-b,c],[width-c,height-d,width-a,height-b],[b,height-c,d,height-a])[k]

def iou(a,b):
    w=max(0,min(a[2],b[2])-max(a[0],b[0]));h=max(0,min(a[3],b[3])-max(a[1],b[1]));inter=w*h
    return inter/max(1,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)

class ExperimentalEngine(ComponentEngine):
    def __init__(self, release, path):
        super().__init__(release, path)
        # Suppress weak rotated proposals in the web experiment. This is an
        # inference policy, not a claim that the model has been validated.
        self.detector_threshold = max(.5, self.detector_threshold)

    def predict(self,image,parents):
        import torch
        from PIL import Image
        output=[];height,width=image.shape[:2]
        for parent in parents:
            x1,y1,x2,y2=(parent[k] for k in ('x1','y1','x2','y2'))
            if not (0<=x1<x2<=width and 0<=y1<y2<=height):raise ImageInputError('Parent coordinates outside original image')
            crop=image[y1:y2,x1:x2];h,w=crop.shape[:2];proposals=[]
            for k in (0,1,2,3):
                result=self.detector.predict(np.rot90(crop,k).copy(),conf=self.detector_threshold,imgsz=self.image_size,max_det=12,
                    agnostic_nms=False,device='cpu',verbose=False)[0]
                if result.boxes is None:continue
                for box in result.boxes:
                    bbox=inverse_box([int(v) for v in box.xyxy[0].tolist()],k,w,h)
                    bbox=[max(0,bbox[0]),max(0,bbox[1]),min(w,bbox[2]),min(h,bbox[3])]
                    if bbox[2]>bbox[0] and bbox[3]>bbox[1]:proposals.append((float(box.conf.item()),int(box.cls.item()),bbox))
            selected=[]
            for confidence,kind,box in sorted(proposals,reverse=True):
                same=[v for v in selected if v[1]==kind]
                if len(same)>=(4 if PARTS[kind]=='label' else 1) or any(iou(box,v[2])>.55 for v in same):continue
                selected.append((confidence,kind,box))
            components=[]
            if selected:
                crops=[self.transform(Image.fromarray(crop[b[1]:b[3],b[0]:b[2],::-1].copy())) for _,_,b in selected]
                with torch.inference_mode():probabilities=self.classifier(torch.stack(crops)).softmax(1)
                for (confidence,kind,b),prob in zip(selected,probabilities):
                    value,cls=prob.max(0);value=float(value)
                    components.append({'partType':PARTS[kind],'material':MATERIALS[int(cls)] if value>=self.threshold else 'unknown',
                        'detectionConfidence':round(confidence,5),'materialConfidence':round(value,5),'needsConfirm':True,
                        'status':'NEEDS_CONFIRM','x1':b[0]+x1,'y1':b[1]+y1,'x2':b[2]+x1,'y2':b[3]+y1})
            output.append({'detectionId':parent['id'],'componentAnalysisStatus':'COMPLETED','components':components})
        return output

def analyze(image,request):
    global _engine,_signature
    try:release,path=config()
    except (ValueError,KeyError,OSError,TypeError):return JSONResponse({'error':'Model nhận diện chi tiết chưa sẵn sàng.'},status_code=503)
    signature=json.dumps(release,sort_keys=True)+str(path)
    with _lock:
        if _engine is None or signature!=_signature:
            import torch
            torch.set_num_threads(4)
            _engine=ExperimentalEngine(release,path);_signature=signature
        parents=_engine.predict(image,[p.model_dump() for p in request.parents])
    return {'requestId':request.request_id,'modelVersion':release['version'],'experimental':True,'status':'COMPLETED',
        'imageWidth':image.shape[1],'imageHeight':image.shape[0],'componentCount':sum(len(p['components']) for p in parents),'parents':parents,
        'notice':'Nhận diện chi tiết đang thử nghiệm. Kiểm tra trực tiếp vật liệu trước khi phân loại.'}

@app.get('/health')
def health():
    try:release,_=config();return {'service':'TrashSmart component experiment','status':'READY','modelVersion':release['version'],'experimental':True}
    except (ValueError,KeyError,OSError,TypeError):return {'service':'TrashSmart component experiment','status':'MODEL_UNAVAILABLE','experimental':True}

@app.post('/predict-image-url')
def predict_url(request:UrlRequest):
    try:return analyze(download_image(str(request.image_url)),request)
    except ImageInputError as error:return JSONResponse({'error':str(error)},status_code=error.status_code)
    except Exception:
        logging.exception('Detailed analysis failed');return JSONResponse({'error':'Phân tích chi tiết gặp lỗi.'},status_code=500)

@app.post('/predict-image')
def predict_upload(file:UploadFile=File(...),parents:str=Form(...),request_id:int=Form(...)):
    try:
        request=ParentRequest.model_validate({'parents':json.loads(parents),'request_id':request_id})
        return analyze(read_upload(file.file),request)
    except ImageInputError as error:return JSONResponse({'error':str(error)},status_code=error.status_code)
    except (ValueError,TypeError):return JSONResponse({'error':'Invalid parent metadata'},status_code=422)
