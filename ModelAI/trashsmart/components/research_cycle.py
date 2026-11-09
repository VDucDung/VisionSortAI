"""Long local research job: train a candidate, evaluate, propose parts; never deploy."""
import csv
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


def write_status(job, **values):
    file = Path(job) / "status.json"
    previous = json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}
    previous.update(values)
    previous.update(updatedAt=datetime.now(timezone.utc).isoformat(), pid=os.getpid(), activated=False)
    temporary = file.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(previous, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(file)


def propose_components(root, source, output, model, image_size=416, progress=None):
    """Use model geometry only. CSV materials never become component labels."""
    import numpy as np
    from PIL import Image, ImageOps
    from . import PARTS
    from .data import contained, validate
    from .intake import load_intake, check_record_intake
    intake = load_intake(root)
    names = [model.names[i] for i in range(len(model.names))]
    if names != list(PARTS):
        raise ValueError("Expected cap/body/label detector")
    records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if output.exists():
        raise ValueError("Part proposals already exist; use a new version")
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary = output.with_suffix(".partial.jsonl")
    count, boxes, errors,excluded = 0, 0, [],[]
    with temporary.open("x", encoding="utf-8") as stream:
        for index, original in enumerate(records):
            record = json.loads(json.dumps(original))
            from .scope_review import apply_review
            record=apply_review(root,record,intake.get('scopeReviews',{}))
            if intake['imageIndex'].get(record['image'],{}).get('excludeFromBottleTraining'):
                excluded.append(record['image']);continue
            if not record['bottles']:
                excluded.append(record['image']);continue
            try:
                check_record_intake(record, root, intake)
                with Image.open(contained(root, record["image"])) as raw:
                    image = np.asarray(ImageOps.exif_transpose(raw).convert("RGB"))[:, :, ::-1].copy()
                for bottle in record["bottles"]:
                    x1,y1,x2,y2 = map(int,bottle["bbox"])
                    crop = image[y1:y2,x1:x2]
                    if not crop.size:
                        raise ValueError("Empty parent crop")
                    predictions = model.predict(crop,device="cpu",imgsz=image_size,conf=.25,iou=.7,
                                                agnostic_nms=False,max_det=30,verbose=False)[0]
                    components = []
                    if predictions.boxes is not None:
                        for box in predictions.boxes:
                            a,b,c,d = (int(v) for v in box.xyxy[0].tolist())
                            bbox = [max(0,a)+x1,max(0,b)+y1,min(x2-x1,c)+x1,min(y2-y1,d)+y1]
                            if bbox[0]>=bbox[2] or bbox[1]>=bbox[3]:
                                continue
                            kind = PARTS[int(box.cls.item())]
                            components.append({"id":f"part-{len(components)+1}","partType":kind,"bbox":bbox,
                                               "proposalConfidence":round(float(box.conf.item()),5),
                                               "material":"unknown","materialVerified":False,"verificationBasis":""})
                    bottle["components"] = components
                    bottle["partsExhaustive"] = False
                    boxes += len(components)
                record.update(annotationReviewed=False,proposalOnly=True,source="user-model-proposal",
                              reviewNote="Bottle and part boxes are model proposals; review every visible part. Materials remain unverified.")
                validate(record, root)
                stream.write(json.dumps(record,ensure_ascii=False)+"\n")
                count += 1
            except (ValueError,OSError,KeyError) as error:
                errors.append({"image":record.get("image"),"error":str(error)})
            if progress and (index+1)%25==0:
                progress(index+1,len(records),boxes)
            stream.flush()
    temporary.replace(output)
    report = {"source":str(source),"output":str(output),"candidateImages":count,"componentBoxes":boxes,
              "readErrors":errors,"scopeExcludedImages":excluded,"annotationReviewed":False,"materialVerifiedCount":0,"masterAnnotationsModified":False}
    output.with_suffix(".report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    return report


def run_cycle(args):
    from . import PARTS
    root, job = args.data.resolve(), args.output.resolve()
    models_root = root / "05_models"
    if job == models_root or not job.is_relative_to(models_root):
        raise ValueError("Research output must be a new child of dataset/05_models")
    if args.epochs < 1 or args.threads < 1:
        raise ValueError("Invalid research epochs/threads")
    if getattr(args,'resume',None) is not None:
        raise ValueError("Research cycles use a new output; use --weights for a previous candidate instead of --resume")
    job.mkdir(parents=True,exist_ok=False)
    started = time.monotonic()
    write_status(job,phase="VALIDATING",maxEpochs=args.epochs,epoch=0,startedAt=datetime.now(timezone.utc).isoformat(),
                 trainingScope="bottle-component-geometry",materialClassifierReady=False)
    try:
        # Restrict this process only; do not change system power policy or other services.
        for key in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS"):
            os.environ[key]=str(args.threads)
        import torch
        import ultralytics.utils as yolo_utils
        import ultralytics.utils.torch_utils as yolo_torch
        from ultralytics import YOLO
        torch.set_num_threads(args.threads)
        yolo_utils.NUM_THREADS=args.threads
        yolo_torch.NUM_THREADS=args.threads
        from .training import train_detector
        prepared=root/'04_prepared/public-detector-v1'
        source=root/'02_annotations/user-bottle-proposals-v1.jsonl'
        output=root/f'02_annotations/user-component-proposals-{job.name}.jsonl'
        if not source.is_file() or not Path(args.weights).is_file():
            raise ValueError("Missing local weights or bottle proposals")
        if output.exists() or output.with_suffix('.partial.jsonl').exists():
            raise ValueError("Existing component proposal version; select a new research job name")
        if not (prepared/'source-acceptance.json').is_file():
            raise ValueError("Missing explicit public geometry source acceptance")
        acceptance=json.loads((prepared/'source-acceptance.json').read_text(encoding='utf-8'))
        if acceptance.get('verifiedMaterialLabels')!=0 or not acceptance.get('detectorOnly'):
            raise ValueError("Expected detector-only public research dataset")
        def progress(trainer):
            metrics={str(k):float(v) if math.isfinite(float(v)) else None for k,v in trainer.metrics.items()}
            write_status(job,phase="TRAINING",epoch=min(args.epochs,int(trainer.epoch)+1),metrics=metrics,
                         elapsedSeconds=round(time.monotonic()-started,1),actualTorchThreads=torch.get_num_threads())
            if (job/'stop.requested').exists():
                trainer.stop=True
        train_args=SimpleNamespace(data=prepared,output=job/'training',device='cpu',epochs=args.epochs,
                                   batch=args.batch,imgsz=args.imgsz,workers=0,threads=args.threads,
                                   weights=str(Path(args.weights).resolve()),resume=None,progress_callback=progress)
        write_status(job,phase="TRAINING",preparedDataset=str(prepared))
        candidate=train_detector(train_args)
        if (job/'stop.requested').exists():
            write_status(job,phase="STOPPED",checkpoint=candidate['candidate'])
            return
        weights=Path(candidate['candidate'])
        write_status(job,phase="EVALUATING",checkpoint=str(weights))
        model=YOLO(str(weights))
        if [model.names[i] for i in range(len(model.names))]!=list(PARTS):
            raise ValueError("Trained checkpoint class order mismatch")
        metrics=model.val(data=str(job/'training/dataset.yaml'),split='test',device='cpu',batch=args.batch,
                          imgsz=args.imgsz,workers=0,agnostic_nms=False,project=str(job/'evaluation'),name='test')
        with (job/'training/detector/results.csv').open(encoding='utf-8',newline='') as stream:
            completed=len(list(csv.DictReader(stream)))
        evaluation={'scope':'part-geometry-only','split':'test','completedEpochs':completed,
                    'metrics':{k:float(v) for k,v in metrics.results_dict.items()},
                    'detectorSha256':hashlib.sha256(weights.read_bytes()).hexdigest(),
                    'endToEndReviewed':False,'materialClassifierReady':False,'activated':False}
        (job/'evaluation/detector-test.json').write_text(json.dumps(evaluation,indent=2),encoding='utf-8')
        write_status(job,phase="PROPOSING_COMPONENTS",completedEpochs=completed,evaluation=evaluation)
        def part_progress(done,total,boxes):
            write_status(job,phase="PROPOSING_COMPONENTS",proposalProgress={'processed':done,'total':total,'boxes':boxes})
        proposals=propose_components(root,source,output,model,args.imgsz,part_progress)
        # Select proposals for the annotation viewer only. Never touch runtime release.json or master labels.
        pointer=root/'02_annotations/proposals.active.json'
        temporary=pointer.with_suffix('.json.tmp')
        temporary.write_text(json.dumps({'file':output.name,'reviewed':False}),encoding='utf-8')
        temporary.replace(pointer)
        write_status(job,phase="READY_FOR_REVIEW",epoch=completed,checkpoint=str(weights),evaluation=evaluation,
                     componentProposals=proposals,elapsedSeconds=round(time.monotonic()-started,1))
    except Exception as error:
        write_status(job,phase="FAILED",errorType=type(error).__name__,error=str(error),elapsedSeconds=round(time.monotonic()-started,1))
        raise
