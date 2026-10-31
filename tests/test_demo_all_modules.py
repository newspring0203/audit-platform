"""시연 파일의 실제 API 흐름. 고객 자료·외부 API를 사용하지 않는다."""
from pathlib import Path
from io import BytesIO
import sys,tempfile,time,json,unittest,zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from backend.app.main import create_app,AppConfig
from backend.app.storage import StorageConfig
from backend.app.worker import run
from audit_data_lab import kyc_review

CASES=[
 ('analytical_review',{'current_year':'2026','prior_year':'2025','change_threshold_pct':30,'tb_period':'10','tb_sign_basis':'debit_positive'},{'gl':'gl_comparison.csv','tb':'tb.csv','account_mapping':'account_mapping.csv'},'year_comparison'),
 ('jet',{'round_unit':1000,'rare_user_max':10,'rare_account_max':3,'combined_rule_min':2},{'gl':'gl_jet.csv','log':'log_control.csv'},'flagged_lines'),
 ('gl_user_split',{'user_column':'Entered_By','max_groups':500},{'gl':'gl_jet.csv'},'group_index'),
 ('cash_proofing',{'as_of':'20261031','date_tolerance_days':2,'aging_days':5},{'bank':'bank.csv','cash_gl':'cash_gl.csv','balances':'balances.csv'},'review_items'),
 ('inventory',{'as_of':'20261031','stale_days':180},{'movements':'movements.csv','opening':'opening.csv','lot_snapshot':'lot_snapshot.csv'},'review_items'),
 ('data_cleansing',{'required_columns':['GL_Account_Number','Effective_Date','Amount'],'date_columns':['Effective_Date'],'amount_columns':['Amount']},{'data':'cleansing_raw.csv','mapping':'cleansing_mapping.csv'},'issues'),
 ('quickbooks_preprocessing',{'date_format':'%Y-%m-%d'},{'quickbooks':'quickbooks_report.xlsx'},'modified_gl'),
]

class AllDemoTests(unittest.TestCase):
    def test_all_local_modules_upload_run_download_reference_link_and_history(self):
        expected=json.loads((ROOT/'data/demo/v1/expected_results.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(AppConfig(StorageConfig(Path(tmp)/'runtime'),cleanup_interval_seconds=3600,requests_per_minute=10000))
            token=app.state.store.issue_token('synthetic','tester');h={'Authorization':'Bearer '+token}
            with TestClient(app) as client:
                for module,parameters,slots,table in CASES:
                    with self.subTest(module=module):
                        response=client.post('/api/jobs',headers=h,json={'module':module,'parameters':parameters});self.assertEqual(response.status_code,201,response.text)
                        base='/api/jobs/'+response.json()['job_id']
                        for slot,name in slots.items():
                            response=client.put(base+'/inputs/'+slot,content=(ROOT/'data/demo/v1'/name).read_bytes(),headers=h|{'X-Filename':name});self.assertEqual(response.status_code,200,response.text)
                        self.assertEqual(client.post(base+'/run',headers=h).status_code,202)
                        end=time.monotonic()+15
                        while time.monotonic()<end:
                            status=client.get(base,headers=h).json()
                            if status['status']=='completed':break
                            time.sleep(.05)
                        self.assertEqual(status['status'],'completed')
                        response=client.get(base+'/review',headers=h);self.assertEqual(response.status_code,200,response.text);review=response.json()
                        if module in expected:
                            for key,value in expected[module].items():self.assertEqual(review['summary'][key],value,(module,key))
                        else:self.assertEqual(review['summary']['transaction_row_count'],2)
                        self.assertEqual(review['review_log']['references'],{})
                        rows=client.get(base+'/review/tables/'+table,headers=h).json()['rows'];self.assertTrue(rows)
                        record=rows[0]['review_id'];refs=[]
                        for n in [1,2]:
                            reference={'title':f'SYNTHETIC TEST {n} (공식 기준 아님)','issuer':'DEMO','edition':'TEST-2026','paragraph':f'DEMO-{n:02d}','applicability_note':'기준서 등록·선택 기능 테스트용이며 실무 회계기준이 아닙니다.'}
                            response=client.post(base+'/review/references',headers=h,json=reference);self.assertEqual(response.status_code,201,response.text);refs.append(response.json()['reference_id'])
                        latest=client.get(base+'/review',headers=h).json();self.assertEqual(len(latest['review_log']['references']),2)
                        note={'revision':latest['review_log']['revision'],'status':'검토중','explanation':'합성 시연 결과 확인','evidence_reference':'DEMO-01','conclusion':'기능 테스트이며 실제 감사 판단은 수행하지 않음','reference_ids':refs}
                        response=client.put(base+'/review/notes/'+record,headers=h,json=note);self.assertEqual(response.status_code,200,response.text)
                        exported=client.get(base+'/review/export',headers=h).json();self.assertEqual(exported['review_log']['events'][-1]['reference_ids'],refs)
                        response=client.get(base+'/downloads/'+status['artifact']['artifact_id'],headers=h);self.assertEqual(response.status_code,200)
                        filename=next(f['zip_filename'] for f in client.get('/api/features',headers=h).json()['features'] if f['module']==module)
                        self.assertEqual(response.headers['content-disposition'],f'attachment; filename="{filename}"')
                        with zipfile.ZipFile(BytesIO(response.content)) as z:self.assertIn('review/analysis/summary.json',z.namelist());self.assertIn('review/review_snapshot.json',z.namelist())
                        self.assertEqual(client.delete(base,headers=h).status_code,204)

    def test_kyc_worker_with_mock_disclosure_no_network_or_real_keys(self):
        result=kyc_review('SYNTHETIC TEST',fetch_documents=lambda _: [{'title':'DEMO 공시 (가상)','url':'https://example.invalid/demo','published_at':'2026-10-31','text':'Synthetic document for local workflow testing only.'}])
        with tempfile.TemporaryDirectory() as tmp:
            with patch('audit_data_lab.kyc_live.run_live_kyc',return_value=result) as provider:
                run({'directory':tmp,'parameters':{'company':'SYNTHETIC TEST','start_date':'20260101','end_date':'20261031','with_ai':False},'inputs':{},'module':'kyc','job_id':'mock-kyc','allow_ai':False})
                provider.assert_called_once()
            snapshot=json.loads((Path(tmp)/'report/review_snapshot.json').read_text());self.assertEqual(snapshot['summary']['source_count'],1);self.assertEqual(snapshot['summary']['insight_count'],0)
            self.assertTrue((Path(tmp)/'bundle.zip').is_file())
