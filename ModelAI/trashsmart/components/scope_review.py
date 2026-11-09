"""Manual visual object-scope decisions, separate from material verification."""
import hashlib
import json
from pathlib import Path
from .data import contained


def load_reviews(root):
    root=Path(root).resolve()
    file=root/'02_annotations/scope-reviews.jsonl'
    reviews,errors={},[]
    if not file.exists():return reviews,errors
    for line,text in enumerate(file.read_text(encoding='utf8').splitlines(),1):
        if not text.strip():continue
        try:
            review=json.loads(text)
            image=contained(root,review['image'])
            if not image.is_relative_to(root/'01_user_photos') or review['objectScope'] not in {'bottle','not_bottle','uncertain'}:
                raise ValueError('Invalid scope review')
            if not review.get('evidence') or len(review.get('imageSha256',''))!=64:
                raise ValueError('Scope review requires image checksum and visual evidence')
            with image.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            if digest!=review['imageSha256']:
                raise ValueError('Photo changed since scope review; review it again')
            reviews[image.relative_to(root).as_posix()]=review
        except (ValueError,OSError,KeyError,TypeError) as error:
            errors.append({'line':line,'error':str(error)})
    return reviews,errors


def rejected_box(bottle,review):
    return any(bottle.get('id')==box.get('id') and bottle.get('bbox')==box.get('bbox') for box in review.get('rejectedBottleBoxes',[]))


def apply_review(root,record,reviews=None):
    """Filter only explicitly reviewed false boxes. Do not approve remaining geometry."""
    if reviews is None:reviews,_=load_reviews(root)
    image=contained(root,record['image']).relative_to(Path(root).resolve()).as_posix()
    review=reviews.get(image)
    if not review:return record
    result=json.loads(json.dumps(record))
    result['objectScopeReview']=review['objectScope']
    result['scopeReviewNote']=review['notes']
    result['bottles']=[] if review['objectScope']=='not_bottle' else [b for b in result['bottles'] if not rejected_box(b,review)]
    return result
