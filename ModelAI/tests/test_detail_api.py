import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from pydantic import ValidationError
from trashsmart.components.detail_api import ParentRequest,inverse_box,config,analyze,ExperimentalEngine

class DetailedApiTests(unittest.TestCase):
    def test_web_experiment_suppresses_weak_part_proposals(self):
        def initialize(engine, release, path):engine.detector_threshold=release['detectionThreshold']
        with patch('trashsmart.components.detail_api.ComponentEngine.__init__',initialize):
            self.assertEqual(ExperimentalEngine({'detectionThreshold':.25},None).detector_threshold,.5)
            self.assertEqual(ExperimentalEngine({'detectionThreshold':.75},None).detector_threshold,.75)

    def test_rotated_part_coordinates_map_back_to_original_parent(self):
        # Original rectangle [10,20,40,60], original dimensions 100x200.
        self.assertEqual(inverse_box([20,60,60,90],1,100,200),[10,20,40,60])
        self.assertEqual(inverse_box([60,140,90,180],2,100,200),[10,20,40,60])
        self.assertEqual(inverse_box([140,10,180,40],3,100,200),[10,20,40,60])

    def test_invalid_or_duplicate_saved_parents_are_rejected(self):
        parent={'id':9,'x1':10,'y1':20,'x2':90,'y2':180}
        for parents in ([],[parent,parent],[{**parent,'x2':5}]):
            with self.assertRaises(ValidationError):ParentRequest.model_validate({'request_id':7,'parents':parents})

    def test_production_release_cannot_be_loaded_as_an_experiment(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'release.json';path.write_text(json.dumps({'validated':True,'trainingScope':'bottle-components'}))
            with patch.dict('os.environ',{'DETAILS_RELEASE_PATH':str(path)}):
                with self.assertRaisesRegex(ValueError,'experimental'):config()

    def test_missing_candidate_does_not_touch_legacy_models_or_fabricate_parts(self):
        request=ParentRequest.model_validate({'request_id':7,'parents':[{'id':9,'x1':0,'y1':0,'x2':2,'y2':2}]})
        with patch('trashsmart.components.detail_api.config',side_effect=FileNotFoundError()):
            response=analyze(np.zeros((3,3,3),dtype=np.uint8),request)
        self.assertEqual(response.status_code,503)
        self.assertNotIn('parents',json.loads(response.body))

if __name__=='__main__':unittest.main()
