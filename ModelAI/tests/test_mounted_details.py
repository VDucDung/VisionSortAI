import asyncio
import unittest
from unittest.mock import patch
import httpx
from fastapi import FastAPI
from trashsmart.pipeline import main
from trashsmart.components import detail_api
from trashsmart.pipeline.admission import PredictionAdmission


class MountedDetailsTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_entrypoint_serves_detailed_predictions(self):
        payload={'request_id':49,'image_url':'https://example.com/a.jpg',
                 'parents':[{'id':7,'x1':1,'y1':2,'x2':30,'y2':40}]}
        result={'requestId':49,'status':'COMPLETED','experimental':True,'parents':[],'componentCount':0}
        with patch.object(detail_api,'download_image',return_value='local-test-image'), \
             patch.object(detail_api,'analyze',return_value=result) as analyze:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://test') as client:
                response=await client.post('/details/predict-image-url',json=payload)
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['requestId'],49)
                self.assertEqual(analyze.call_args.args[1].parents[0].id,7)
                self.assertEqual((await client.get('/live')).status_code,200)

    async def test_mounted_body_limit_still_applies_before_parsing(self):
        parent=FastAPI();child=FastAPI()
        child.add_middleware(PredictionAdmission,limit=1,max_body=10)
        @child.post('/predict-image-url')
        async def prediction():raise AssertionError('Oversized request reached handler')
        parent.mount('/details',child)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=parent),base_url='http://test') as client:
            response=await client.post('/details/predict-image-url',content=b'x'*20)
            self.assertEqual(response.status_code,413)

    async def test_mounted_experiment_has_its_own_admission_slot(self):
        parent=FastAPI();child=FastAPI();started=asyncio.Event();release=asyncio.Event()
        child.add_middleware(PredictionAdmission,limit=1,max_body=1024)
        @child.post('/predict-image-url')
        async def prediction():
            started.set();await release.wait();return {'ok':True}
        @parent.get('/live')
        async def live():return {'ok':True}
        parent.mount('/details',child)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=parent),base_url='http://test') as client:
            task=asyncio.create_task(client.post('/details/predict-image-url',json={}))
            try:
                await asyncio.wait_for(started.wait(),2)
                rejected=await client.post('/details/predict-image-url',json={})
                self.assertEqual(rejected.status_code,503)
                self.assertEqual((await client.get('/live')).status_code,200)
            finally:
                release.set();await task
