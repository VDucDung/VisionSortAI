import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import cv2,numpy as np
from trashsmart.components import hitl


class HitlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.base=self.root/'base';self.base.mkdir();self.rng=np.random.default_rng(42)
        self.manifest=[]
        for i,split in enumerate(('train','val','test')):
            for j,material in enumerate(('glass','metal','paper','plastic')):
                image=self.rng.integers(0,256,(40,40,3),dtype=np.uint8);source=f'sources/{split}-{material}.png'
                file=self.base/source;file.parent.mkdir(exist_ok=True);cv2.imwrite(str(file),image)
                crop=f'material/{split}/{material}/base.png';dest=self.base/crop;dest.parent.mkdir(parents=True);cv2.imwrite(str(dest),image[:20,:20])
                self.manifest.append({'crop':crop,'split':split,'material':material,'sourceImage':source,'sourceSha256':hitl.digest(file)})
        report={'trainingScope':'bottle-components','counts':{},'materialManifest':self.manifest,'sourceAnnotationsSha256':'old'}
        (self.base/'dataset-report.json').write_text(json.dumps(report))
        self.feedback=self.root/'feedback.json';self.output=self.root/'prepared';self.image=self.rng.integers(0,256,(50,50,3),dtype=np.uint8)
        self.row={'schemaVersion':1,'caseId':'a'*64,'adminReviewed':True,'trainingConsent':True,'regionCorrect':True,'verificationBasis':'PHYSICAL_CHECK',
            'split':'train','partType':'label','material':'plastic','imageUrl':'https://example.com/bottle.jpg','imageWidth':50,'imageHeight':50,'bbox':[5,5,40,40]}
        self.args=SimpleNamespace(base_data=self.base,feedback=self.feedback,source_cache=None,output=self.output)
    def prepare(self,rows):
        self.feedback.write_text(json.dumps({'schemaVersion':1,'records':rows}))
        with patch.object(hitl,'download_image',return_value=self.image):return hitl.prepare(self.args)
    def test_only_verified_approved_opt_in_labels_become_train_crops_and_holdouts_are_unchanged(self):
        rows=[self.row,{**self.row,'caseId':'b'*64,'adminReviewed':False},{**self.row,'caseId':'c'*64,'material':'unknown'},
            {**self.row,'caseId':'d'*64,'trainingConsent':False},{**self.row,'caseId':'e'*64,'verificationBasis':'VISUAL_ONLY'}]
        hashes={r['crop']:hitl.digest(self.base/r['crop']) for r in self.manifest}
        result=self.prepare(rows);self.assertEqual(result['added'],1);self.assertEqual(result['skipped'],4)
        report=json.loads((self.output/'dataset-report.json').read_text());self.assertEqual(report['materialManifest'][-1]['split'],'train')
        for name,sha in hashes.items():self.assertEqual(hitl.digest(self.output/name),sha);self.assertEqual(hitl.digest(self.base/name),sha)
    def test_exact_and_near_heldout_photos_are_not_allowed_in_the_training_round(self):
        self.image=cv2.imread(str(self.base/'sources/val-glass.png'))
        self.row.update(imageWidth=40,imageHeight=40,bbox=[0,0,20,20]);result=self.prepare([self.row]);self.assertEqual(result['added'],0)
        self.assertEqual(json.loads((self.output/'dataset-report.json').read_text())['hitlSkipped'][0]['reason'],'heldout_image_or_near_duplicate')
    def test_duplicate_cases_and_duplicate_regions_do_not_inflate_label_count(self):
        result=self.prepare([self.row,self.row,{**self.row,'caseId':'b'*64}]);self.assertEqual(result['added'],1);self.assertEqual(result['skipped'],2)
    def test_conflicting_human_materials_for_one_region_abort_preparation(self):
        with self.assertRaisesRegex(ValueError,'Conflicting'):self.prepare([self.row,{**self.row,'caseId':'b'*64,'material':'paper'}])
        self.assertFalse((self.output/'dataset-report.json').exists())
    def test_tampered_box_or_changed_source_dimensions_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'dimensions'):self.prepare([{**self.row,'imageWidth':51}])
    def test_existing_round_is_never_overwritten(self):
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError,'exists'):self.prepare([self.row])
    def test_admin_visual_review_can_be_used_without_claiming_physical_verification(self):
        row={**self.row,'verificationBasis':'ADMIN_VISUAL_REVIEW','userVerificationBasis':'VISUAL_ONLY',
             'adminVerificationBasis':'VISUAL_REVIEW','verificationSource':'ADMIN'}
        result=self.prepare([row]);self.assertEqual(result['added'],1)
        added=json.loads((self.output/'dataset-report.json').read_text())['materialManifest'][-1]
        self.assertEqual(added['verificationBasis'],'ADMIN_VISUAL_REVIEW');self.assertEqual(added['userVerificationBasis'],'VISUAL_ONLY')
        self.assertEqual(added['verificationSource'],'ADMIN')
    def test_unreviewed_visual_only_feedback_is_still_excluded(self):
        rows=[{**self.row,'verificationBasis':'VISUAL_ONLY'},
              {**self.row,'caseId':'b'*64,'verificationBasis':'ADMIN_VISUAL_REVIEW'}]
        self.assertEqual(self.prepare(rows)['added'],0)
    def test_later_round_preserves_old_labels_and_counts_only_new_approved_cases(self):
        self.prepare([self.row]);next_output=self.root/'round-two';next_image=self.rng.integers(0,256,(50,50,3),dtype=np.uint8)
        self.feedback.write_text(json.dumps({'schemaVersion':1,'records':[self.row,{**self.row,'caseId':'b'*64}]}))
        args=SimpleNamespace(base_data=self.output,feedback=self.feedback,source_cache=None,output=next_output)
        with patch.object(hitl,'download_image',return_value=next_image):result=hitl.prepare(args)
        self.assertEqual(result['added'],1);report=json.loads((next_output/'dataset-report.json').read_text())
        self.assertEqual(report['hitlNewCaseIds'],['b'*64]);self.assertEqual(len(report['materialManifest']),14)
    def test_training_waits_for_enough_reviewed_labels(self):
        self.prepare([self.row]);args=SimpleNamespace(data=self.output,min_new=20)
        with self.assertRaisesRegex(ValueError,'at least 20'):hitl.train(args)
    def test_small_cpu_training_creates_an_isolated_candidate_and_never_activates_it(self):
        import torch
        from torchvision.transforms import Compose,Resize,ToTensor
        self.prepare([self.row]);release_dir=self.root/'source-release';release_dir.mkdir()
        material=release_dir/'material.pth';detector=release_dir/'detector.pt';material.write_bytes(b'preserved-parent');detector.write_bytes(b'preserved-detector')
        release={'version':'source-v1','trainingScope':'bottle-components','experimental':True,'validated':False,
            'materialClassifier':{'file':material.name,'sha256':hitl.digest(material)},'detector':{'file':detector.name,'sha256':hitl.digest(detector)}}
        release_file=release_dir/'experimental-release.json';release_file.write_text(json.dumps(release));old_hash=hitl.digest(material)
        class TinyBackbone(torch.nn.Module):
            def __init__(self):super().__init__();self.fc=torch.nn.Linear(3,4)
            def forward(self,x):return self.fc(x.mean((2,3)))
        args=SimpleNamespace(data=self.output,release=release_file,output=self.root/'candidate',version='hitl-test-v1',min_new=1,epochs=2,threads=1)
        with patch('trashsmart.components.training.load_classifier',return_value=(TinyBackbone(),{})),patch('trashsmart.components.training.material_transform',return_value=Compose([Resize((32,32)),ToTensor()])):
            result=hitl.train(args)
        self.assertFalse(result['activated']);self.assertEqual(hitl.digest(material),old_hash)
        new_release=json.loads((args.output/'experimental-release.json').read_text());self.assertFalse(new_release['validated']);self.assertFalse(new_release['activeLearning']['activated'])
        self.assertEqual(new_release['version'],'hitl-test-v1');self.assertEqual(new_release['materialClassifier']['sha256'],hitl.digest(args.output/'material-resnet18.pth'))
        evaluation=json.loads((args.output/'evaluation.json').read_text());self.assertEqual(evaluation['material']['count'],4);self.assertFalse(evaluation['endToEndReviewed'])
        with self.assertRaisesRegex(ValueError,'exists'):hitl.train(args)
