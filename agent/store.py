"""Content-addressed, read-only experiment transfer snapshots.

Manifest v1 admits synthetic or recorded experiment data, never production
recipes or learner data. Hashes prove byte integrity, not external authenticity
or real-world success. Recorded authority must be authenticated independently.
No imported text is executed and no model is trained by this module.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType

ALLOWED_CLASSES = frozenset({'fixture', 'engine', 'artist', 'agent'})
SHA = re.compile(r'[0-9a-f]{64}\Z')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _keys(value, required, optional=()):
    _require(isinstance(value, dict), 'expected JSON object')
    _require(set(required) <= value.keys() and value.keys() <= set(required) | set(optional),
             'missing or unsupported fields')


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, 'duplicate JSON field')
            result[key] = value
        return result
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('invalid UTF-8 JSON') from error


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _provenance(value):
    _keys(value, ('sourceClass', 'origin'), ('children',))
    _require(isinstance(value['sourceClass'], str) and value['sourceClass'] in ALLOWED_CLASSES, 'learner or unknown provenance refused at every age')
    _require(_text(value['origin']), 'named origin required')
    children = value.get('children', [])
    _require(isinstance(children, list), 'invalid provenance children')
    for child in children:
        _provenance(child)


def _scope(value):
    _require(isinstance(value['sourceClass'], str) and value['sourceClass'] in ALLOWED_CLASSES, 'learner or unknown source class refused')
    _provenance(value['provenance'])
    _require(value['sourceClass'] == value['provenance']['sourceClass'], 'source class mismatch')
    _require(value['experimentOnly'] is True and value['dataClass'] in ('synthetic', 'recorded'),
             'v1 supports labeled experiment data only; no production admission')


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class StoreSnapshot:
    sha256: str
    manifest: object
    records: tuple


def load_store(manifest_path, expected_sha256, *, experiment=False):
    """Read and validate bytes once; return an immutable in-memory snapshot.

    Caller supplies the frozen manifest SHA independently. experiment=True is an
    explicit controlled read-only opt-in, including evidence-stripped A5 records.
    """
    _require(experiment is True, 'snapshot requires explicit experiment opt-in')
    _require(isinstance(expected_sha256, str) and SHA.fullmatch(expected_sha256), 'invalid manifest SHA256')
    path = Path(manifest_path)
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == expected_sha256, 'manifest SHA256 mismatch')
    manifest = _json(raw)
    _keys(manifest, ('format', 'experimentOnly', 'dataClass', 'sourceClass', 'provenance', 'seenTaskIds', 'files'))
    _require(manifest['format'] == 'imaginebench-transfer-store/1', 'unsupported store format')
    _scope(manifest)
    seen = manifest['seenTaskIds']
    _require(isinstance(seen, list) and all(_text(task) for task in seen) and len(seen) == len(set(seen)), 'invalid seen task IDs')
    _require(isinstance(manifest['files'], list), 'invalid files')
    root = path.resolve().parent
    records, paths = [], set()
    for entry in manifest['files']:
        _keys(entry, ('path', 'sha256', 'kind'))
        name = entry['path']
        _require(isinstance(name, str) and name and '\\' not in name and ':' not in name, 'unsafe store path')
        relative = PurePosixPath(name)
        _require(not relative.is_absolute() and all(part not in ('', '.', '..') for part in name.split('/')),
                 'unsafe store path')
        _require(name not in paths and relative.suffix == '.json', 'duplicate or unsupported store path')
        paths.add(name)
        target = root.joinpath(*relative.parts)
        _require(target.resolve().is_relative_to(root), 'store path escapes snapshot')
        _require(not any(parent.is_symlink() for parent in [target, *target.parents] if parent != root.parent), 'symlink store path refused')
        _require(entry['kind'] in ('recipes', 'prior') and isinstance(entry['sha256'], str) and SHA.fullmatch(entry['sha256']), 'invalid file descriptor')
        content = target.read_bytes()
        _require(hashlib.sha256(content).hexdigest() == entry['sha256'], 'store input SHA256 mismatch')
        payload = _json(content)
        _keys(payload, ('format', 'records'))
        _require(payload['format'] == 'imaginebench-transfer-records/1' and isinstance(payload['records'], list), 'unsupported records format')
        for record in payload['records']:
            _validate_record(record, set(seen))
            _require(manifest['dataClass'] == 'recorded' or record['dataClass'] == 'synthetic',
                     'synthetic manifest cannot conceal recorded inputs')
            _require((record['kind'] == 'prior') == (entry['kind'] == 'prior'), 'record/file kind mismatch')
            records.append(record)
    by_id = {record['id']: record for record in records}
    _require(len(by_id) == len(records), 'duplicate record ID')
    for record in records:
        if record['kind'] == 'acceptance':
            _reference(record['evidence'], 'evidence', by_id)
            _require(record['recipeId'] in by_id and by_id[record['recipeId']]['kind'] == 'recipe',
                     'orphan acceptance record refused')
    for recipe in records:
        if recipe['kind'] != 'recipe':
            continue
        acceptance = _reference(recipe['acceptance'], 'acceptance', by_id)
        evidence = _reference(recipe['evidence'], 'evidence', by_id)
        _require(recipe['dataClass'] == acceptance['dataClass'] == evidence['dataClass'],
                 'recipe/acceptance/evidence data class mismatch')
        _require(acceptance['recipeId'] == recipe['id'] and
                 acceptance['recipeTextSha256'] == hashlib.sha256(recipe['text'].encode('utf-8')).hexdigest(), 'acceptance content binding mismatch')
        _require(acceptance['evidence'] == recipe['evidence'], 'acceptance evidence binding mismatch')
        _require(acceptance['taskIds'] == recipe['taskIds'] == evidence['taskIds'] and
                 acceptance['fixture'] == recipe['fixture'] == evidence['fixture'], 'proof scope mismatch')
    return StoreSnapshot(expected_sha256, _freeze(manifest), tuple(_freeze(r) for r in records))


def _reference(ref, kind, records):
    _keys(ref, ('id', 'sha256'))
    _require(_text(ref['id']) and isinstance(ref['sha256'], str) and SHA.fullmatch(ref['sha256']), 'invalid reference')
    record = records.get(ref['id'])
    _require(record is not None and record['kind'] == kind and digest(record) == ref['sha256'], 'unresolved or changed evidence reference')
    return record


def _validate_record(record, seen):
    base = ('id', 'kind', 'taskIds', 'fixture', 'sourceClass', 'provenance', 'experimentOnly', 'dataClass')
    _require(isinstance(record, dict), 'invalid record')
    kind = record.get('kind')
    extra = {'recipe': ('text', 'acceptance', 'evidence'), 'stale-recipe': ('text',), 'prior': ('text',),
             'acceptance': ('recipeId', 'recipeTextSha256', 'decision', 'evidence'),
             'evidence': ('verifier', 'result', 'measurement')}
    _require(isinstance(kind, str) and kind in extra, 'unsupported record kind')
    _keys(record, base + extra[kind])
    _scope(record)
    _require(_text(record['id']) and _text(record['fixture']), 'record identity/fixture required')
    tasks = record['taskIds']
    _require(isinstance(tasks, list) and tasks and all(_text(task) for task in tasks) and
             len(tasks) == len(set(tasks)) and set(tasks) <= seen, 'record tasks must belong to frozen S')
    if kind in ('recipe', 'stale-recipe', 'prior'):
        _require(_text(record['text']), 'record text required')
    elif kind == 'acceptance':
        _require(_text(record['recipeId']) and isinstance(record['recipeTextSha256'], str) and
                 SHA.fullmatch(record['recipeTextSha256']) and record['decision'] == 'accept', 'invalid acceptance')
    elif kind == 'evidence':
        _require(_text(record['verifier']) and record['result'] == 'passed' and _text(record['measurement']), 'named verification measurement required')


validate_store = load_store
