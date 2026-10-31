from pathlib import Path
import sys,json,tempfile,unittest,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
import pandas as pd
from fastapi.testclient import TestClient
from backend.app.main import create_app,AppConfig
from backend.app.storage import StorageConfig
from backend.app.worker import run
from audit_data_lab.traceability import attach_traceability
from audit_data_lab import analytical_review,inventory_analysis,cash_proofing
from test_deeper_analytics import two_years,cash_rows,inventory_rows

class TraceabilityTests(unittest.TestCase):
    def test_gl_scopes_years_currency_account_and_stable_ids(self):
        g=two_years();other=g.iloc[:1].copy();other['Amount_Currency']='EUR';other['Amount']='999';g=pd.concat([g,other],ignore_index=True)
        result=analytical_review(g,current_year='2007',prior_year='2006')
        manifest=attach_traceability(result,{'gl':g},{'gl':{'sha256':'file-hash','version_id':'version-1'}},run_id='run1',parameters={})
        row=next(r for r in manifest['tables']['year_comparison']['rows'] if r['values']['Amount_Currency']=='USD')
        trace=manifest['trace'][row['review_id']]
        self.assertEqual(trace['status'],'group_inputs');self.assertEqual(len(trace['sources']),2)
        for ref in trace['sources']:
            self.assertTrue(all(g.iloc[n-2]['Amount_Currency']=='USD' for n in ref['rows']))
            self.assertEqual(ref['dataset_version_id'],'version-1')
        self.assertIn('Change_Pct',trace['calculation'])
        self.assertEqual(result.tables['year_comparison'].iloc[0]['Review_Record_ID'],manifest['tables']['year_comparison']['rows'][0]['review_id'])

    def test_missing_comparison_year_is_not_fabricated_zero(self):
        gl=two_years();gl.loc[gl.Fiscal_Year.eq('2006'),'GL_Account_Number']='OTHER'
        result=analytical_review(gl,current_year='2007',prior_year='2006')
        for row in result.to_dict()['tables']['year_comparison']:
            self.assertTrue(row['Current_Movement'] is None or row['Prior_Movement'] is None)
            self.assertIsNone(row['Change'])

    def test_cash_exact_source_rows_and_source_not_mutated(self):
        b=cash_rows('b',['20070101'],['100']);g=cash_rows('g',['20070101'],['100'])
        before=b.copy(deep=True);r=cash_proofing(b,g)
        m=attach_traceability(r,{'bank':b,'cash_gl':g},{},run_id='cash')
        trace=m['trace'][m['tables']['matches']['rows'][0]['review_id']]
        self.assertEqual([(x['slot'],x['rows']) for x in trace['sources']],[('bank',[2]),('cash_gl',[2])]);pd.testing.assert_frame_equal(b,before)

    def test_inventory_timeline_excludes_future_movements(self):
        movements,opening=inventory_rows();r=inventory_analysis(movements,opening,as_of='20070131')
        m=attach_traceability(r,{'movements':movements,'opening':opening},{},run_id='stock')
        trace=m['trace'][m['tables']['movement_timeline']['rows'][0]['review_id']]
        self.assertEqual(next(ref['rows'] for ref in trace['sources'] if ref['slot']=='movements'),[2])

class ReviewApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=create_app(AppConfig(StorageConfig(Path(self.temp.name)/'runtime'),cleanup_interval_seconds=3600))
        self.store=self.app.state.store;self.token=self.store.issue_token('tenant','owner');self.other=self.store.issue_token('tenant','other')
        self.client=TestClient(self.app);self.client.__enter__();self.addCleanup(self.client.__exit__,None,None,None)
        self.h={'Authorization':'Bearer '+self.token};self.oh={'Authorization':'Bearer '+self.other}
        self.job=self.client.post('/api/jobs',json={'module':'cash_proofing'},headers=self.h).json()['job_id'];self.base='/api/jobs/'+self.job
    def upload(self,slot,content):return self.client.put(self.base+'/inputs/'+slot,content=content,headers=self.h|{'X-Filename':'test.csv'})
    def complete(self):
        for slot,frame in [('bank',cash_rows('b',['20070101'],['100'])),('cash_gl',cash_rows('g',['20070101'],['100']))]:self.assertEqual(self.upload(slot,frame.to_csv(index=False).encode()).status_code,200)
        row=self.store.owned(self.job,self.store.authenticate(self.token));folder=self.store.job_path(row)
        run({'directory':str(folder),'parameters':{},'inputs':json.loads(row['inputs']),'module':'cash_proofing','job_id':self.job});self.store.finalize(self.job)
        review=self.client.get(self.base+'/review',headers=self.h).json()
        result=self.client.get(self.base+'/review/tables/matches',headers=self.h).json()['rows'][0]
        return review,result['review_id']
    def test_version_replacement_retains_files_and_hashes_until_delete(self):
        self.upload('bank',b'X\nold\n');self.upload('bank',b'X\nnew\n')
        row=self.store.owned(self.job,self.store.authenticate(self.token));asset=json.loads(row['inputs'])['bank']
        self.assertEqual(len(asset['history']),1);self.assertNotEqual(asset['version_id'],asset['history'][0]['version_id'])
        path=self.store.job_path(row);self.assertEqual((path/'inputs'/asset['history'][0]['stored_name']).read_bytes(),b'X\nold\n')
        d=self.client.get(self.base+'/materials',headers=self.h).json()['datasets']['bank'];self.assertNotIn('stored_name',d);self.assertNotIn('stored_name',d['previous_versions'][0])
        self.client.delete(self.base,headers=self.h);self.assertFalse(path.exists())
    def test_material_dates_validate_and_freeze_on_run(self):
        self.upload('bank',b'X\n1\n')
        path=self.base+'/materials/bank'
        self.assertEqual(self.client.patch(path,json={'period_start':'2026-12-31','period_end':'2026-01-01'},headers=self.h).status_code,422)
        self.assertEqual(self.client.patch(path,json={'period_start':'2026-01-01','period_end':'2026-12-31','pbc_reference':'PBC-01'},headers=self.h).status_code,200)
        self.store.update_status(self.job,'queued')
        self.assertEqual(self.client.patch(path,json={'label':'changed'},headers=self.h).status_code,409)
    def test_trace_and_source_pagination_and_export_ids(self):
        _,rid=self.complete();trace=self.client.get(self.base+'/review/trace/'+rid,headers=self.h)
        self.assertEqual(trace.status_code,200);self.assertEqual(trace.json()['sources'][0]['rows'],[2])
        source=self.client.get(self.base+'/review/sources/bank?review_id='+rid,headers=self.h).json()
        self.assertEqual(source['rows'][0]['values']['Amount'],'100');self.assertEqual(source['rows'][0]['source_row'],2)
        self.assertEqual(self.client.get(self.base+'/review/sources/bank?review_id='+rid+'&limit=101',headers=self.h).status_code,422)
        exported=self.client.get(self.base+'/review/export',headers=self.h)
        self.assertEqual(exported.headers['cache-control'],'private, no-store');self.assertEqual(exported.json()['run_id'],self.job)
    def test_all_review_routes_deny_other_owner_and_expired(self):
        _,rid=self.complete()
        paths=['/materials','/review','/review/tables/matches','/review/trace/'+rid,'/review/sources/bank?review_id='+rid,'/review/export']
        for path in paths:self.assertEqual(self.client.get(self.base+path,headers=self.oh).status_code,404,path)
        self.assertEqual(self.client.post(self.base+'/review/references',json=self.reference(),headers=self.oh).status_code,404)
        self.assertEqual(self.client.put(self.base+'/review/notes/'+rid,json={'revision':0},headers=self.oh).status_code,404)
        with self.store.connection() as db:db.execute('UPDATE jobs SET expires=0 WHERE id=?',(self.job,))
        for path in paths:self.assertEqual(self.client.get(self.base+path,headers=self.h).status_code,404,path)
    def reference(self):return {'title':'사용자 확인 기준서','issuer':'발행기관','edition':'2026 판본','paragraph':'문단 1','url':'https://example.org/standard','applicability_note':'거래 사실과 적용 범위를 검토할 예정'}
    def test_reference_is_unverified_and_notes_append_conflict_and_completion(self):
        _,rid=self.complete();ref=self.client.post(self.base+'/review/references',json=self.reference(),headers=self.h)
        self.assertEqual(ref.status_code,201);self.assertEqual(ref.json()['reference']['verification_status'],'user_supplied_unverified')
        path=self.base+'/review/notes/'+rid
        self.assertEqual(self.client.put(path,json={'revision':0},headers=self.h).status_code,409)
        self.assertEqual(self.client.put(path,json={'revision':1,'status':'검토완료'},headers=self.h).status_code,422)
        note={'revision':1,'status':'검토완료','evidence_reference':'PBC-01','conclusion':'추가 근거 확인','reference_ids':[ref.json()['reference_id']]}
        self.assertEqual(self.client.put(path,json=note,headers=self.h).status_code,200)
        self.assertEqual(self.client.put(path,json=note,headers=self.h).status_code,409)
        log=self.client.get(self.base+'/review',headers=self.h).json()['review_log'];self.assertEqual(len(log['events']),1);self.assertEqual(log['events'][0]['reviewer'],'owner')
    def test_reference_rejects_script_url_and_unknown_record(self):
        _,rid=self.complete();r=self.reference();r['url']='javascript:alert(1)'
        self.assertEqual(self.client.post(self.base+'/review/references',json=r,headers=self.h).status_code,422)
        self.assertEqual(self.client.put(self.base+'/review/notes/missing',json={'revision':0},headers=self.h).status_code,404)
    def test_version_compare_requires_unique_keys_and_returns_changes(self):
        self.upload('bank',b'Row_ID,Amount\nA,100\nB,50\n')
        self.upload('bank',b'Row_ID,Amount\nA,120\nC,30\n')
        assets=self.client.get(self.base+'/materials',headers=self.h).json()['datasets']['bank']
        prior=assets['previous_versions'][0]['version_id']
        response=self.client.get(self.base+'/materials/bank/compare',params={'prior_version':prior,'keys':'Row_ID'},headers=self.h)
        self.assertEqual(response.status_code,200,response.text)
        result=response.json();self.assertEqual(result['summary'],{'added':1,'removed':1,'changed':1,'unchanged':0})
        change=next(x for x in result['changes'] if x['kind']=='changed');self.assertEqual(change['prior']['Amount'],'100');self.assertEqual(change['current']['Amount'],'120')
        self.assertEqual(self.client.get(self.base+'/materials/bank/compare',params={'prior_version':prior,'keys':'Amount'},headers=self.oh).status_code,404)
        self.upload('bank',b'Row_ID,Amount\nA,100\nA,120\n')
        duplicate=self.client.get(self.base+'/materials/bank/compare',params={'prior_version':prior,'keys':'Row_ID'},headers=self.h)
        self.assertEqual(duplicate.status_code,422);self.assertEqual(duplicate.json()['error']['issues'][0]['code'],'COMPARISON_KEY_DUPLICATED')

    def test_frontend_is_local_and_csp_and_no_store(self):
        r=self.client.get('/');self.assertEqual(r.status_code,200);self.assertIn("script-src 'self'",r.headers['content-security-policy']);self.assertIn('no-store',r.headers['cache-control'])
        self.assertEqual(self.client.get('/workspace.js').status_code,200)
    def test_original_hash_tamper_returns_issue_not_success(self):
        self.upload('bank',b'Row_ID,Bank_Account,Currency,Date,Amount\nb0,A,USD,20070101,100\n')
        row=self.store.owned(self.job,self.store.authenticate(self.token));assets=json.loads(row['inputs']);folder=self.store.job_path(row)
        (folder/'inputs'/assets['bank']['stored_name']).write_bytes(b'tampered')
        run({'directory':str(folder),'parameters':{},'inputs':assets,'module':'cash_proofing','job_id':self.job})
        snapshot=json.loads((folder/'report'/'review_snapshot.json').read_text())
        self.assertEqual(snapshot['metadata']['execution_status'],'not_executed_input_issue')
        self.assertEqual(snapshot['tables']['validation_issues']['rows'][0]['values']['code'],'SOURCE_HASH_MISMATCH')
