import hashlib,json,tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_release import verify
class Release(unittest.TestCase):
 def test_hash_tamper_and_unlisted_files(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'README.md';p.write_bytes(b'public')
   m={'files':[{'path':'README.md','sha256':hashlib.sha256(b'public').hexdigest(),'bytes':6,'license':'MIT'}]}
   (root/'manifest.json').write_text(json.dumps(m));self.assertEqual(verify(root)['files'],1)
   p.write_bytes(b'tamper')
   with self.assertRaises(ValueError):verify(root)
   p.write_bytes(b'public');(root/'private.txt').write_bytes(b'unlisted')
   with self.assertRaises(ValueError):verify(root)
 def test_private_path_and_engine_binary_refused(self):
  for name,data in [('README.md',b'C:'+bytes([92])+b'Users'+bytes([92])+b'Private'),('engine.exe',b'binary'),('.env',b'secret'),('.env.local',b'secret'),('.ENV.LOCAL',b'secret')]:
   with tempfile.TemporaryDirectory() as td:
    root=Path(td);(root/name).write_bytes(data);(root/'manifest.json').write_text(json.dumps({'files':[{'path':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'license':'MIT'}]}))
    with self.assertRaises(ValueError):verify(root)
 def test_nested_manifest_cannot_escape_inventory(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'manifest.json').write_text(json.dumps({'files':[]}));(root/'parity').mkdir();(root/'parity'/'manifest.json').write_bytes(b'private')
   with self.assertRaises(ValueError):verify(root)
 def test_manifest_metadata_and_nested_result_paths_checked(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);m=root/'manifest.json';m.write_text(json.dumps({'files':[],'description':'C:'+chr(47)+'Users'+chr(47)+'Private'}))
   with self.assertRaises(ValueError):verify(root)
   m.write_bytes(json.dumps({'files':[],'description':'C:'+chr(47)+'Users'+chr(47)+'Private'}).replace('/',chr(92)+'u002f').encode())
   with self.assertRaises(ValueError):verify(root)
   m.write_text(json.dumps({'files':[]}));p=root/'parity'/'results';p.mkdir(parents=True);(p/'private.log').write_text('private')
   with self.assertRaises(ValueError):verify(root)
 def test_duplicate_inventory_key_refused(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'manifest.json').write_bytes(b'{"files":[{"path":"../external"}],"files":[]}')
   with self.assertRaises(ValueError):verify(root)
if __name__=='__main__':unittest.main()
