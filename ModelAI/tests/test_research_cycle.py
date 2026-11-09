import csv,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from PIL import Image
from trashsmart.components.research_cycle import propose_components,run_cycle
from trashsmart.components.intake import FIELDS


class ResearchCycleTests(unittest.TestCase):
    def test_scope_filtered_empty_parent_is_excluded_without_fake_read_error(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.jsonl';output=root/'parts.jsonl'
            image='01_user_photos/glass/empty.jpg'
            source.write_text(json.dumps({'image':image,'bottles':[]})+'\n',encoding='utf8')
            report=propose_components(root,source,output,SimpleNamespace(names={0:'cap',1:'body',2:'label'}))
            self.assertEqual(report['candidateImages'],0)
            self.assertEqual(report['scopeExcludedImages'],[image])
            self.assertEqual(report['readErrors'],[])
            self.assertEqual(output.read_text(),'')

    def test_part_proposals_map_coordinates_but_never_promote_csv_materials(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);photo=root/'01_user_photos/glass/bottle_001_front.jpg'
            photo.parent.mkdir(parents=True);Image.new('RGB',(100,200),'blue').save(photo)
            row=dict(zip(FIELDS,['bottle_001','Fixture','glass','true','metal','true','paper','true','Fixture user confirmation','image_path=glass/bottle_001_front.jpg']))
            with (root/'01_user_photos/materials.csv').open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerow(row)
            record={'image':photo.relative_to(root).as_posix(),'groupId':'bottle_001','split':'train',
                    'annotationReviewed':False,'bottles':[{'id':'b1','bbox':[10,20,90,180],'partsExhaustive':False,'components':[]}]}
            source=root/'02_annotations/bottles.jsonl';source.parent.mkdir();source.write_text(json.dumps(record)+'\n',encoding='utf8')
            box=SimpleNamespace(xyxy=np.array([[5,1,30,15]]),cls=np.array(0),conf=np.array(.9))
            class Model:
                names={0:'cap',1:'body',2:'label'}
                def predict(self,crop,**options):
                    self.options=options
                    return [SimpleNamespace(boxes=[box])]
            model=Model();output=root/'02_annotations/parts.jsonl'
            report=propose_components(root,source,output,model)
            part=json.loads(output.read_text())['bottles'][0]['components'][0]
            self.assertEqual(part['bbox'],[15,21,40,35]);self.assertEqual(part['partType'],'cap')
            self.assertEqual(part['material'],'unknown');self.assertFalse(part['materialVerified'])
            self.assertEqual(report['materialVerifiedCount'],0);self.assertFalse(model.options['agnostic_nms'])
            self.assertFalse((root/'02_annotations/annotations.jsonl').exists())

    def test_whole_material_detector_is_rejected_for_part_proposals(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'cap/body/label'):
                propose_components(Path(folder),Path(folder)/'unused',Path(folder)/'output',SimpleNamespace(names={0:'glass'}))

    def test_job_cannot_write_outside_models_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            args=SimpleNamespace(data=root,output=root/'wrong',epochs=40,threads=4)
            with self.assertRaisesRegex(ValueError,'05_models'):
                run_cycle(args)
            self.assertFalse((root/'wrong').exists())


if __name__=='__main__':unittest.main()
