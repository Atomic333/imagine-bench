"""Verify the versioned public input inventory without executing an engine or model."""
import argparse,hashlib,json,re
from pathlib import Path,PurePosixPath
SKIP={'.git'}
PRIVATE=re.compile(rb'[A-Za-z]:[\\/]+(?:Users|Unreal-AI|Program Files)',re.I)
FORBIDDEN={'.exe','.dll','.pdb','.obj','.cpp','.h','.hpp','.hlsl','.uasset','.unitypackage','.env','.log'}
def unique(pairs):
 value={}
 for key,item in pairs:
  if key in value:raise ValueError('Duplicate release metadata key')
  value[key]=item
 return value
def verify(root):
 root=Path(root).resolve()
 for entry in root.rglob('*'):
  if entry.relative_to(root).parts[0] not in SKIP and (entry.is_symlink() or getattr(entry,'is_junction',lambda:False)()):raise ValueError('Linked release inputs refused')
 raw=(root/'manifest.json').read_bytes()
 if PRIVATE.search(raw):raise ValueError('Private local path in release metadata')
 manifest=json.loads(raw,object_pairs_hook=unique)
 if PRIVATE.search(json.dumps(manifest,ensure_ascii=False).encode()):raise ValueError('Private local path in decoded release metadata')
 seen=set()
 for row in manifest['files']:
  rel=PurePosixPath(row['path'])
  if rel.is_absolute() or '..' in rel.parts or str(rel)!=row['path'] or row['path'] in seen:raise ValueError('Invalid or duplicate inventory path')
  path=root/row['path']
  if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():raise ValueError('Missing or unsafe public file')
  if path.suffix.lower() in FORBIDDEN or path.name.lower() == '.env' or path.name.lower().startswith('.env.'):raise ValueError('Engine code/binary or private file type refused')
  data=path.read_bytes()
  if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Public input hash mismatch: '+row['path'])
  if PRIVATE.search(data):raise ValueError('Private local path in public input: '+row['path'])
  if row['license'] not in {'MIT','CC-BY-4.0','CC0-1.0'}:raise ValueError('Unqualified public licence')
  seen.add(row['path'])
 actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.relative_to(root).parts[0] not in SKIP and p.relative_to(root).as_posix()!='manifest.json'}
 if actual!=seen:raise ValueError('Unlisted or missing release inputs: '+str(sorted(actual^seen)))
 return {'files':len(seen),'passed':True,'modelRuns':0}
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent);args=parser.parse_args();print(json.dumps(verify(args.root)))
