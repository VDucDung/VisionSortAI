import csv,hashlib,json,tempfile,unittest
from pathlib import Path
from PIL import Image
from trashsmart.components.intake import FIELDS,load_intake,check_record_intake
from trashsmart.components.scope_review import apply_review


class ScopeAndDedupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        photo=self.root/'01_user_photos/glass/a.jpg';photo.parent.mkdir(parents=True)
        Image.new('RGB',(100,200),'blue').save(photo);self.image=photo.relative_to(self.root).as_posix()
        self.digest=hashlib.sha256(photo.read_bytes()).hexdigest()
        with (self.root/'01_user_photos/materials.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader()
            w.writerow(dict(zip(FIELDS,['g1','fixture','glass','false','unknown','false','unknown','false','dataset only','image_path=glass/a.jpg'])))
        (self.root/'02_annotations').mkdir()

    def tearDown(self):self.temp.cleanup()

    def review(self,scope='bottle',wrong=None):
        review={'image':self.image,'imageSha256':self.digest,'objectScope':scope,'evidence':'manual fixture visual scope',
                'notes':'scope only','rejectedBottleBoxes':wrong or []}
        (self.root/'02_annotations/scope-reviews.jsonl').write_text(json.dumps(review)+'\n',encoding='utf8')

    def test_scope_review_does_not_verify_material_or_approve_geometry(self):
        self.review(wrong=[{'id':'false','bbox':[1,2,3,4]}])
        record={'image':self.image,'annotationReviewed':False,'bottles':[{'id':'false','bbox':[1,2,3,4]},
                {'id':'real','bbox':[10,20,80,180],'components':[],'partsExhaustive':False}]}
        result=apply_review(self.root,record)
        self.assertEqual(len(result['bottles']),1);self.assertFalse(result['annotationReviewed'])
        self.assertEqual(result['bottles'][0]['components'],[]);self.assertFalse(result['bottles'][0]['partsExhaustive'])
        self.assertEqual(len(record['bottles']),2)

    def test_non_bottle_blocks_export_acceptance(self):
        self.review('not_bottle');intake=load_intake(self.root)
        with self.assertRaisesRegex(ValueError,'outside bottle'):
            check_record_intake({'image':self.image,'bottles':[]},self.root,intake)
        self.assertEqual(intake['notes']['g1']['body_verified'],'false')

    def test_changed_photo_invalidates_old_visual_scope(self):
        self.review('not_bottle');Image.new('RGB',(100,200),'red').save(self.root/self.image)
        intake=load_intake(self.root)
        self.assertFalse(intake['imageIndex'][self.image]['excludeFromBottleTraining'])
        self.assertEqual(len(intake['audit']['scopeReviewErrors']),1)

    def test_exact_duplicate_policy_does_not_delete_or_relabel_source(self):
        other=self.root/'01_user_photos/glass/b.jpg';other.write_bytes((self.root/self.image).read_bytes())
        with (self.root/'01_user_photos/materials.csv').open('a',encoding='utf-8',newline='') as f:
            csv.DictWriter(f,fieldnames=FIELDS).writerow(dict(zip(FIELDS,['g2','fixture','glass','false','unknown','false','unknown','false','dataset only','image_path=glass/b.jpg'])))
        alias=other.relative_to(self.root).as_posix()
        policy={'aliases':[{'image':alias,'canonicalImage':self.image,'sha256':self.digest}]}
        (self.root/'02_annotations/exact-dedup-policy.json').write_text(json.dumps(policy),encoding='utf8')
        intake=load_intake(self.root)
        self.assertTrue(intake['imageIndex'][alias]['excludeFromBottleTraining']);self.assertTrue(other.exists())
        self.assertFalse(intake['imageIndex'][self.image]['excludeFromBottleTraining'])
        self.assertEqual(intake['notes']['g2']['body_verified'],'false')


if __name__=='__main__':unittest.main()
