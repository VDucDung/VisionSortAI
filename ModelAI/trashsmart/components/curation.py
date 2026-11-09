"""Reproducible curation queue and scientific QA sheets; raw photos are unchanged."""
import argparse
import hashlib
import json
from collections import Counter,defaultdict
from pathlib import Path

from .data import contained
from .intake import load_intake


def plan(root, output):
    import cv2
    import numpy as np
    from PIL import Image,ImageOps
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    root, output=Path(root).resolve(),Path(output).resolve()
    if not output.is_relative_to(root/'02_annotations') or output.exists():
        raise ValueError('Choose a new curation directory under 02_annotations')
    intake=load_intake(root)
    audit=json.loads((root/'intake-audit.json').read_text(encoding='utf8'))
    source=root/'02_annotations/user-bottle-proposals-v1.jsonl'
    records=[json.loads(line) for line in source.read_text(encoding='utf8').splitlines() if line.strip()]
    queue=[];groups=defaultdict(list);hashes=[]
    for index,r in enumerate(records):
        file=contained(root,r['image'])
        with Image.open(file) as raw:
            small=np.asarray(ImageOps.exif_transpose(raw).convert('L').resize((32,32)),dtype=np.float32)
        low=cv2.dct(small)[:8,:8].flatten()[1:]
        value=0
        for bit in low>np.median(low):value=(value<<1)|int(bit)
        hashes.append(value)
        meta=intake['imageIndex'][r['image']]
        entry={'id':index+1,'image':r['image'],'groupId':r['groupId'],'sourceSplit':r.get('split'),
               'folder':r['image'].split('/')[1],'bottleBoxCount':len(r['bottles']),
               'confidence':max(b.get('proposalConfidence',0) for b in r['bottles']),
               'fileSha256':hashlib.sha256(file.read_bytes()).hexdigest(),'perceptualHash':f'{value:016x}',
               'scopeReview':'PENDING','componentGeometryReview':'PENDING','materialVerification':'UNVERIFIED',
               'excludeFromBottleTraining':meta['excludeFromBottleTraining']}
        queue.append(entry);groups[entry['folder']].append(entry)
    near=[]
    for i in range(len(queue)):
        for j in range(i):
            distance=(hashes[i]^hashes[j]).bit_count()
            if distance<=4:
                near.append({'a':queue[j]['id'],'b':queue[i]['id'],'distance':distance,
                             'crossSplit':queue[j]['sourceSplit']!=queue[i]['sourceSplit'],
                             'reviewRequired':True,'sameProductConfirmed':False})
    selected=[];seen=set()
    for folder,items in groups.items():
        ordered=sorted(items,key=lambda r:r['confidence'],reverse=True)
        # High, middle and low confidence samples in each material folder.
        positions=[0,1,len(ordered)//2,max(0,len(ordered)//2-1),max(0,len(ordered)-2),len(ordered)-1]
        for position in positions:
            r=ordered[position]
            if r['id'] not in seen:selected.append(r);seen.add(r['id'])
    output.mkdir(parents=True)
    (output/'queue.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in queue),encoding='utf8')
    (output/'similarity-review.json').write_text(json.dumps({'method':'63-bit low-frequency grayscale DCT hash, distance <=4; review candidates only',
        'pairs':near,'crossSplitPairCount':sum(p['crossSplit'] for p in near),'automaticGrouping':False},indent=2),encoding='utf8')
    proposal_by_image={r['image']:r for r in records}
    for start in range(0,len(selected),10):
        page=selected[start:start+10]
        fig,axes=plt.subplots(2,5,figsize=(20,9))
        for axis,entry in zip(axes.flat,page):
            with Image.open(contained(root,entry['image'])) as raw:
                image=ImageOps.exif_transpose(raw).convert('RGB')
            axis.imshow(image)
            for bottle in proposal_by_image[entry['image']]['bottles']:
                x1,y1,x2,y2=bottle['bbox']
                axis.add_patch(Rectangle((x1,y1),x2-x1,y2-y1,fill=False,edgecolor='#16a34a',linewidth=2))
            axis.set_title(f"Q{entry['id']} | {entry['folder']} | {entry['confidence']:.2f}\n{entry['groupId']} | {entry['sourceSplit']}",fontsize=10)
            axis.axis('off')
        for axis in list(axes.flat)[len(page):]:axis.axis('off')
        fig.suptitle('Scope QA: model bottle-box proposals, no verified component materials',fontsize=15)
        fig.tight_layout(rect=[0,0,1,.94],h_pad=4,w_pad=1);fig.savefig(output/f'scope-sheet-{start//10+1:02d}.png',dpi=110);plt.close(fig)
    report={'queueImages':len(queue),'byFolder':dict(Counter(r['folder'] for r in queue)),
            'exactDuplicateGroups':len(audit['exactDuplicateGroups']),'crossSplitExactDuplicateGroups':len(audit['crossSplitDuplicateGroups']),
            'nearDuplicateReviewPairs':len(near),'crossSplitNearReviewPairs':sum(p['crossSplit'] for p in near),
            'manualBatchIds':[r['id'] for r in selected],'sourceProposalSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'csvSha256':hashlib.sha256((root/'01_user_photos/materials.csv').read_bytes()).hexdigest(),
            'autoApprovedScopeLabels':0,'materialLabelsCreated':0,'rawPhotosModified':False}
    (output/'plan.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--data',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();plan(args.data,args.output)
