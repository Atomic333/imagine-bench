"""Select genuine unrelated fixture recipe text with exact whitespace-word lengths.

This emits an experiment plan, not a production-admissible evidence store. Evidence
is never fabricated or transferred to imply that unrelated text solves a target task.
Use separately validated store snapshots; A5 text is outside this selection API.
"""
import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path


def select_placebo(reference, unrelated, *, unrelated_fixture):
    if not unrelated_fixture:
        raise ValueError('explicit unrelated fixture required')
    targets = [r for r in reference.records if r['kind']=='recipe']
    candidates = [r for r in unrelated.records if r['kind']=='recipe']
    if not targets:
        raise ValueError('reference has no recipes')
    fixtures = {r['fixture'] for r in targets}
    if unrelated_fixture in fixtures:
        raise ValueError('placebo must use an unrelated fixture')
    used, pairs = set(), []
    target_tasks = {t for r in targets for t in r['taskIds']}
    for target in sorted(targets,key=lambda r:r['id']):
        count = len(target['text'].split())
        matches = [r for r in candidates if r['id'] not in used and r['fixture']==unrelated_fixture
                   and not target_tasks.intersection(r['taskIds']) and r.get('provenance')
                   and len(r['text'].split())==count]
        if not matches:
            raise ValueError('no genuine unrelated recipe with exact word length '+str(count))
        chosen = sorted(matches,key=lambda r:r['id'])[0]
        used.add(chosen['id'])
        pairs.append({'referenceRecipeId':target['id'],'sourceRecipeId':chosen['id'],
                      'sourceFixture':chosen['fixture'],'text':chosen['text'],'wordCount':count,
                      'textSha256':hashlib.sha256(chosen['text'].encode('utf-8')).hexdigest()})
    return {'format':'imaginebench-placebo-selection/1','experimentOnly':True,'dataClass':getattr(unrelated,'manifest',{}).get('dataClass','synthetic'),
            'admissibleProductionEvidence':False,'arm':'A4','lengthUnit':'whitespace-delimited words (str.split)',
            'referenceStoreSha256':reference.sha256,'sourceStoreSha256':unrelated.sha256,
            'unrelatedFixture':unrelated_fixture,'recipeCount':len(pairs),'recipes':pairs}


def thaw(value):
    if isinstance(value, Mapping):
        return {key:thaw(item) for key,item in value.items()}
    if isinstance(value, (tuple,list)):
        return [thaw(item) for item in value]
    return value


def generate_store(reference, unrelated, output, *, unrelated_fixture):
    """Copy original selected records and their proofs unchanged into a fresh store."""
    from store import load_store
    plan = select_placebo(reference,unrelated,unrelated_fixture=unrelated_fixture)
    by_id = {r['id']:r for r in unrelated.records}
    wanted = set()
    for selection in plan['recipes']:
        recipe = by_id[selection['sourceRecipeId']]
        wanted.update((recipe['id'],recipe['acceptance']['id'],recipe['evidence']['id']))
    records = [thaw(by_id[key]) for key in sorted(wanted)]
    manifest = thaw(unrelated.manifest)
    manifest['seenTaskIds'] = sorted({t for r in records for t in r['taskIds']})
    payload = (json.dumps({'format':'imaginebench-transfer-records/1','records':records},ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
    manifest['files'] = [{'path':'recipes.json','sha256':hashlib.sha256(payload).hexdigest(),'kind':'recipes'}]
    raw = (json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
    output = Path(output)
    output.mkdir(exist_ok=False)
    (output/'recipes.json').write_bytes(payload)
    (output/'manifest.json').write_bytes(raw)
    plan['generatedStoreSha256'] = hashlib.sha256(raw).hexdigest()
    load_store(output/'manifest.json',plan['generatedStoreSha256'],experiment=True)
    (output/'selection.json').write_text(json.dumps(plan,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return plan


def main():
    from store import load_store
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--reference-sha256',required=True)
    parser.add_argument('--unrelated',type=Path,required=True)
    parser.add_argument('--unrelated-sha256',required=True)
    parser.add_argument('--unrelated-fixture',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    reference = load_store(args.reference,args.reference_sha256,experiment=True)
    unrelated = load_store(args.unrelated,args.unrelated_sha256,experiment=True)
    report = generate_store(reference,unrelated,args.output,unrelated_fixture=args.unrelated_fixture)
    print(report['generatedStoreSha256'])


if __name__ == '__main__':
    main()
