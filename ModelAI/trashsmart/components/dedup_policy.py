"""Reversible exact-copy exclusions; no file deletion or CSV reassignment."""
import hashlib
import json
from pathlib import Path
from .data import contained


def load_policy(root,index):
    root=Path(root).resolve();file=root/'02_annotations/exact-dedup-policy.json'
    if not file.exists():return {},[]
    document=json.loads(file.read_text(encoding='utf8'))
    aliases,errors={},[];digests={}
    for entry in document.get('aliases',[]):
        try:
            alias=contained(root,entry['image']).relative_to(root).as_posix()
            canonical=contained(root,entry['canonicalImage']).relative_to(root).as_posix()
            if alias not in index or canonical not in index or alias==canonical:
                raise ValueError('Duplicate policy paths do not match current intake')
            for name in (alias,canonical):
                if name not in digests:
                    with (root/name).open('rb') as stream:digests[name]=hashlib.file_digest(stream,'sha256').hexdigest()
                if digests[name]!=entry['sha256']:
                    raise ValueError('Photo changed since duplicate policy; audit it again')
            aliases[alias]=canonical
        except (ValueError,OSError,KeyError) as error:
            errors.append({'image':entry.get('image'),'error':str(error)})
    return aliases,errors
