from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from backend.app.contracts import MODULES,NewJob
from backend.app.worker import run
from audit_data_lab.excel_reports import build_review_payload
from test_deeper_analytics import cash_rows
from audit_data_lab import cash_proofing,execute_analysis

class DeeperIntegrationTests(unittest.TestCase):
    def test_optional_inputs_exposed(self):
        self.assertEqual(MODULES['cash_proofing']['required_inputs'],['bank','cash_gl'])
        self.assertIn('balances',MODULES['cash_proofing']['optional_inputs'])
        NewJob(module='analytical_review',parameters={'tb_period':'12','tb_sign_basis':'debit_positive'}).checked()
        NewJob(module='kyc',parameters={'report_type':'A003'}).checked()

    def test_worker_cash_timing_condition_and_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'inputs').mkdir()
            inputs={}
            for slot,frame in [('bank',cash_rows('b',['20070101'],['100'])),('cash_gl',cash_rows('g',['20070103'],['100']))]:
                frame.to_csv(root/'inputs'/f'{slot}.csv',index=False)
                inputs[slot]={'stored_name':f'{slot}.csv','suffix':'.csv'}
            captured=[]
            def paper(result,folder,**kwargs):
                captured.append(result);folder.mkdir();(folder/'result.txt').write_text(result.name)
            with patch('backend.app.worker.generate_working_paper',side_effect=paper):
                run({'directory':tmp,'parameters':{'date_tolerance_days':2},'inputs':inputs,'module':'cash_proofing','job_id':'test'})
            self.assertEqual(captured[0].summary['timing_match_count'],1)
            self.assertTrue((root/'bundle.zip').exists())

    def test_nonjet_excel_payload_reports_module_and_issues(self):
        b=cash_rows('b',['20070101'],['100'])
        import pandas as pd
        result=execute_analysis('cash_proofing',lambda:cash_proofing(b,b,balances=pd.DataFrame({'wrong':[1]}),as_of='20070131'))
        payload=build_review_payload(result,entity='test',period='test')
        self.assertEqual(payload['summary'][0],['검사 모듈','cash_proofing'])
        self.assertGreater(len(payload['issues']),0)
        self.assertNotIn('로그 금액 대사',[row[0] for row in payload['summary']])
