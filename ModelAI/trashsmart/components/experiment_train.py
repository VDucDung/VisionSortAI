"""Isolated research training. Never modifies the legacy pipeline or production release."""
import hashlib,io,json,math,os,shutil,time,urllib.request
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(r'D:\thacsi\DOAN\HAUI-TRASH\AI_DATASET\bottle_components')
JOB=ROOT/'05_models/components-experimental-v1'
HEADERS={'User-Agent':'TrashSmart-Academic-Research/1.0'}
CLASSES=('glass','metal','paper','plastic')
CATEGORIES={6:'glass',8:'metal',33:'paper',5:'plastic',7:'plastic',4:'plastic'}

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def status(**values):
    file=JOB/'status.json';old=json.loads(file.read_text()) if file.exists() else {}
    old.update(values)
    if values.get('phase') and values['phase']!='FAILED':old.pop('error',None);old.pop('errorType',None)
    old.update(pid=os.getpid(),updatedAt=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),legacyModelReplaced=False)
    temp=file.with_suffix('.tmp');temp.write_text(json.dumps(old,indent=2),encoding='utf8')
    for attempt in range(40):
        try:temp.replace(file);break
        except PermissionError:
            if attempt==39:raise
            time.sleep(.05)

def download(item,cache):
    image=item;file=cache/f"{image['id']}.jpg"
    if file.exists():return image['id'],file,None
    url=image['flickr_url']
    host=urlparse(url).hostname or ''
    if urlparse(url).scheme!='https' or not (host=='img.tacodataset.org' or host.endswith('.staticflickr.com')):return image['id'],None,'Source host not allowlisted'
    try:
        request=urllib.request.Request(url,headers=HEADERS)
        with urllib.request.urlopen(request,timeout=20) as response:body=response.read(20*1024*1024+1)
        if len(body)>20*1024*1024:raise ValueError('Image size limit')
        from PIL import Image
        with Image.open(io.BytesIO(body)) as raw:
            if raw.width*raw.height>32_000_000 or raw.size!=(image['width'],image['height']):raise ValueError('Source dimensions mismatch')
            raw.load()
        temp=file.with_suffix('.partial');temp.write_bytes(body);temp.replace(file)
        return image['id'],file,None
    except Exception as error:return image['id'],None,str(error)

def dataset():
    import cv2,numpy as np
    from PIL import Image
    metadata=ROOT/'03_public/taco-material-review/annotations.json'
    data=json.loads(metadata.read_text(encoding='utf8'));images={x['id']:x for x in data['images']}
    selected=[];counts=Counter()
    for annotation in sorted(data['annotations'],key=lambda a:hashlib.sha256(f"exp-v1:{a['id']}".encode()).hexdigest()):
        material=CATEGORIES.get(annotation['category_id']);bbox=annotation['bbox']
        if material and min(bbox[2:])>=24 and counts[material]<90:
            selected.append(annotation);counts[material]+=1
    ids=sorted({a['image_id'] for a in selected});cache=ROOT/'03_public/taco-material-review/images';cache.mkdir(exist_ok=True)
    files={};errors=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(download,images[i],cache) for i in ids]
        for n,future in enumerate(as_completed(futures),1):
            i,file,error=future.result()
            if file:files[i]=file
            else:errors.append({'imageId':i,'error':error})
            status(phase='DOWNLOADING',processed=n,total=len(ids),downloadErrors=len(errors))
    status(phase='GROUPING_DATA',downloadedImages=len(files))
    # Conservative source-image groups: exact and very similar full images stay together.
    group={i:i for i in files};phashes={};digests={}
    def find(i):
        while group[i]!=i:group[i]=group[group[i]];i=group[i]
        return i
    def union(a,b):
        a,b=find(a),find(b);group[max(a,b)]=min(a,b)
    for i,file in files.items():
        with Image.open(file) as raw:small=np.asarray(raw.convert('L').resize((32,32)),dtype=np.float32)
        low=cv2.dct(small)[:8,:8].flatten()[1:];bits=0
        for bit in low>np.median(low):bits=(bits<<1)|int(bit)
        phashes[i]=bits;digests[i]=sha(file)
    for index,a in enumerate(sorted(files)):
        for b in sorted(files)[:index]:
            if digests[a]==digests[b] or (phashes[a]^phashes[b]).bit_count()<=4:union(a,b)
    usable=[a for a in selected if a['image_id'] in files]
    for seed in range(42,142):
        splits={i:('train' if (n:=int(hashlib.sha256(f'{seed}:{find(i)}'.encode()).hexdigest()[:8],16)%100)<70 else 'val' if n<85 else 'test') for i in files}
        totals=Counter((splits[a['image_id']],CATEGORIES[a['category_id']]) for a in usable)
        if all(totals[s,m]>=(4 if s=='train' else 2) for s in ('train','val','test') for m in CLASSES):break
    else:raise ValueError('Not enough source-image groups for every material split')
    output=JOB/'dataset';manifest=[];count=Counter()
    for annotation in usable:
        i=annotation['image_id'];material=CATEGORIES[annotation['category_id']];split=splits[i]
        x,y,w,h=annotation['bbox'];meta=images[i]
        box=[max(0,math.floor(x)),max(0,math.floor(y)),min(meta['width'],math.ceil(x+w)),min(meta['height'],math.ceil(y+h))]
        if box[2]<=box[0] or box[3]<=box[1]:continue
        dest=output/'material'/split/material/f"taco-{annotation['id']}.jpg";dest.parent.mkdir(parents=True,exist_ok=True)
        with Image.open(files[i]) as raw:raw.convert('RGB').crop(box).save(dest,quality=95)
        manifest.append({'crop':dest.relative_to(output).as_posix(),'material':material,'split':split,'groupId':f'taco-image-cluster-{find(i)}',
            'source':'TACO official category annotation','imageId':i,'annotationId':annotation['id'],'categoryId':annotation['category_id'],
            'sourceUrl':meta['flickr_url'],'sourceSha256':digests[i],'bbox':box,'sourceLicenseMetadata':meta.get('license'),
            'annotationSourceSha256':sha(metadata),'physicalVerificationByAssistant':False})
        count[f'material/{split}/{material}']+=1
    # User-declared, visually reviewed crops remain train-only; never repartition the old dataset.
    user=ROOT/'04_prepared/reviewed-materials-v2';user_report=json.loads((user/'dataset-report.json').read_text(encoding='utf8'))
    for row in user_report['materialManifest']:
        dest=output/'material/train'/row['material']/('user-'+Path(row['crop']).name);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(user/row['crop'],dest)
        manifest.append({**row,'crop':dest.relative_to(output).as_posix(),'source':'user-declaration-reviewed-geometry','split':'train'})
        count['material/train/'+row['material']]+=1
    report={'trainingScope':'bottle-components','counts':dict(count),'materialManifest':manifest,'splitSeed':seed,
        'splitPolicy':'TACO source-image/perceptual clusters held out; local declared products remain source train. Not an independent real-bottle product benchmark.',
        'sourceAnnotationsSha256':hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),
        'downloadErrors':errors,'auxiliaryDomain':'Normal paper and whole glass/plastic bottle crops supplement the part material classifier; no fake parent bottle labels.',
        'sourceRepository':'https://github.com/pedropro/TACO','physicalMaterialVerificationPerformed':False}
    (output/'dataset-report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return output,report

def train(data,report):
    import torch
    from torch.utils.data import DataLoader,TensorDataset
    from torchvision.datasets import ImageFolder
    from torchvision.models import resnet18,ResNet18_Weights
    from .training import material_transform
    torch.manual_seed(42);torch.set_num_threads(4)
    model=resnet18(weights=ResNet18_Weights.DEFAULT);model.eval();head=torch.nn.Linear(model.fc.in_features,4);model.fc=torch.nn.Identity()
    features={};labels={}
    for split in ('train','val','test'):
        dataset=ImageFolder(data/'material'/split,transform=material_transform())
        if dataset.classes!=list(CLASSES):raise ValueError('Class order mismatch')
        feats=[];targets=[]
        with torch.inference_mode():
            for n,(x,y) in enumerate(DataLoader(dataset,batch_size=16,num_workers=0)):
                feats.append(model(x).clone());targets.append(y)
                status(phase='EXTRACTING_FEATURES',split=split,batch=n+1)
        features[split]=torch.cat(feats).clone();labels[split]=torch.cat(targets)
    # Frozen eval backbone + fixed transform: caching is equivalent to recomputing features each epoch.
    optimizer=torch.optim.AdamW(head.parameters(),lr=.003,weight_decay=.01)
    class_counts=torch.bincount(labels['train'],minlength=4).float();loss_fn=torch.nn.CrossEntropyLoss(weight=len(labels['train'])/(4*class_counts))
    loader=DataLoader(TensorDataset(features['train'],labels['train']),batch_size=16,shuffle=True,generator=torch.Generator().manual_seed(42))
    def score(split):
        with torch.no_grad():prob=head(features[split]).softmax(1);pred=prob.argmax(1)
        confusion=torch.zeros((4,4),dtype=torch.int64)
        for a,b in zip(labels[split],pred):confusion[a,b]+=1
        f1=[2*confusion[i,i].item()/max(1,confusion[i,:].sum().item()+confusion[:,i].sum().item()) for i in range(4)]
        return {'accuracy':float((pred==labels[split]).float().mean()),'macroF1':sum(f1)/4,'f1ByClass':dict(zip(CLASSES,f1)),
                'confusionMatrix':confusion.tolist(),'count':len(labels[split]),'confidenceCoverageAt070':float((prob.max(1).values>=.7).float().mean())}
    best=-1;best_state=None;best_epoch=0
    for epoch in range(75):
        head.train();total=0.
        for x,y in loader:
            optimizer.zero_grad();loss=loss_fn(head(x),y);loss.backward();optimizer.step();total+=loss.item()*len(y)
        head.eval();val=score('val')
        if val['macroF1']>best:best=val['macroF1'];best_state={k:v.detach().clone() for k,v in head.state_dict().items()};best_epoch=epoch+1
        status(phase='TRAINING_CLASSIFIER',epoch=epoch+1,maxEpochs=75,valMacroF1=val['macroF1'],loss=total/len(labels['train']))
    head.load_state_dict(best_state);head.eval();evaluation={'split':'test','classes':list(CLASSES),'material':score('test'),
        'validation':score('val'),'bestEpoch':best_epoch,'endToEndReviewed':False,'benchmarkScope':'TACO source-image-held-out auxiliary material crops; not physical bottle-product accuracy','experimental':True}
    model.fc=head
    payload={'training_scope':'bottle-components','architecture':'resnet18','class_names':list(CLASSES),'model_state_dict':model.state_dict(),
        'epoch':best_epoch-1,'training_mode':'frozen-backbone-cached-features','dataset_sha256':report['sourceAnnotationsSha256'],'validated':False}
    weight=JOB/'material-resnet18.pth';torch.save(payload,weight)
    detector=JOB/'parts-yolo11n.pt';shutil.copyfile(ROOT/'05_models/research-detector-v2/training/detector/weights/best.pt',detector)
    evaluation['materialSha256']=sha(weight);evaluation['detectorSha256']=sha(detector)
    (JOB/'evaluation.json').write_text(json.dumps(evaluation,indent=2),encoding='utf8')
    release={'version':'components-experimental-v1','trainingScope':'bottle-components','experimental':True,'validated':False,
        'evaluationReport':'evaluation.json','detector':{'file':detector.name,'sha256':sha(detector)},
        'materialClassifier':{'file':weight.name,'sha256':sha(weight)},'materialThreshold':.7,'detectionThreshold':.25,'detectorImageSize':416}
    (JOB/'experimental-release.json').write_text(json.dumps(release,indent=2),encoding='utf8')
    status(phase='READY',evaluation=evaluation,experimentalRelease=str(JOB/'experimental-release.json'))

def main():
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[key]='4'
    if JOB.exists():
        previous=json.loads((JOB/'status.json').read_text())
        if previous.get('phase')!='FAILED' or (JOB/'material-resnet18.pth').exists():raise ValueError('Existing experiment must be preserved; select a new version')
        (JOB/f"failed-attempt-{int(time.time())}.json").write_text(json.dumps(previous,indent=2),encoding='utf8')
    else:JOB.mkdir(parents=True)
    from trashsmart.pipeline.config import YOLO_MODEL_PATH,RESNET_MODEL_PATH
    original={str(p):sha(p) for p in (Path(YOLO_MODEL_PATH),Path(RESNET_MODEL_PATH)) if p.is_file()}
    (JOB/'legacy-model-checksums.json').write_text(json.dumps(original,indent=2),encoding='utf8')
    try:
        status(phase='PREPARING',startedAt=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
        output,report=dataset();train(output,report)
        if any(sha(p)!=digest for p,digest in original.items()):raise ValueError('Legacy model changed externally')
    except Exception as error:status(phase='FAILED',errorType=type(error).__name__,error=str(error));raise

if __name__=='__main__':main()
