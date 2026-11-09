"""Grouped folders, CSV image mapping and source split preservation."""
import csv
import json
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image
from trashsmart.components import data
from trashsmart.components.intake import FIELDS, load_intake, audit_intake, check_record_intake
from trashsmart.components.annotate import make_server


class GroupedIntakeTests(unittest.TestCase):
    def test_numbered_views_map_one_csv_row_without_material_confirmation(self):
        images=[self.photo(f'images/bottle_real_001_view0{i}.jpg',color) for i,color in [(1,'blue'),(2,'red'),(3,'green')]]
        self.csv([self.row('bottle_real_001','object_type=bottle; source_split=train; group_identity_verified=false')])
        intake=load_intake(self.root)
        self.assertEqual(intake['audit']['errors'],[])
        self.assertEqual(intake['audit']['matchedPhotoCount'],3)
        for image in images:
            self.assertEqual(intake['imageIndex'][image]['groupId'],'bottle_real_001')
            self.assertEqual(intake['imageIndex'][image]['split'],'train')
        self.assertEqual(intake['notes']['bottle_real_001']['body_verified'],'false')
        self.assertEqual(intake['notes']['bottle_real_001']['cap_material'],'unknown')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def photo(self,relative,color='blue'):
        file=self.root/'01_user_photos'/relative;file.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGB',(100,200),color).save(file)
        return file.relative_to(self.root).as_posix()

    def row(self,group='g1',notes=''):
        return dict(zip(FIELDS,[group,'Photo','glass','false','unknown','false','unknown','false','Dataset material label; not physically verified',notes]))

    def csv(self,rows):
        file=self.root/'01_user_photos/materials.csv';file.parent.mkdir(parents=True,exist_ok=True)
        with file.open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)

    def test_nested_folders_map_image_path_and_normalize_valid_split(self):
        image=self.photo('glass/valid__bottle.jpg')
        self.csv([self.row('glass_001','image_path=glass/valid__bottle.jpg; source_split=valid')])
        intake=load_intake(self.root)
        self.assertEqual(intake['imageIndex'][image]['groupId'],'glass_001')
        self.assertEqual(intake['imageIndex'][image]['split'],'val')
        self.assertEqual(intake['notes']['glass_001']['body_verified'],'false')
        self.assertEqual(intake['notes']['glass_001']['cap_material'],'unknown')
        self.assertEqual(intake['audit']['errors'],[])
        with self.assertRaisesRegex(ValueError,'source train'):
            check_record_intake({'image':image,'split':'train'},self.root,intake)

    def test_needs_review_supported_but_evidence_not_listed(self):
        image=self.photo('needs_review/mixed_materials/a.jpg')
        self.photo('evidence/closeup.jpg')
        self.csv([self.row(notes='image_path=needs_review/mixed_materials/a.jpg')])
        intake=load_intake(self.root)
        self.assertEqual(intake['files'],[image]);self.assertTrue(intake['imageIndex'][image]['needsReview'])

    def test_old_images_folder_and_multiple_views_keep_one_group(self):
        self.photo('images/bottle_001_front.jpg');self.photo('images/bottle_001_back.jpg');self.photo('images/bottle_001_side2.jpg')
        self.csv([self.row('bottle_001')])
        intake=load_intake(self.root)
        self.assertEqual(intake['audit']['matchedPhotoCount'],3)
        self.assertEqual({item['groupId'] for item in intake['imageIndex'].values()},{'bottle_001'})

    def test_duplicate_basenames_require_explicit_path(self):
        self.photo('glass/a.jpg');self.photo('metal/a.jpg')
        self.csv([self.row(notes='image=a.jpg')]);intake=load_intake(self.root)
        self.assertEqual(len(intake['audit']['ambiguousBasenames']),1);self.assertFalse(intake['imageIndex'])

    def test_paths_cannot_escape_or_read_evidence(self):
        self.photo('evidence/a.jpg')
        for path in ('../private.jpg','evidence/a.jpg'):
            self.csv([self.row(notes='image_path='+path)])
            self.assertTrue(load_intake(self.root)['audit']['errors'])

    def test_same_product_cannot_span_source_splits(self):
        first=self.photo('glass/train__a.jpg');self.photo('glass/test__b.jpg')
        self.csv([self.row(notes='image_path=glass/train__a.jpg'),self.row(notes='image_path=glass/test__b.jpg')])
        intake=load_intake(self.root)
        self.assertEqual(len(intake['audit']['groupSplitConflicts']),1)
        with self.assertRaisesRegex(ValueError,'spans source splits'):
            check_record_intake({'image':first,'split':'train'},self.root,intake)

    def test_hash_audit_finds_exact_duplicates_across_splits(self):
        self.photo('glass/train__a.jpg');self.photo('glass/test__b.jpg')
        self.csv([self.row('g1','image_path=glass/train__a.jpg'),self.row('g2','image_path=glass/test__b.jpg')])
        audit=audit_intake(self.root,True)
        self.assertEqual(len(audit['exactDuplicateGroups']),1)
        self.assertEqual(len(audit['crossSplitDuplicateGroups']),1)

    def test_out_of_scope_can_is_blocked_at_export(self):
        image=self.photo('metal/can_001_front.jpg')
        self.csv([self.row('can_001','image_path=metal/can_001_front.jpg; object_type=can; exclude_from_bottle_training=true')])
        record={'image':image,'groupId':'can_001','annotationReviewed':True,'bottles':[]}
        data.write_records(self.root,[record])
        with self.assertRaisesRegex(ValueError,'outside bottle'):
            data.export(self.root,self.root/'export')
        alias=image.replace('/metal/','/metal/../metal/')
        with self.assertRaisesRegex(ValueError,'outside bottle'):
            check_record_intake({'image':alias},self.root,load_intake(self.root))

    def test_bottle_proposal_is_not_an_exhaustive_part_annotation(self):
        image=self.photo('glass/bottle_001_front.jpg')
        self.csv([self.row('bottle_001','image_path=glass/bottle_001_front.jpg')])
        record={'image':image,'source':'user-model-proposal','annotationReviewed':True,'bottles':[{'partsExhaustive':True,'components':[]}]}
        with self.assertRaisesRegex(ValueError,'component boxes'):
            check_record_intake(record,self.root,load_intake(self.root))

    def test_proposal_fallback_is_read_only_and_materials_stay_absent(self):
        from trashsmart.components.proposals import find_proposal
        path=self.root/'02_annotations/user-bottle-proposals-v1.jsonl';path.parent.mkdir(parents=True)
        proposal={'image':'01_user_photos/glass/a.jpg','annotationReviewed':False,'proposalOnly':True,'bottles':[{'components':[]}]}
        path.write_text(json.dumps(proposal)+'\n',encoding='utf8')
        result=find_proposal(self.root,proposal['image'])
        self.assertFalse(result['annotationReviewed']);self.assertEqual(result['bottles'][0]['components'],[])
        self.assertEqual(data.read_records(self.root),[])

    def test_annotation_http_reads_grouped_photo_and_preserves_original_split(self):
        image=self.photo('plastic/test__bottle.jpg')
        self.csv([self.row('plastic_040','image_path=plastic/test__bottle.jpg; source_split=test')])
        server=make_server(self.root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urllib.request.urlopen(base+'/api/files') as response:
                index=json.load(response)
            self.assertIn(image,index['files']);self.assertEqual(index['imageIndex'][image]['groupId'],'plastic_040')
            with urllib.request.urlopen(base+'/image?image='+image) as response:
                self.assertEqual(response.headers.get_content_type(),'image/jpeg')
            with urllib.request.urlopen(base) as response:
                token=re.search("const token='([^']+)'",response.read().decode()).group(1)
            record={'image':image,'groupId':'plastic_040','split':'train','bottles':[],'annotationReviewed':False}
            def request():
                return urllib.request.Request(base+'/api/record',data=json.dumps(record).encode(),headers={'Content-Type':'application/json','X-Annotation-Token':token})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request())
            self.assertEqual(error.exception.code,400);error.exception.close()
            record['split']='test'
            with urllib.request.urlopen(request()) as response:
                self.assertTrue(json.load(response)['saved'])
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__=='__main__':
    unittest.main()
