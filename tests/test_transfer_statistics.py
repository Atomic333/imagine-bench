import copy
from pathlib import Path
import sys
import tempfile
import hashlib
import json
import unittest
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'agent'))
from bootstrap import analyze, metrics, validate
from placebo import select_placebo, generate_store


def rows():
    return [dict(arm=arm,task=task,split='S',repeat=repeat,seed=repeat,
                 status='accepted',proposals=1,probes=(1 if task=='t0' else 9)+(int(arm[1]) if repeat==0 else 0),
                 tokens=10,wall_s=1,budget_s=10,invariant_rejections=0,
                 model_id='model',harness_id='harness',prompt_sha256='a'*64,
                 task_sha256=('b' if task=='t0' else 'c')*64,store_sha256=arm[1]*64,
                 source_class='synthetic',public_holdout=True,learner_records=0,endpoint_eligible=True)
            for task in ('t0','t1') for repeat in range(2) for arm in ('A0','A1','A2','A3','A4','A5')]


class StatisticsTests(unittest.TestCase):
    def test_deterministic_paired_cluster(self):
        a = analyze(rows())
        self.assertEqual(a,analyze(list(reversed(rows()))))
        self.assertEqual(a['unit'],'paired task clusters, preserving every repeat')
        self.assertEqual(a['splits']['S']['comparisons']['A3-A0']['probes_per_accepted']['ci95'],[1.5,1.5])
        comparison = a['splits']['S']['comparisons']['A3-A0']['probes_per_accepted']
        self.assertEqual(comparison['baselineMean'],5)
        self.assertEqual(comparison['armMean'],6.5)
        self.assertAlmostEqual(comparison['relative_change'],0.3)
        self.assertGreater(comparison['relative_ci95'][1],comparison['relative_ci95'][0])
        self.assertEqual(a['splits']['S']['arms']['A0']['t0']['status_counts']['accepted'],2)
        self.assertIsNone(a['qualification'])

    def test_missing_duplicate_and_provenance(self):
        source = rows()
        for variant in (source[:-1],source+[source[0]]):
            with self.assertRaises(ValueError):
                validate(variant)
        for key,value in [('model_id','other'),('task_sha256','d'*64),('seed',99),('source_class','trusted')]:
            variant = copy.deepcopy(source)
            variant[0][key] = value
            with self.assertRaises(ValueError):
                validate(variant)

    def test_failures_count_and_undefined(self):
        source = rows()[:2]
        source[0].update(status='timeout',wall_s=4,probes=20)
        m = metrics(source)
        self.assertEqual(m['probes_per_accepted'],source[1]['probes']+20)
        self.assertEqual(m['restricted_wall_to_acceptance_s'],5.5)
        source[1]['status']='failed'
        self.assertIsNone(metrics(source)['probes_per_accepted'])

    def test_negative_usage_rejected(self):
        source = rows()
        source[0]['tokens']=-1
        with self.assertRaises(ValueError):
            validate(source)

    def test_read_only_endpoint_retains_costs(self):
        source = rows()
        for row in source:
            if row['task']=='t0':
                row.update(endpoint_eligible=False,status='passed',proposals=0)
        report = analyze(source)
        self.assertIsNone(report['splits']['S']['arms']['A0']['t0']['probes_per_accepted'])
        self.assertEqual(report['splits']['S']['arms']['A0']['t0']['attempt_tokens'],10)
        self.assertEqual(report['splits']['S']['comparisons']['A3-A0']['probes_per_accepted']['eligible_tasks'],1)

    def test_contamination_and_reused_seeds_rejected(self):
        source = rows()
        source[0]['learner_records']=1
        with self.assertRaises(ValueError):
            analyze(source)
        source = rows()
        for row in source:
            row['seed']=0
        with self.assertRaises(ValueError):
            analyze(source)

    def test_identical_arms_share_task_cluster_draws(self):
        source = rows()
        for row in source:
            if row['arm'] in ('A1','A3'):
                row['probes'] = 4 if row['task']=='t0' else 21
                row['tokens'] = 20 if row['task']=='t0' else 50
        report=analyze(source)
        comparisons=report['splits']['S']['comparisons']
        self.assertEqual(comparisons['A1-A0'],comparisons['A3-A0'])

    def test_arbitrary_full_matrix_is_not_verified_design(self):
        source=[]
        base=rows()[0]
        for split,count in [('S',20),('U',10),('N',5)]:
            for task in range(count):
                for repeat in range(5):
                    for arm in ('A0','A1','A2','A3','A4','A5'):
                        source.append(dict(base,split=split,task=split+str(task),repeat=repeat,seed=repeat,arm=arm,store_sha256=arm[1]*64))
        report=analyze(source)
        self.assertTrue(report['matrix_shape_complete'])
        self.assertFalse(report['task_identity_verified'])
        self.assertIsNone(report['qualification'])


class PlaceboTests(unittest.TestCase):
    def snapshot(self,fixture,text):
        return SimpleNamespace(sha256='e'*64,records=[dict(kind='recipe',id=fixture,fixture=fixture,
                                taskIds=[fixture],text=text,provenance={'origin':'genuine fixture record'})])

    def test_exact_unrelated_selection(self):
        reference = self.snapshot('room','open the door')
        other = self.snapshot('material-zoo','adjust roughness now')
        result = select_placebo(reference,other,unrelated_fixture='material-zoo')
        self.assertEqual(result['recipes'][0]['text'],'adjust roughness now')
        self.assertEqual(result['recipes'][0]['wordCount'],3)
        self.assertFalse(result['admissibleProductionEvidence'])

    def test_length_and_related_rejected(self):
        reference = self.snapshot('room','open the door')
        for candidate,fixture in [(self.snapshot('room','open this gate'),'room'),
                                  (self.snapshot('zoo','too short'),'zoo')]:
            with self.assertRaises(ValueError):
                select_placebo(reference,candidate,unrelated_fixture=fixture)

    def test_generated_store_roundtrip_preserves_proof(self):
        from store import digest, load_store
        def snapshot(root, fixture, text):
            root.mkdir()
            base = dict(taskIds=[fixture],fixture=fixture,sourceClass='fixture',
                        provenance={'sourceClass':'fixture','origin':'synthetic unit test'},
                        experimentOnly=True,dataClass='synthetic')
            evidence = dict(base,id='e',kind='evidence',verifier='unit-test',result='passed',measurement='synthetic assertion')
            ref = {'id':'e','sha256':digest(evidence)}
            acceptance = dict(base,id='a',kind='acceptance',recipeId='r',recipeTextSha256=hashlib.sha256(text.encode()).hexdigest(),decision='accept',evidence=ref)
            recipe = dict(base,id='r',kind='recipe',text=text,evidence=ref,acceptance={'id':'a','sha256':digest(acceptance)})
            raw = json.dumps({'format':'imaginebench-transfer-records/1','records':[recipe,acceptance,evidence]}).encode()
            (root/'recipes.json').write_bytes(raw)
            manifest = dict(format='imaginebench-transfer-store/1',experimentOnly=True,dataClass='synthetic',sourceClass='fixture',
                            provenance=base['provenance'],seenTaskIds=[fixture],files=[dict(path='recipes.json',sha256=hashlib.sha256(raw).hexdigest(),kind='recipes')])
            raw = json.dumps(manifest).encode()
            (root/'manifest.json').write_bytes(raw)
            return load_store(root/'manifest.json',hashlib.sha256(raw).hexdigest(),experiment=True)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root=Path(temp)
            reference = snapshot(root/'reference','room','open the door')
            unrelated = snapshot(root/'unrelated','zoo','set roughness now')
            plan = generate_store(reference,unrelated,root/'generated',unrelated_fixture='zoo')
            generated = load_store(root/'generated'/'manifest.json',plan['generatedStoreSha256'],experiment=True)
            self.assertEqual(generated.records,unrelated.records if list(r['id'] for r in unrelated.records)==sorted(r['id'] for r in unrelated.records) else tuple(sorted(unrelated.records,key=lambda r:r['id'])))


if __name__ == '__main__':
    unittest.main()
