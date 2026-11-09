"""Component contracts, dataset leakage, and real inference coordinate mapping."""
import hashlib
import json
import tempfile
import re
import threading
import urllib.request
import urllib.error
import zipfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch
from PIL import Image

from trashsmart.components import data, inference


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def record(self, name="a.jpg", group="bottle-1", color="green", split="train"):
        file = self.root / "01_user_photos/images" / name
        file.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (100, 200), color).save(file)
        return {"image": file.relative_to(self.root).as_posix(), "groupId": group, "split": split,
                "annotationReviewed": True, "bottles": [{"id": "b1", "bbox": [10, 10, 90, 190], "partsExhaustive": True,
                "components": [{"id": "c1", "partType": "cap", "bbox": [20, 10, 80, 30], "material": "metal",
                                "materialVerified": True, "verificationBasis": "physical sample"},
                               {"id": "c2", "partType": "label", "bbox": [20, 80, 80, 150], "material": "unknown", "materialVerified": False}]}]}

    def test_export_offsets_part_boxes_and_excludes_unverified_material(self):
        data.write_records(self.root, [self.record()])
        output = self.root / "export"
        result = data.export(self.root, output)
        self.assertEqual(result["counts"]["material/train/metal"], 1)
        self.assertFalse(any("unknown" in p.as_posix() for p in output.rglob("*.jpg")))
        lines = next((output / "detector/labels/train").glob("*.txt")).read_text().splitlines()
        values = list(map(float, lines[0].split()))
        self.assertEqual(values[0], 0)
        self.assertAlmostEqual(values[1], .5)
        self.assertAlmostEqual(values[2], 10/180)
        self.assertEqual(len(lines), 2)

    def test_same_product_cannot_cross_splits(self):
        records = [self.record(), self.record("b.jpg", color="blue", split="test")]
        data.write_records(self.root, records)
        with self.assertRaisesRegex(ValueError, "group"):
            data.export(self.root, self.root / "export")

    def test_duplicate_photos_cannot_be_different_groups(self):
        records = [self.record(), self.record("b.jpg", group="other", split="test")]
        data.write_records(self.root, records)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            data.export(self.root, self.root / "export")

    def test_examples_unknown_evidence_and_outside_boxes_are_rejected(self):
        for mutation in (lambda r:r.update(exampleOnly=True),
                         lambda r:r["bottles"][0]["components"][0].update(verificationBasis=""),
                         lambda r:r["bottles"][0]["components"][0].update(bbox=[0, 0, 100, 200])):
            record = self.record()
            mutation(record)
            with self.assertRaises(ValueError):
                data.validate(record, self.root)

    def test_incomplete_annotations_do_not_train_background(self):
        record = self.record()
        record["bottles"][0]["partsExhaustive"] = False
        data.write_records(self.root, [record])
        with self.assertRaisesRegex(ValueError, "partsExhaustive"):
            data.export(self.root, self.root / "export")

    def test_split_is_stable_and_paths_stay_inside_root(self):
        self.assertEqual(data.split_for("same-product"), data.split_for("same-product"))
        with self.assertRaises(ValueError):
            data.contained(self.root, "../outside.jpg")

    def test_partial_material_opt_in_does_not_teach_unlabeled_detector_background(self):
        record=self.record();record['bottles'][0]['partsExhaustive']=False
        data.write_records(self.root,[record])
        output=self.root/'export';result=data.export(self.root,output,include_partial_materials=True)
        self.assertEqual(result['counts'],{'material/train/metal':1})
        self.assertEqual(result['manifest'],[])
        self.assertEqual(len(result['materialManifest']),1)
        self.assertFalse(result['materialManifest'][0]['detectorAnnotationExhaustive'])
        self.assertEqual(result['materialManifest'][0]['partType'],'cap')
        self.assertEqual(list((output/'detector').rglob('*.jpg')),[])
        self.assertEqual(list((output/'detector').rglob('*.txt')),[])
        self.assertEqual(len(list((output/'material').rglob('*.jpg'))),1)

    def test_partial_unreviewed_or_unverified_parts_are_never_exported(self):
        record=self.record();record['bottles'][0]['partsExhaustive']=False
        record['annotationReviewed']=False;data.write_records(self.root,[record])
        with self.assertRaisesRegex(ValueError,'No reviewed'):
            data.export(self.root,self.root/'unreviewed',include_partial_materials=True)
        record['annotationReviewed']=True
        record['bottles'][0]['components'][0]['materialVerified']=False
        data.write_records(self.root,[record])
        with self.assertRaisesRegex(ValueError,'partsExhaustive'):
            data.export(self.root,self.root/'unverified',include_partial_materials=True)

    def test_partial_materials_keep_product_split_leakage_guard(self):
        a=self.record();b=self.record('b.jpg',color='red',split='test')
        for record in (a,b):record['bottles'][0]['partsExhaustive']=False
        data.write_records(self.root,[a,b])
        with self.assertRaisesRegex(ValueError,'group'):
            data.export(self.root,self.root/'export',include_partial_materials=True)

    def test_unreviewed_data_cannot_be_exported(self):
        record = self.record(); record["annotationReviewed"] = False
        data.write_records(self.root, [record])
        with self.assertRaisesRegex(ValueError, "No reviewed"):
            data.export(self.root, self.root / "export")

    def test_training_bundle_excludes_unrelated_secrets_and_runtime_files(self):
        from trashsmart.components.packaging import package_training
        data.write_records(self.root,[self.record()])
        prepared=self.root/'prepared';data.export(self.root,prepared)
        (prepared/'.env').write_text('FIXTURE_ONLY=not-a-real-secret')
        (prepared/'accounts.json').write_text('[]')
        (prepared/'source-acceptance.json').write_text('{"detectorOnly":true}')
        result=package_training(prepared,self.root/'bundle.zip')
        with zipfile.ZipFile(self.root/'bundle.zip') as archive:
            self.assertFalse(any('.env' in n or 'accounts' in n for n in archive.namelist()))
            self.assertIn('dataset/source-acceptance.json',archive.namelist())
            self.assertIn('trashsmart/components/training.py',archive.namelist())
        self.assertEqual(len(result['sha256']),64)


class InferenceTests(unittest.TestCase):
    def test_colab_gpu_index_is_normalized_for_pytorch(self):
        from trashsmart.components.training import torch_device
        self.assertEqual(str(torch_device("0")), "cuda:0")
        self.assertEqual(str(torch_device("cpu")), "cpu")

    def response(self):
        return {"count": 1, "requiresConfirmation": False, "detections": [{"x1": 10, "y1": 20, "x2": 90, "y2": 150}]}

    def test_disabled_and_missing_models_do_not_fabricate_components(self):
        for state in ("NOT_RUN", "MODEL_UNAVAILABLE"):
            with patch.object(inference, "release_config", return_value=(state, None, Path("none"))):
                result = inference.attach_components(np.zeros((200, 100, 3), dtype=np.uint8), self.response())
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["componentCount"], 0)
            self.assertEqual(result["detections"][0]["components"], [])
            self.assertEqual(result["detections"][0]["componentAnalysisStatus"], state)

    def test_engine_maps_crop_coordinates_to_parent_image_and_rejects_weak_material(self):
        engine = object.__new__(inference.ComponentEngine)
        engine.threshold = .7; engine.detector_threshold = .25; engine.image_size = 512
        fake_box = SimpleNamespace(xyxy=torch.tensor([[2.,3.,20.,10.]]), cls=torch.tensor(0), conf=torch.tensor(.9))
        predicted = SimpleNamespace(boxes=[fake_box])
        def detector(crop, **options):
            self.assertFalse(options["agnostic_nms"])
            self.assertEqual(crop.shape[:2], (130,80))
            return [predicted]
        engine.detector = SimpleNamespace(predict=detector)
        engine.transform = lambda img: torch.zeros(3, 224, 224)
        engine.classifier = lambda batch: torch.zeros((1, 4))
        result = engine.predict(np.zeros((200,100,3),dtype=np.uint8), self.response()["detections"])[0][0]
        self.assertEqual([result[k] for k in ("x1","y1","x2","y2")], [12,23,30,30])
        self.assertEqual(result["partType"], "cap")
        self.assertEqual(result["material"], "unknown")
        self.assertTrue(result["needsConfirm"])

    def test_invalid_release_never_becomes_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "release.json"
            file.write_text(json.dumps({"validated": True, "trainingScope": "whole-bottle"}))
            with patch.dict("os.environ", {"PARTS_ENABLED":"true", "PARTS_RELEASE_PATH":str(file)}):
                self.assertEqual(inference.release_config()[0], "MODEL_UNAVAILABLE")

    def test_inference_failure_preserves_bottle_result_and_does_not_claim_completion(self):
        release = {"version":"test"}
        with patch.object(inference, "release_config", return_value=("READY",release,Path("none"))), patch.object(inference,"ComponentEngine",side_effect=ValueError("bad weights")):
            result=inference.attach_components(np.zeros((200,100,3),dtype=np.uint8),self.response())
        self.assertEqual(result["count"],1)
        self.assertEqual(result["componentCount"],0)
        self.assertEqual(result["detections"][0]["componentAnalysisStatus"],"FAILED")

    def test_release_requires_independent_end_to_end_review(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for name in ("det.pt", "mat.pth"):
                (folder / name).write_bytes(b"fixture")
            digest = hashlib.sha256(b"fixture").hexdigest()
            release = {"validated":True,"trainingScope":"bottle-components","version":"test", "evaluationReport":"evaluation.json",
                       "detector":{"file":"det.pt","sha256":digest}, "materialClassifier":{"file":"mat.pth","sha256":digest}}
            (folder / "release.json").write_text(json.dumps(release))
            (folder / "evaluation.json").write_text(json.dumps({"split":"test","endToEndReviewed":False,"detectorSha256":digest,"materialSha256":digest}))
            with patch.dict("os.environ", {"PARTS_ENABLED":"true", "PARTS_RELEASE_PATH":str(folder/'release.json')}):
                self.assertEqual(inference.release_config()[0], "MODEL_UNAVAILABLE")


class AnnotationHttpTests(unittest.TestCase):
    def test_loopback_annotation_roundtrip_and_write_token(self):
        from trashsmart.components.annotate import make_server
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);photo=root/'01_user_photos/images/bottle_001_front.jpg'
            photo.parent.mkdir(parents=True);Image.new('RGB',(100,200),'blue').save(photo)
            server=make_server(root,0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{server.server_port}'
            try:
                with urllib.request.urlopen(base) as response:
                    html=response.read().decode()
                token=re.search("const token='([^']+)'",html).group(1)
                record={'image':'01_user_photos/images/bottle_001_front.jpg','groupId':'bottle_001','annotationReviewed':False,'bottles':[]}
                request=urllib.request.Request(base+'/api/record',data=json.dumps(record).encode(),headers={'Content-Type':'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
                self.assertEqual(error.exception.code,403)
                error.exception.close()
                request.add_header('X-Annotation-Token',token)
                with urllib.request.urlopen(request) as response:
                    self.assertTrue(json.load(response)['saved'])
                self.assertEqual(data.read_records(root)[0]['groupId'],'bottle_001')
                with urllib.request.urlopen(base+'/api/files') as response:
                    self.assertEqual(json.load(response)['files'],[record['image']])
                evil=urllib.request.Request(base+'/api/files',headers={'Host':'untrusted.example'})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(evil)
                self.assertEqual(error.exception.code,403)
                error.exception.close()
            finally:
                server.shutdown();server.server_close();thread.join()


if __name__ == "__main__":
    unittest.main()
