"""Data safety uses a supplied current template; never generate product facts."""
import contextlib
import csv
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
