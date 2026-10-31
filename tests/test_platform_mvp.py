from pathlib import Path
import sys,tempfile,unittest,csv,io
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from backend.app.main import create_app,AppConfig
from backend.app.storage import StorageConfig
from backend.app.contracts import NewJob
from backend.app.ui_schema import module_ui

class MvpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.app=create_app(AppConfig(StorageConfig(Path(self.tmp.name)/'runtime'),cleanup_interval_seconds=3600));s=self.app.state.store
        self.token=s.issue_token('test','owner');self.other=s.issue_token('test','other');self.h={'Authorization':'Bearer '+self.token};self.oh={'Authorization':'Bearer '+self.other}
        self.client=TestClient(self.app);self.client.__enter__();self.addCleanup(self.client.__exit__,None,None,None)
    def test_jobs_list_only_live_owned_jobs(self):
        own=self.client.post('/api/jobs',json={'module':'gl_user_split'},headers=self.h).json()['job_id']
        self.client.post('/api/jobs',json={'module':'gl_user_split'},headers=self.oh)
        jobs=self.client.get('/api/jobs',headers=self.h);self.assertEqual(jobs.status_code,200);self.assertEqual([j['job_id'] for j in jobs.json()['jobs']],[own]);self.assertIn('no-store',jobs.headers['cache-control'])
        self.assertEqual(self.client.get('/api/jobs').status_code,401)
        with self.app.state.store.connection() as db:db.execute('UPDATE jobs SET expires=0 WHERE id=?',(own,))
        self.assertEqual(self.client.get('/api/jobs',headers=self.h).json()['jobs'],[])
    def test_feature_ui_and_safe_empty_templates(self):
        features=self.client.get('/api/features',headers=self.h).json()['features']
        for f in features:self.assertIn('fields',f['ui']);self.assertIn('description',f['ui'])
        response=self.client.get('/api/input-templates/cash_proofing/bank',headers=self.h);self.assertEqual(response.status_code,200)
        rows=list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))));self.assertEqual(rows,[['Row_ID','Bank_Account','Currency','Date','Amount']])
        self.assertEqual(self.client.get('/api/input-templates/kyc/data',headers=self.h).status_code,404)
        self.assertEqual(self.client.get('/api/input-templates/cash_proofing/bank').status_code,401)
    def test_server_rejects_bad_parameters_before_job_creation(self):
        for module,params in [('inventory',{'as_of':'20260230'}),('cash_proofing',{'date_tolerance_days':-1}),('gl_user_split',{'max_groups':True}),('analytical_review',{'current_year':'2026','prior_year':'2026'}),('kyc',{'start_date':'20261031','end_date':'20260101'}),('quickbooks_preprocessing',{'date_format':'guess'})]:
            response=self.client.post('/api/jobs',json={'module':module,'parameters':params},headers=self.h);self.assertEqual(response.status_code,422,(params,response.text))
    def test_missing_basis_not_confirmed_by_ui_default(self):
        ar=module_ui()['analytical_review'];self.assertEqual(next(f for f in ar['fields'] if f['key']=='tb_sign_basis')['default'],'')
        NewJob(module='analytical_review',parameters={'current_year':'2026','prior_year':'2025'}).checked()
    def test_frontend_has_forms_and_keeps_advanced_mode(self):
        page=self.client.get('/');self.assertEqual(page.status_code,200)
        for marker in ['parameterForm','jobsList','summaryCards','고급 조건 JSON']:self.assertIn(marker,page.text)
