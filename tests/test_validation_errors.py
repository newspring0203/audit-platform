"""사용자에게 전달할 오류 코드·원본 행·JSON 형식을 검증한다."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import pandas as pd
from test_sap_to_ads import fixtures, K, POST, PERIOD, AMOUNT

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from audit_data_lab.validation import DataValidationError, validate_sap_inputs, save_validation_report

class StructuredValidationTests(unittest.TestCase):
    def validate(self,b,h,t):
        return validate_sap_inputs(b,h,t,company='3000',year='2007',ledger='0',record_type='0',version='1')

    def test_multiple_independent_errors_are_collected_and_json_safe(self):
        b,h,t=fixtures();b.loc[0,AMOUNT]='bad';h.loc[0,PERIOD]='02'
        with self.assertRaises(DataValidationError) as caught:self.validate(b,h,t)
        payload=caught.exception.to_dict()
        codes={i['code'] for i in payload['errors']}
        self.assertIn('INVALID_AMOUNT',codes);self.assertIn('PERIOD_DATE_MISMATCH',codes)
        self.assertEqual(json.loads(json.dumps(payload,ensure_ascii=False,allow_nan=False)),payload)
        issue=next(i for i in payload['errors'] if i['code']=='PERIOD_DATE_MISMATCH')
        self.assertEqual(issue['field'],'Period');self.assertEqual(issue['source_field'],PERIOD)
        self.assertEqual(issue['source_row'],2);self.assertEqual(issue['source_table'],'BKPF')
        self.assertEqual(issue['journal_id'],'3000:2007:000001')
        self.assertEqual(issue['value'],'02')
        self.assertTrue(issue['message']);self.assertEqual(payload['status'],'validation_failed')

    def test_original_row_survives_scope_filter_and_nonstandard_index(self):
        b,h,t=fixtures();other=h.copy();other[K[0]]='4000'
        h=pd.concat([other,h],ignore_index=True);h.index=[50,99];h.loc[99,PERIOD]='02'
        with self.assertRaises(DataValidationError) as caught:self.validate(b,h,t)
        issue=next(i for i in caught.exception.issues if i.code=='PERIOD_DATE_MISMATCH')
        self.assertEqual(issue.source_row,3)

    def test_missing_column_has_no_fabricated_row(self):
        b,h,t=fixtures();h=h.drop(columns=[POST])
        with self.assertRaises(DataValidationError) as caught:self.validate(b,h,t)
        issue=caught.exception.issues[0]
        self.assertEqual(issue.code,'MISSING_COLUMN');self.assertIsNone(issue.source_row)
        self.assertEqual(issue.source_field,POST)

    def test_missing_value_is_json_null(self):
        b,h,t=fixtures();b.loc[0,AMOUNT]=pd.NA
        with self.assertRaises(DataValidationError) as caught:self.validate(b,h,t)
        issue=next(i for i in caught.exception.to_dict()['errors'] if i['code']=='MISSING_AMOUNT')
        self.assertIsNone(issue['value']);self.assertEqual(issue['source_row'],2)

    def test_missing_scope_key_is_not_silently_filtered_out(self):
        b,h,t=fixtures();b.loc[0,K[0]]=pd.NA
        with self.assertRaises(DataValidationError) as caught:self.validate(b,h,t)
        self.assertIn('MISSING_SCOPE_KEY',{i.code for i in caught.exception.issues})

    def test_input_frames_are_not_mutated(self):
        b,h,t=fixtures();before=[f.copy(deep=True) for f in [b,h,t]]
        result=self.validate(b,h,t)
        for old,current in zip(before,[b,h,t]):pd.testing.assert_frame_equal(old,current)
        self.assertEqual(result[0]['__source_row'].tolist(),[2,3])
        self.assertNotIn('__source_row',b.columns)

    def test_reports_are_cleared_after_success(self):
        b,h,t=fixtures();b.loc[0,AMOUNT]='bad'
        with self.assertRaises(DataValidationError) as caught:self.validate(b,h,t)
        with tempfile.TemporaryDirectory() as folder:
            save_validation_report(folder,caught.exception)
            p=Path(folder)
            payload=json.loads((p/'validation_errors.json').read_text())
            self.assertEqual(payload['status'],'validation_failed')
            self.assertGreater(len(pd.read_csv(p/'validation_errors.csv')),0)
            save_validation_report(folder)
            payload=json.loads((p/'validation_errors.json').read_text())
            self.assertEqual(payload['status'],'input_validation_passed')
            self.assertEqual(payload['errors'],[])
            self.assertEqual(len(pd.read_csv(p/'validation_errors.csv')),0)

    def test_duplicate_columns_have_structured_error(self):
        b,h,t=fixtures();b=pd.concat([b,b[[AMOUNT]]],axis=1)
        with self.assertRaises(DataValidationError) as caught:self.validate(b,h,t)
        self.assertEqual(caught.exception.issues[0].code,'DUPLICATE_COLUMNS')

if __name__=='__main__':unittest.main(verbosity=2)
