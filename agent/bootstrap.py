"""Offline paired-task transfer analysis; input measurements must be independently trusted.

JSONL or CSV rows use REQUIRED fields below. A failed/timeout row carries all usage,
not just successful usage. wall_s is elapsed until acceptance or censoring; budget_s
is a common, preregistered administrative horizon. Restricted time uses that horizon
for failures, making censoring explicit rather than deleting failed attempts.
"""
import argparse
import csv
import json
import math
import random
from pathlib import Path

ARMS = tuple('A'+str(i) for i in range(6))
REQUIRED = ('arm task split repeat seed status proposals probes tokens wall_s budget_s '
            'invariant_rejections model_id harness_id prompt_sha256 task_sha256 '
            'store_sha256 source_class public_holdout learner_records endpoint_eligible').split()
COUNTS = ('repeat','seed','proposals','probes','tokens','invariant_rejections','learner_records')


def load_rows(path):
    path = Path(path)
    if path.suffix.lower() == '.csv':
        with path.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            for key in COUNTS:
                row[key] = int(row[key])
            for key in ('wall_s', 'budget_s'):
                row[key] = float(row[key])
            if row['public_holdout'] not in ('true','false'):
                raise ValueError('public_holdout must be true or false')
            row['public_holdout'] = row['public_holdout'] == 'true'
            if row['endpoint_eligible'] not in ('true','false'):
                raise ValueError('endpoint_eligible must be true or false')
            row['endpoint_eligible'] = row['endpoint_eligible'] == 'true'
        return rows
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def validate(rows):
    if not rows:
        raise ValueError('empty measurements')
    cells, tasks, global_ids, stores = {}, {}, set(), {}
    for row in rows:
        if set(REQUIRED) - row.keys():
            raise ValueError('missing measurement fields')
        if row['arm'] not in ARMS or row['split'] not in ('S','U','N'):
            raise ValueError('unknown arm or split')
        if row['status'] not in ('accepted','passed','failed','timeout'):
            raise ValueError('status must include explicit failures/timeouts')
        if row['source_class'] not in ('synthetic','trusted') or type(row['public_holdout']) is not bool or type(row['endpoint_eligible']) is not bool:
            raise ValueError('invalid provenance classification')
        for key in COUNTS:
            if type(row[key]) is not int or row[key] < 0:
                raise ValueError('invalid nonnegative integer: '+key)
        if row['learner_records']:
            raise ValueError('learner-class contamination: zero transferred learner records required')
        for key in ('wall_s','budget_s'):
            if isinstance(row[key], bool) or not isinstance(row[key], (int,float)) or not math.isfinite(row[key]) or row[key] < 0:
                raise ValueError('invalid elapsed time')
        if row['budget_s'] <= 0 or row['wall_s'] > row['budget_s']:
            raise ValueError('elapsed exceeds censoring horizon')
        if row['status'] == 'accepted' and row['proposals'] < 1:
            raise ValueError('acceptance requires a proposal')
        if row['status']=='accepted' and not row['endpoint_eligible']:
            raise ValueError('ineligible endpoint cannot accept a proposal')
        if row['status']=='passed' and row['endpoint_eligible']:
            raise ValueError('eligible endpoint must name acceptance explicitly')
        for key in ('prompt_sha256','task_sha256','store_sha256'):
            if not isinstance(row[key],str) or len(row[key]) != 64 or any(c not in '0123456789abcdef' for c in row[key]):
                raise ValueError('invalid digest: '+key)
        if not row['task'] or not row['model_id'] or not row['harness_id']:
            raise ValueError('missing task/model/harness')
        global_ids.add((row['model_id'],row['harness_id'],row['prompt_sha256'],row['source_class']))
        identity = (row['split'],row['task_sha256'],row['budget_s'],row['endpoint_eligible'],row['public_holdout'])
        if row['task'] in tasks and tasks[row['task']] != identity:
            raise ValueError('task provenance or horizon mismatch')
        tasks[row['task']] = identity
        arm = row['arm']
        if arm in stores and stores[arm] != row['store_sha256']:
            raise ValueError('store changed within arm')
        stores[arm] = row['store_sha256']
        cell = (row['task'],row['repeat'],arm)
        if cell in cells:
            raise ValueError('duplicate task/repeat/arm')
        cells[cell] = row
    if len(global_ids) != 1:
        raise ValueError('mismatched model/harness/prompt/provenance')
    repeats = {r['repeat'] for r in rows}
    for task in tasks:
        task_seeds = set()
        for repeat in repeats:
            pair = [cells.get((task,repeat,arm)) for arm in ARMS]
            if any(r is None for r in pair):
                raise ValueError('missing paired cell')
            if len({r['seed'] for r in pair}) != 1:
                raise ValueError('seeds must match across arms')
            if pair[0]['seed'] in task_seeds:
                raise ValueError('seeds must differ across repeats within task')
            task_seeds.add(pair[0]['seed'])
    return tasks, repeats


def metrics(rows):
    accepted = sum(r['status']=='accepted' for r in rows)
    proposals = sum(r['proposals'] for r in rows)
    eligible = all(r['endpoint_eligible'] for r in rows)
    return {'probes_per_accepted':sum(r['probes'] for r in rows)/accepted if accepted else None,
            'restricted_wall_to_acceptance_s':sum(r['wall_s'] if r['status']=='accepted' else r['budget_s'] for r in rows)/len(rows) if eligible else None,
            'acceptance_rate':accepted/len(rows) if eligible else None,
            'task_success_rate':sum(r['status'] in ('accepted','passed') for r in rows)/len(rows),
            'attempt_wall_s':sum(r['wall_s'] for r in rows)/len(rows),
            'attempt_probes':sum(r['probes'] for r in rows)/len(rows),
            'attempt_tokens':sum(r['tokens'] for r in rows)/len(rows),
            'tokens_per_proposal':sum(r['tokens'] for r in rows)/proposals if proposals else None,
            'invariant_rejections':sum(r['invariant_rejections'] for r in rows)/len(rows)}


def analyze(rows, seed=20261109, resamples=10000, equivalence_margins=None):
    tasks, repeats = validate(rows)
    if resamples != 10000:
        raise ValueError('protocol requires 10000 resamples')
    rng = random.Random(seed)
    result = {'format':'imaginebench-transfer-analysis/1','bootstrap_seed':seed,'resamples':resamples,
              'confidence':0.95,'unit':'paired task clusters, preserving every repeat',
              'censoring':'failures/timeouts assigned preregistered budget_s for restricted time; no deletion',
              'qualification':None,'qualification_reason':'split/task membership not verified; external trusted evidence and preregistered equivalence protocol required',
              'task_identity_verified':False,
              'acceptance_unit':'at most one accepted proposal per attempt; accepted status counts exactly one',
              'learner_records':sum(r['learner_records'] for r in rows),'splits':{}}
    for split in ('S','U','N'):
        ids = sorted(t for t,v in tasks.items() if v[0] == split)
        if not ids:
            continue
        groups = {arm:{t:[r for r in rows if r['task']==t and r['arm']==arm] for t in ids} for arm in ARMS}
        per = {arm:{t:metrics(groups[arm][t]) for t in ids} for arm in ARMS}
        # All arms and endpoints with the same task membership share each draw.
        # Repeats remain inside the sampled task cluster throughout.
        sample_sets = {}
        comparisons = {}
        for arm,control in [(a,'A0') for a in ARMS[1:]]+[('A5','A1')]:
            comp = {}
            for key in next(iter(per['A0'].values())):
                selected_ids = [t for t in ids if tasks[t][3]] if key in ('probes_per_accepted','restricted_wall_to_acceptance_s','acceptance_rate') else ids
                values = [(per[control][t][key],per[arm][t][key]) for t in selected_ids]
                if not values or any(a is None or b is None for a,b in values):
                    comp[key] = {'difference':None,'ci95':None,'eligible':False,'reason':'at least one task has undefined endpoint (zero acceptances/proposals)'}
                    continue
                delta = [b-a for a,b in values]
                membership = tuple(selected_ids)
                if membership not in sample_sets:
                    sample_sets[membership] = [[rng.randrange(len(delta)) for _ in delta] for _ in range(resamples)]
                draws, relative_draws = [], []
                for sampled in sample_sets[membership]:
                    draws.append(sum(delta[i] for i in sampled)/len(delta))
                    baseline = sum(values[i][0] for i in sampled)/len(delta)
                    treatment = sum(values[i][1] for i in sampled)/len(delta)
                    relative_draws.append(treatment/baseline-1 if baseline>0 else None)
                draws.sort()
                baseline = sum(a for a,b in values)/len(values)
                treatment = sum(b for a,b in values)/len(values)
                relative_ci = None
                if all(v is not None for v in relative_draws):
                    relative_draws.sort()
                    relative_ci = [relative_draws[249],relative_draws[9749]]
                comp[key] = {'difference':sum(delta)/len(delta),'ci95':[draws[249],draws[9749]],'eligible':True,'eligible_tasks':len(delta),
                             'baselineMean':baseline,'armMean':treatment,'relative_change':treatment/baseline-1 if baseline>0 else None,'relative_ci95':relative_ci}
            comparisons[arm+'-'+control] = comp
        regressions = {arm:[t for t in ids if any(r['status'] in ('accepted','passed') for r in groups['A0'][t]) and not any(r['status'] in ('accepted','passed') for r in groups[arm][t])] for arm in ARMS[1:]}
        details = {a:{t:dict(per[a][t],attempts=len(groups[a][t]),endpoint_eligible=tasks[t][3],public_holdout=tasks[t][4],
                            status_counts={status:sum(r['status']==status for r in groups[a][t]) for status in ('accepted','passed','failed','timeout')},
                            censored_count=sum(r['status'] in ('failed','timeout') and r['endpoint_eligible'] for r in groups[a][t])) for t in ids} for a in ARMS}
        result['splits'][split] = {'tasks':len(ids),'arms':details,'comparisons':comparisons,'regressions':regressions}
    # Qualification deliberately requires a separately preregistered equivalence protocol.
    result['equivalence'] = {'status':'inconclusive','preregistered_margins':equivalence_margins,
                             'reason':'absence of statistical significance does not establish equivalence'}
    result['matrix_shape_complete'] = {s:sum(v[0]==s for v in tasks.values()) for s in ('S','U','N')} == {'S':20,'U':10,'N':5} and repeats == set(range(5))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('measurements', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--seed', type=int, default=20261109)
    args = parser.parse_args()
    report = analyze(load_rows(args.measurements), args.seed)
    text = json.dumps(report, indent=2, allow_nan=False)+'\n'
    if args.output:
        with args.output.open('x',encoding='utf-8') as stream:
            stream.write(text)
    else:
        print(text,end='')


if __name__ == '__main__':
    main()
