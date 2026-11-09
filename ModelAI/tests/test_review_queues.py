import json,tempfile,unittest
from pathlib import Path
from PIL import Image
from trashsmart.components.annotate import review_queues


class ReviewQueueTests(unittest.TestCase):
    def test_queue_only_selects_existing_photos_and_ignores_label_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);photo=root/'01_user_photos/plastic/a.jpg'
            photo.parent.mkdir(parents=True);Image.new('RGB',(20,20)).save(photo)
            queue=root/'02_annotations/review-queues/new.json';queue.parent.mkdir(parents=True)
            image=photo.relative_to(root).as_posix()
            queue.write_text(json.dumps({'title':'Candidate review','files':[image,image],
                                         'annotationReviewed':True,'materialVerified':True,'groupId':'other'}),encoding='utf8')
            queues,errors=review_queues(root,[image])
            self.assertEqual(errors,[])
            self.assertEqual(queues,[{'id':'new','title':'Candidate review','files':[image]}])

    def test_missing_paths_traversal_and_evidence_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'02_annotations/review-queues';folder.mkdir(parents=True)
            for index,image in enumerate(['../outside.jpg','01_user_photos/evidence/private.jpg','01_user_photos/images/missing.jpg']):
                (folder/f'{index}.json').write_text(json.dumps({'title':'Invalid','files':[image]}),encoding='utf8')
            queues,errors=review_queues(root,[])
            self.assertEqual(queues,[]);self.assertEqual(len(errors),3)

    def test_malformed_queue_does_not_hide_good_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'02_annotations/review-queues';folder.mkdir(parents=True)
            (folder/'bad.json').write_text('{broken',encoding='utf8')
            (folder/'empty.json').write_text(json.dumps({'title':'No candidates','files':[]}),encoding='utf8')
            queues,errors=review_queues(root,[])
            self.assertEqual(len(errors),1);self.assertEqual(queues,[{'id':'empty','title':'No candidates','files':[]}])


if __name__=='__main__':unittest.main()
