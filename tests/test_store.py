"""Frozen store admission tests; all fixtures are synthetic."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent'))
from store import load_store, digest


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.record = dict(id='stale-1', kind='stale-recipe', taskIds=['bench.01'], fixture='fx.synthetic',
                           sourceClass='agent', provenance={'sourceClass':'agent','origin':'synthetic-fixture'},
                           text='Inspect the fixture.', experimentOnly=True, dataClass='synthetic')
        self.manifest = dict(format='imaginebench-transfer-store/1', experimentOnly=True, dataClass='synthetic',
                             sourceClass='agent', provenance={'sourceClass':'agent','origin':'synthetic-fixture'},
                             seenTaskIds=['bench.01'], files=[])

    def write(self, record=None):
        payload = {'format':'imaginebench-transfer-records/1','records':[record or self.record]}
        raw = json.dumps(payload).encode('utf-8')
        (self.root/'recipes.json').write_bytes(raw)
        self.manifest['files'] = [dict(path='recipes.json', sha256=hashlib.sha256(raw).hexdigest(), kind='recipes')]
        raw = json.dumps(self.manifest).encode('utf-8')
        path = self.root/'manifest.json'
        path.write_bytes(raw)
        return path, hashlib.sha256(raw).hexdigest()

    def load(self, record=None):
        return load_store(*self.write(record), experiment=True)

    def test_snapshot_is_immutable_and_stale_is_experiment_only(self):
        snapshot = self.load()
        with self.assertRaises(TypeError):
            snapshot.records[0]['text'] = 'changed'
        with self.assertRaises(ValueError):
            load_store(*self.write())

    def test_tamper_and_wrong_manifest_hash(self):
        path, sha = self.write()
        with self.assertRaises(ValueError): load_store(path, '0'*64, experiment=True)
        (self.root/'recipes.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError): load_store(path, sha, experiment=True)

    def test_traversal_and_windows_paths(self):
        for path in ('../outside.json','C:/outside.json','x\\outside.json','/absolute.json','a/../recipes.json'):
            with self.subTest(path=path):
                self.write()
                self.manifest['files'][0]['path'] = path
                raw = json.dumps(self.manifest).encode('utf-8')
                manifest = self.root/'manifest.json'
                manifest.write_bytes(raw)
                with self.assertRaises(ValueError): load_store(manifest, hashlib.sha256(raw).hexdigest(), experiment=True)

    def test_nested_learner_and_unknown_provenance_refused(self):
        for cls in ('learner','unknown'):
            record = copy.deepcopy(self.record)
            record['provenance']['children'] = [{'sourceClass':cls,'origin':'restricted'}]
            with self.assertRaises(ValueError): self.load(record)

    def test_unsupported_executable_and_non_seen_task_refused(self):
        for changes in ({'script':'print(1)'}, {'kind':'executable'}, {'taskIds':['bench.30']}, {'sourceClass':'learner'}):
            record = dict(self.record, **changes)
            with self.assertRaises(ValueError): self.load(record)

    def test_verified_named_acceptance_and_tampered_reference(self):
        base = {key:value for key,value in self.record.items() if key not in ('id','kind','text')}
        evidence = dict(base, id='e1', kind='evidence', verifier='synthetic-conformance',
                        result='passed', measurement='Synthetic fixture assertion only')
        ref = {'id':'e1', 'sha256':digest(evidence)}
        acceptance = dict(base, id='a1', kind='acceptance', recipeId='r1',
                          recipeTextSha256=hashlib.sha256(b'Inspect.').hexdigest(),
                          decision='accept', evidence=ref)
        recipe = dict(base, id='r1', kind='recipe', text='Inspect.', evidence=ref,
                      acceptance={'id':'a1', 'sha256':digest(acceptance)})
        path, _ = self.write()
        def freeze():
            raw = json.dumps({'format':'imaginebench-transfer-records/1',
                              'records':[recipe, acceptance, evidence]}).encode('utf-8')
            (self.root/'recipes.json').write_bytes(raw)
            self.manifest['files'][0]['sha256'] = hashlib.sha256(raw).hexdigest()
            raw = json.dumps(self.manifest).encode('utf-8')
            path.write_bytes(raw)
            return hashlib.sha256(raw).hexdigest()
        self.assertEqual(len(load_store(path, freeze(), experiment=True).records), 3)
        evidence['measurement'] = 'Changed after acceptance'
        with self.assertRaises(ValueError): load_store(path, freeze(), experiment=True)

    def test_resealed_recipe_proof_cross_class_is_refused(self):
        self.manifest['dataClass'] = 'recorded'
        base = {key:value for key,value in self.record.items() if key not in ('id','kind','text')}
        for classes in (('recorded','synthetic','synthetic'),
                        ('recorded','recorded','synthetic'),
                        ('synthetic','recorded','recorded')):
            with self.subTest(classes=classes):
                evidence = dict(base, id='e1', kind='evidence', dataClass=classes[2],
                                verifier='fixture-check', result='passed', measurement='fixture assertion')
                evidence_ref = {'id':'e1', 'sha256':digest(evidence)}
                acceptance = dict(base, id='a1', kind='acceptance', dataClass=classes[1],
                                  recipeId='r1', recipeTextSha256=hashlib.sha256(b'Inspect.').hexdigest(),
                                  decision='accept', evidence=evidence_ref)
                recipe = dict(base, id='r1', kind='recipe', dataClass=classes[0], text='Inspect.',
                              evidence=evidence_ref, acceptance={'id':'a1','sha256':digest(acceptance)})
                path, _ = self.write()
                raw = json.dumps({'format':'imaginebench-transfer-records/1',
                                  'records':[recipe,acceptance,evidence]}).encode('utf-8')
                (self.root/'recipes.json').write_bytes(raw)
                self.manifest['files'][0]['sha256'] = hashlib.sha256(raw).hexdigest()
                raw = json.dumps(self.manifest).encode('utf-8')
                path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, 'data class'):
                    load_store(path, hashlib.sha256(raw).hexdigest(), experiment=True)

    def test_cli_records_validation_without_claiming_consumption(self):
        path, sha = self.write()
        command = [sys.executable, str(Path(__file__).resolve().parents[1]/'agent'/'run.py'),
                   '--task', 'bench.01', '--store', str(path), '--store-sha256', sha,
                   '--store-experiment', '--scratch', str(self.root)]
        run = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(run.stdout)
        self.assertEqual(report['store']['sha256'], sha)
        self.assertFalse(report['store']['consumedByAdapter'])
        self.assertIsNone(report['store']['transferBenefit'])
        self.assertEqual(report['attempts'], 3)

    def test_orphan_acceptance_without_evidence_is_refused(self):
        base = {key:value for key,value in self.record.items() if key not in ('id','kind','text')}
        acceptance = dict(base, id='a1', kind='acceptance', recipeId='missing',
                          recipeTextSha256='1'*64, decision='accept',
                          evidence={'id':'absent', 'sha256':'0'*64})
        with self.assertRaises(ValueError): self.load(acceptance)

    def test_recorded_snapshot_requires_experiment_and_refuses_learner(self):
        self.manifest['dataClass'] = 'recorded'
        record = dict(self.record, dataClass='recorded')
        snapshot = self.load(record)
        self.assertEqual(snapshot.manifest['dataClass'], 'recorded')
        record['provenance'] = {'sourceClass':'agent','origin':'recorded',
                                'children':[{'sourceClass':'learner','origin':'all-ages-refused'}]}
        with self.assertRaises(ValueError): self.load(record)

    def test_boolean_acceptance_is_not_proof(self):
        record = dict(self.record, kind='recipe', accepted=True)
        with self.assertRaises(ValueError): self.load(record)

    def test_prior_refuses_nested_learner_data(self):
        record = dict(self.record, kind='prior', provenance={'sourceClass':'agent','origin':'synthetic',
                      'children':[{'sourceClass':'learner','origin':'any-age'}]})
        with self.assertRaises(ValueError): self.load(record)

if __name__ == '__main__': unittest.main()
