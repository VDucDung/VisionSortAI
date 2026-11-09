"""FE/BE/AI wire contract checks; weights and external uploads are mocked."""
import unittest
from unittest.mock import patch
try:
    from fastapi.testclient import TestClient
    from trashsmart.pipeline import main as api
except ModuleNotFoundError as error:
    raise unittest.SkipTest(str(error))

class IntegrationContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)

    def test_metadata_is_lightweight_and_matches_runtime(self):
        with patch.object(api, "get_models", side_effect=AssertionError("metadata must not load weights")):
            response = self.client.get("/metadata")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["apiVersion"], "1")
        self.assertEqual(data["materialCodes"], api.CLASS_NAMES)
        self.assertEqual(set(data["materialCodes"]), {"glass", "metal", "paper", "plastic"})
        self.assertEqual(data["confirmationThreshold"], api.RESNET_CONF_THRESHOLD)
        self.assertEqual(data["confidenceRange"], [0, 1])

    def test_invalid_request_id_is_rejected(self):
        response = self.client.post("/predict-image-url", json={"request_id": -1, "image_url": "https://example.com/a.jpg"})
        self.assertEqual(response.status_code, 422)
