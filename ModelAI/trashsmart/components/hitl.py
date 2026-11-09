"""Reviewed HITL rounds. No server/worker, online weight update, or auto activation."""
import argparse, copy, hashlib, json, re, shutil
from collections import Counter
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from . import MATERIALS, PARTS
from trashsmart.pipeline.input_limits import download_image


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def phash(image):
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    low=cv2.dct(cv2.resize(gray,(32,32)).astype(np.float32))[:8,:8].flatten()[1:]
    value=0
    for bit in low>np.median(low):value=(value<<1)|int(bit)
    return value


def inside(root,name):
    target=(root/name).resolve()
    if not target.is_relative_to(root.resolve()):raise ValueError('Dataset path escapes its root')
    return target


def eligible(row):
    basis=row.get('verificationBasis')
    verified_basis=(basis in ('PHYSICAL_CHECK','PACKAGING_MARK') or
        basis=='ADMIN_VISUAL_REVIEW' and row.get('adminVerificationBasis')=='VISUAL_REVIEW' and row.get('verificationSource')=='ADMIN')
    return (row.get('schemaVersion')==1 and row.get('adminReviewed') is True and row.get('trainingConsent') is True and row.get('regionCorrect') is True
        and row.get('material') in MATERIALS and row.get('partType') in PARTS
        and verified_basis and row.get('split')=='train'
        and isinstance(row.get('caseId'),str) and re.fullmatch('[a-f0-9]{64}',row['caseId']))


def prepare(args):
    base=args.base_data.resolve();output=args.output.resolve()
    if output.exists():raise ValueError('Output exists; choose a new HITL round directory')
    if output.is_relative_to(base) or base.is_relative_to(output):raise ValueError('Round output must not overlap the base dataset')
    report=json.loads((base/'dataset-report.json').read_text(encoding='utf-8-sig'))
    exported=json.loads(args.feedback.read_text(encoding='utf-8-sig'))
    if report.get('trainingScope')!='bottle-components' or exported.get('schemaVersion')!=1 or not isinstance(exported.get('records'),list):
        raise ValueError('Expected component dataset and reviewed admin export')
    if len(exported['records'])>100_000:raise ValueError('Export too large for one local round')
    manifest=copy.deepcopy(report['materialManifest']);holdouts=[];holdout_sources={}
    for row in manifest:
        crop=inside(base,row['crop'])
        if row.get('split') not in ('train','val','test') or not crop.is_file():raise ValueError('Invalid base crop/split')
        if row['split'] in ('val','test'):
            if row.get('sourceImage'):source=inside(base,row['sourceImage'])
            elif row.get('imageId') is not None and args.source_cache:source=inside(args.source_cache,str(row['imageId'])+'.jpg')
            else:raise ValueError('Held-out source image is needed to reject near-duplicate feedback')
            image=cv2.imread(str(source))
            if image is None:raise ValueError('Missing held-out source image')
            if row.get('sourceSha256') and digest(source)!=row['sourceSha256']:raise ValueError('Held-out source hash mismatch')
            holdouts.append(phash(image))
            source_hash=digest(source);name=f'_holdout_sources/{source_hash}{source.suffix.lower()}'
            holdout_sources[name]=source;row['sourceImage']=name;row['sourceSha256']=source_hash
    output.mkdir(parents=True)
    for name,source in holdout_sources.items():
        dest=inside(output,name);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    for row in manifest:
        dest=inside(output,row['crop']);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(inside(base,row['crop']),dest)
        row['cropSha256']=digest(dest)
    added=[];skipped=[];images={}
    seen={(r['sourcePixelSha256'],*r['bbox'],r['partType']):r['material'] for r in manifest if r.get('source')=='admin-reviewed-hitl'}
    seen_ids={r['caseId'] for r in manifest if r.get('caseId')}
    # Keep feedback in train only. Test/validation files and assignments are immutable.
    for row in exported['records']:
        case=row.get('caseId','invalid')
        if not eligible(row):skipped.append({'caseId':case,'reason':'not_verified_or_not_approved'});continue
        if case in seen_ids:skipped.append({'caseId':case,'reason':'duplicate_case'});continue
        seen_ids.add(case)
        try:
            url=row['imageUrl']
            # Bound memory for large exports; the downloader enforces URL/size limits.
            if url not in images:
                images.clear();images[url]=download_image(url)
            image=images[url];h,w=image.shape[:2]
            if (w,h)!=(row.get('imageWidth'),row.get('imageHeight')):raise ValueError('Image dimensions changed')
            box=row.get('bbox')
            if not isinstance(box,list) or len(box)!=4 or any(type(v) is not int for v in box):raise ValueError('Invalid bbox')
            x1,y1,x2,y2=box
            if not 0<=x1<x2<=w or not 0<=y1<y2<=h:raise ValueError('Bbox outside source image')
            photo_hash=phash(image)
            if any((photo_hash^other).bit_count()<=4 for other in holdouts):
                skipped.append({'caseId':case,'reason':'heldout_image_or_near_duplicate'});continue
            pixel_sha=hashlib.sha256(str(image.shape).encode()+image.tobytes()).hexdigest()
            key=(pixel_sha,*box,row['partType'])
            if key in seen:
                if seen[key]!=row['material']:raise ValueError('Conflicting labels for the same image region')
                skipped.append({'caseId':case,'reason':'duplicate_image_region'});continue
            seen[key]=row['material']
            crop_name=f'material/train/{row["material"]}/hitl-{case}.jpg';dest=inside(output,crop_name);dest.parent.mkdir(parents=True,exist_ok=True)
            Image.fromarray(image[y1:y2,x1:x2,::-1].copy()).save(dest,quality=95)
            added.append({'crop':crop_name,'material':row['material'],'split':'train','groupId':'hitl-image-'+pixel_sha,
                'cropSha256':digest(dest),
                'caseId':case,'partType':row['partType'],'bbox':box,'source':'admin-reviewed-hitl',
                'sourcePixelSha256':pixel_sha,'sourceUrl':url,'verificationBasis':row['verificationBasis'],
                'userVerificationBasis':row.get('userVerificationBasis',row['verificationBasis']),
                'adminVerificationBasis':row.get('adminVerificationBasis'),'verificationSource':row.get('verificationSource','USER'),
                'trainingConsent':True,'adminReviewed':True,'regionCorrect':True,'modelVersion':row.get('modelVersion'),
                'sourcePhash':format(photo_hash,'016x'),'detectorAnnotationExhaustive':False})
        except ValueError:raise
        except Exception as error:
            # Do not leak source URLs or download credentials in the report.
            skipped.append({'caseId':case,'reason':'image_download_failed','errorType':type(error).__name__})
    manifest+=added
    for split in ('train','val','test'):
        for material in MATERIALS:(output/'material'/split/material).mkdir(parents=True,exist_ok=True)
    counts=Counter(f'material/{r["split"]}/{r["material"]}' for r in manifest)
    result={**report,'counts':dict(counts),'materialManifest':manifest,
        'baseDatasetSha256':digest(base/'dataset-report.json'),'feedbackExportSha256':digest(args.feedback),
        'sourceAnnotationsSha256':hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),
        'hitlReviewedAdded':len(added),'hitlNewCaseIds':[r['caseId'] for r in added],'hitlSkipped':skipped,'hitlPreparationComplete':True,
        'splitPolicy':'Original validation/test unchanged. Reviewed HITL crops are train only; full-image pHash rejects held-out matches (distance <=4). Not a physical product holdout.',
        'annotationScope':'Material classifier crops only; no complete detector labels are fabricated.'}
    (output/'dataset-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return {'added':len(added),'skipped':len(skipped),'output':str(output),'activated':False}


def metrics(logits,targets):
    import torch
    predicted=logits.argmax(1);matrix=torch.zeros((4,4),dtype=torch.int64)
    for truth,guess in zip(targets.cpu(),predicted.cpu()):matrix[int(truth),int(guess)]+=1
    f1=[float(2*matrix[i,i]/(matrix[i,:].sum()+matrix[:,i].sum())) if int(matrix[i,:].sum()+matrix[:,i].sum()) else 0. for i in range(4)]
    return {'accuracy':float((predicted==targets).float().mean()),'macroF1':sum(f1)/4,'f1':dict(zip(MATERIALS,f1)),'confusion':matrix.tolist(),'count':len(targets)}


def train(args):
    report=json.loads((args.data/'dataset-report.json').read_text(encoding='utf8'))
    if report.get('trainingScope')!='bottle-components':raise ValueError('Expected component dataset')
    if not report.get('hitlPreparationComplete') or report.get('hitlReviewedAdded',0)<args.min_new:
        raise ValueError(f'Need at least {args.min_new} new approved, non-held-out HITL crops before a training round')
    if args.min_new<1 or args.epochs<1 or args.threads<1 or not re.fullmatch('[a-z0-9][a-z0-9-]{2,159}',args.version):raise ValueError('Invalid training settings/version')
    if args.output.exists():raise ValueError('Candidate directory exists; never overwrite an earlier model')
    if args.output.resolve().is_relative_to(args.data.resolve()) or args.output.resolve().is_relative_to(args.release.parent.resolve()):
        raise ValueError('Candidate output must be separate from the dataset and source model')
    expected=set()
    for row in report['materialManifest']:
        crop=inside(args.data,row['crop'])
        if digest(crop)!=row.get('cropSha256'):raise ValueError('Dataset crop changed after preparation')
        expected.add(crop.resolve())
    actual={file.resolve() for file in (args.data/'material').rglob('*') if file.is_file()}
    if actual!=expected:raise ValueError('Unexpected training image outside the reviewed manifest')
    new_ids=set(report.get('hitlNewCaseIds',[]))
    added=[r for r in report['materialManifest'] if r.get('source')=='admin-reviewed-hitl' and r.get('caseId') in new_ids]
    if len(added)!=report['hitlReviewedAdded'] or any(r.get('split')!='train' or r.get('adminReviewed') is not True or r.get('trainingConsent') is not True for r in added):
        raise ValueError('Invalid reviewed HITL provenance')
    release=json.loads(args.release.read_text(encoding='utf8'))
    if release.get('trainingScope')!='bottle-components':raise ValueError('Expected component release')
    if args.version==release.get('version'):raise ValueError('Choose a new model version for each HITL round')
    for key in ('materialClassifier','detector'):
        file=inside(args.release.parent,release[key]['file'])
        if digest(file)!=release[key]['sha256']:raise ValueError('Source checkpoint checksum mismatch')
    from .training import load_classifier, material_transform
    import torch
    from torch.utils.data import DataLoader,TensorDataset
    from torchvision.datasets import ImageFolder
    torch.manual_seed(42);torch.set_num_threads(args.threads)
    model,checkpoint=load_classifier(inside(args.release.parent,release['materialClassifier']['file']))
    head=model.fc;model.fc=torch.nn.Identity();model.eval()
    for parameter in model.parameters():parameter.requires_grad=False
    transform=material_transform();features={};labels={}
    for split in ('train','val','test'):
        dataset=ImageFolder(args.data/'material'/split,transform=transform)
        if dataset.classes!=list(MATERIALS) or any(dataset.targets.count(i)<1 for i in range(4)):raise ValueError('All four material classes are required in each split')
        batches=[];targets=[]
        with torch.inference_mode():
            for images,y in DataLoader(dataset,batch_size=16,num_workers=0):batches.append(model(images).clone());targets.append(y)
        features[split]=torch.cat(batches).clone();labels[split]=torch.cat(targets)
    for parameter in head.parameters():parameter.requires_grad=True
    with torch.no_grad():baseline=metrics(head(features['val']),labels['val'])
    best_score=baseline['macroF1'];best_state=copy.deepcopy(head.state_dict());best_epoch=0;epochs=[]
    count=torch.bincount(labels['train'],minlength=4).float();loss_fn=torch.nn.CrossEntropyLoss(weight=len(labels['train'])/(4*count))
    optimizer=torch.optim.AdamW(head.parameters(),lr=.0005,weight_decay=.01)
    loader=DataLoader(TensorDataset(features['train'],labels['train']),batch_size=16,shuffle=True,generator=torch.Generator().manual_seed(42))
    for epoch in range(args.epochs):
        head.train()
        for x,y in loader:optimizer.zero_grad();loss=loss_fn(head(x),y);loss.backward();optimizer.step()
        head.eval()
        with torch.no_grad():score=metrics(head(features['val']),labels['val'])
        if score['macroF1']>best_score:best_score=score['macroF1'];best_state=copy.deepcopy(head.state_dict());best_epoch=epoch+1
        epochs.append({'epoch':epoch+1,'validation':score});print(json.dumps({'epoch':epoch+1,'valMacroF1':score['macroF1']}),flush=True)
    head.load_state_dict(best_state);head.eval()
    with torch.no_grad():validation=metrics(head(features['val']),labels['val']);test=metrics(head(features['test']),labels['test'])
    model.fc=head;args.output.mkdir(parents=True)
    material=args.output/'material-resnet18.pth';detector=args.output/'parts-yolo11n.pt'
    payload={'training_scope':'bottle-components','architecture':'resnet18','class_names':list(MATERIALS),'model_state_dict':model.state_dict(),
        'dataset_sha256':report['sourceAnnotationsSha256'],'epoch':best_epoch-1,'validated':False,'training_mode':'hitl-frozen-backbone',
        'parent_checkpoint_sha256':release['materialClassifier']['sha256'],'hitl_new_samples':report['hitlReviewedAdded']}
    torch.save(payload,material);shutil.copyfile(inside(args.release.parent,release['detector']['file']),detector)
    evaluation={'split':'test','endToEndReviewed':False,'experimental':True,'bestEpoch':best_epoch,'baselineValidation':baseline,
        'validation':validation,'material':test,'epochs':epochs,'materialSha256':digest(material),'detectorSha256':digest(detector),
        'datasetSha256':report['sourceAnnotationsSha256'],'hitlReviewedAdded':report['hitlReviewedAdded'],
        'benchmarkScope':'Unchanged auxiliary crop holdouts. Not independent physical-product or end-to-end bottle accuracy.'}
    (args.output/'evaluation.json').write_text(json.dumps(evaluation,indent=2),encoding='utf8')
    candidate={**release,'version':args.version,'validated':False,'experimental':True,'evaluationReport':'evaluation.json',
        'materialClassifier':{'file':material.name,'sha256':digest(material)},'detector':{'file':detector.name,'sha256':digest(detector)},
        'activeLearning':{'strategy':'uncertainty-priority-with-admin-reviewed-labels','newSamples':report['hitlReviewedAdded'],'activated':False}}
    (args.output/'experimental-release.json').write_text(json.dumps(candidate,indent=2),encoding='utf8')
    return {'candidate':str(args.output),'bestEpoch':best_epoch,'validationMacroF1':validation['macroF1'],'testMacroF1':test['macroF1'],'activated':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    prepare_parser=commands.add_parser('prepare');prepare_parser.add_argument('--feedback',type=Path,required=True)
    prepare_parser.add_argument('--base-data',type=Path,required=True);prepare_parser.add_argument('--source-cache',type=Path)
    prepare_parser.add_argument('--output',type=Path,required=True)
    train_parser=commands.add_parser('train');train_parser.add_argument('--data',type=Path,required=True);train_parser.add_argument('--release',type=Path,required=True)
    train_parser.add_argument('--output',type=Path,required=True);train_parser.add_argument('--version',required=True)
    train_parser.add_argument('--epochs',type=int,default=20);train_parser.add_argument('--min-new',type=int,default=20);train_parser.add_argument('--threads',type=int,default=4)
    args=parser.parse_args();print(json.dumps(prepare(args) if args.command=='prepare' else train(args),ensure_ascii=False))


if __name__=='__main__':main()
