"""Data safety uses a supplied current template; never generate product facts."""
import contextlib
import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from shared.play_api import APIError, PlayError
from shared.play_safety import HEADERS, apply, main, read_csv


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.before=self.csv('before.csv','FALSE')
        self.proposed=self.csv('proposed.csv','TRUE')
    def tearDown(self): self.temp.cleanup()
    def csv(self,name,value):
        path=self.root/name
        with path.open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(HEADERS)
            writer.writerow(['PSL_DATA_COLLECTION_COLLECTS_PERSONAL_DATA','',value,'REQUIRED','Does the app collect or share data?'])
        return path
    def transport(self,failure=None):
        calls=[]
        class Fake:
            def request(inner,method,url,*,payload=None):
                self.assertTrue((self.root/'backup/before.csv').exists())
                self.assertTrue((self.root/'backup/transaction.json').exists())
                calls.append((method,url,payload))
                if failure: raise failure
                return {}
        return Fake(),calls
    def test_real_endpoint_csv_payload_and_backup_before_write(self):
        transport,calls=self.transport()
        result=apply('com.example.habits',self.proposed,self.before,self.root/'backup',transport)
        self.assertEqual(result['status'],'submitted')
        self.assertTrue(calls[0][1].endswith('/applications/com.example.habits/dataSafety'))
        self.assertEqual(calls[0][2],{'safetyLabels':self.proposed.read_bytes().decode('utf-8-sig')})
        self.assertEqual(json.loads((self.root/'backup/transaction.json').read_text())['status'],'submitted')
    def test_unknown_write_persists_receipt_without_retry(self):
        transport,calls=self.transport(APIError(503,'busy'))
        with self.assertRaisesRegex(PlayError,'unknown'):
            apply('com.example.habits',self.proposed,self.before,self.root/'backup',transport)
        self.assertEqual(len(calls),1)
        self.assertEqual(json.loads((self.root/'backup/transaction.json').read_text())['status'],'submission-outcome-unknown')
    def test_rejected_write_does_not_claim_unknown(self):
        transport,calls=self.transport(APIError(400,'bad CSV'))
        with self.assertRaises(APIError):
            apply('com.example.habits',self.proposed,self.before,self.root/'backup',transport)
        self.assertEqual(json.loads((self.root/'backup/transaction.json').read_text())['status'],'submission-rejected')
    def test_identical_proposal_never_writes(self):
        transport,calls=self.transport()
        result=apply('com.example.habits',self.before,self.before,self.root/'backup',transport)
        self.assertEqual(result['status'],'unchanged');self.assertEqual(calls,[])
    def test_comparison_backup_payload_and_receipt_use_one_csv_snapshot(self):
        original = self.proposed.read_bytes()
        read_paths = []
        def changing_read(path):
            value = read_csv(path)
            read_paths.append(Path(path))
            if Path(path) == self.proposed:
                self.csv('proposed.csv', 'FALSE')
            return value
        transport, calls = self.transport()
        with patch('shared.play_safety.read_csv', side_effect=changing_read):
            result = apply('com.example.habits', self.proposed, self.before, self.root/'backup', transport)
        self.assertEqual(read_paths, [self.proposed, self.before])
        self.assertEqual(result['status'], 'submitted')
        self.assertEqual(calls[0][2]['safetyLabels'], original.decode('utf-8-sig'))
        self.assertEqual((self.root/'backup/proposed.csv').read_bytes(), original)
        self.assertEqual(result['proposed_sha256'], hashlib.sha256(original).hexdigest())
    def test_unchanged_live_cli_does_not_load_credentials(self):
        with patch('shared.play_safety.ADCTransport', side_effect=AssertionError('network')), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['apply', '--live', '--package', 'com.example.habits', '--csv', str(self.before), '--before-csv', str(self.before), '--backup-directory', str(self.root/'backup')]), 0)
        self.assertEqual(json.loads(output.getvalue())['status'], 'unchanged')
        self.assertFalse((self.root/'backup').exists())
    def test_existing_backup_blocks_cli_before_loading_credentials(self):
        (self.root/'backup').mkdir()
        with patch('shared.play_safety.ADCTransport', side_effect=AssertionError('network')), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['apply', '--live', '--package', 'com.example.habits', '--csv', str(self.proposed), '--before-csv', str(self.before), '--backup-directory', str(self.root/'backup')]), 2)
    def test_csv_size_limit_bounds_initial_file_read(self):
        data = io.BytesIO(b'x' * (4 * 1024 * 1024 + 2))
        with patch('shared.play_safety.Path.open') as opened:
            opened.return_value.__enter__.return_value = data
            with self.assertRaisesRegex(ValueError, '4 MiB'):
                read_csv('oversized.csv')
            self.assertEqual(data.tell(), 4 * 1024 * 1024 + 1)
    def test_offline_apply_and_missing_before_never_load_credentials(self):
        with patch('shared.play_safety.ADCTransport',side_effect=AssertionError('network')),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['apply','--package','com.example.habits','--csv',str(self.proposed)]),0)
            self.assertEqual(main(['apply','--live','--package','com.example.habits','--csv',str(self.proposed)]),2)
    def test_required_blank_and_bad_boolean_rejected(self):
        for value in ('','YES','true'):
            with self.assertRaises(ValueError):read_csv(self.csv('bad.csv',value))
    def test_real_header_response_id_is_required(self):
        path=self.root/'wrong.csv'
        path.write_text('Question ID (machine readable),Response (machine readable),Response value,Answer requirement,Human-friendly question label\nQ,R,TRUE,REQUIRED,Q\n')
        with self.assertRaisesRegex(ValueError,'headers'):read_csv(path)
    def test_duplicate_rows_and_single_choice_multiple_true_rejected(self):
        for response_ids in (['A','A'],['A','B']):
            path=self.root/'bad.csv'
            with path.open('w',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(HEADERS)
                for response in response_ids:writer.writerow(['Q',response,'TRUE','SINGLE_CHOICE','Question'])
            with self.assertRaises(ValueError):read_csv(path)

if __name__=='__main__':unittest.main()
