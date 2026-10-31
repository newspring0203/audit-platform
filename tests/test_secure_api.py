"""새 임시 저장소만 사용해 소유권·삭제·다운로드·캐시·분석 연결을 검증한다."""
from io import BytesIO
from pathlib import Path
import hashlib,json,os,sys,tempfile,time,unittest,zipfile
from dataclasses import replace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app.main import create_app,AppConfig
from backend.app.storage import StorageConfig,PrivateStore,ServiceError
from backend.app.uploads import validate_upload

class Clock:
    def __init__(self):self.now=1000000.0
    def __call__(self):return self.now

class SecureApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.clock=Clock()
        config=AppConfig(StorageConfig(Path(self.temp.name)/'runtime',job_ttl_seconds=100,token_ttl_seconds=1000),cleanup_interval_seconds=3600)
        self.app=create_app(config,clock=self.clock);self.store=self.app.state.store
        self.tokens={name:self.store.issue_token(tenant,user) for name,tenant,user in [('alice','A','alice'),('bob','A','bob'),('other_tenant','B','alice')]}
        self.client=TestClient(self.app);self.client.__enter__();self.addCleanup(self.client.__exit__,None,None,None)

    def headers(self,who='alice'):return {'Authorization':'Bearer '+self.tokens[who]}
    def create(self,module='data_cleansing',parameters=None,who='alice'):
        r=self.client.post('/api/jobs',json={'module':module,'parameters':parameters or {}},headers=self.headers(who))
        self.assertEqual(r.status_code,201,r.text);return r.json()['job_id']
    def upload(self,job,slot='data',data=b'Date,Amount\n20070101,100\n',filename='data.csv',who='alice'):
        return self.client.put(f'/api/jobs/{job}/inputs/{slot}',content=data,headers={**self.headers(who),'X-Filename':filename})
    def artifact(self,job):
        row=self.store.owned(job,self.store.authenticate(self.tokens['alice']))
        data=BytesIO()
        with zipfile.ZipFile(data,'w') as z:z.writestr('review/summary.json','{"test":true}')
        self.store.write_private(self.store.job_path(row)/'bundle.zip',data.getvalue());self.store.finalize(job)
        return self.client.get('/api/jobs/'+job,headers=self.headers()).json()['artifact']['artifact_id']
    def wait_done(self,job,timeout=10):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            r=self.client.get('/api/jobs/'+job,headers=self.headers())
            if r.status_code==200 and r.json()['status']=='completed':return r.json()
            time.sleep(0.1)
        self.fail('작업이 제한 시간 안에 완료되지 않음')

    def test_authentication_required_and_identity_headers_do_not_authenticate(self):
        for path in ['/api/features','/api/jobs/00000000000000000000000000000000']:
            r=self.client.get(path,headers={'X-User-ID':'alice','X-Tenant-ID':'A'})
            self.assertEqual(r.status_code,401);self.assertIn('no-store',r.headers['cache-control'])

    def test_cross_user_and_cross_tenant_are_denied_for_every_operation(self):
        job=self.create();artifact=self.artifact(job)
        for who in ['bob','other_tenant']:
            h=self.headers(who)
            for method,url in [('get',f'/api/jobs/{job}'),('post',f'/api/jobs/{job}/run'),('delete',f'/api/jobs/{job}'),('get',f'/api/jobs/{job}/downloads/{artifact}')]:
                r=getattr(self.client,method)(url,headers=h);self.assertEqual(r.status_code,404,(who,method,r.text))
            self.assertEqual(self.upload(job,who=who).status_code,404)

    def test_server_does_not_accept_owner_or_api_keys_from_body(self):
        for name in ['user_id','tenant_id','api_key']:
            payload={'module':'data_cleansing',name:'secret-owner-value'}
            r=self.client.post('/api/jobs',json=payload,headers=self.headers())
            self.assertEqual(r.status_code,422);self.assertNotIn('secret-owner-value',r.text)

    def test_owner_can_download_but_random_artifact_or_missing_auth_cannot(self):
        job=self.create();aid=self.artifact(job)
        self.assertEqual(self.client.get(f'/api/jobs/{job}/downloads/{aid}').status_code,401)
        self.assertEqual(self.client.get(f'/api/jobs/{job}/downloads/'+('0'*32),headers=self.headers()).status_code,404)
        r=self.client.get(f'/api/jobs/{job}/downloads/{aid}',headers=self.headers())
        self.assertEqual(r.status_code,200);self.assertTrue(zipfile.is_zipfile(BytesIO(r.content)))
        self.assertEqual(r.headers['cache-control'],'private, no-store')
        self.assertNotIn('etag',r.headers);self.assertNotIn('last-modified',r.headers)

    def test_expiry_denies_access_then_cleanup_removes_all_job_files(self):
        job=self.create();aid=self.artifact(job);self.uploaded_path=None
        row=self.store.owned(job,self.store.authenticate(self.tokens['alice']));folder=self.store.job_path(row)
        (folder/'tmp').mkdir();self.store.write_private(folder/'tmp'/'debug.tmp',b'private')
        self.clock.now+=101
        self.assertEqual(self.client.get(f'/api/jobs/{job}/downloads/{aid}',headers=self.headers()).status_code,404)
        self.app.state.manager.cleanup()
        self.assertFalse(folder.exists())
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0],0)

    def test_manual_delete_removes_inputs_and_downloads(self):
        job=self.create();self.assertEqual(self.upload(job).status_code,200);aid=self.artifact(job)
        folder=self.store.job_path(self.store.owned(job,self.store.authenticate(self.tokens['alice'])))
        self.assertEqual(self.client.delete('/api/jobs/'+job,headers=self.headers()).status_code,204)
        self.assertFalse(folder.exists());self.assertEqual(self.client.get(f'/api/jobs/{job}/downloads/{aid}',headers=self.headers()).status_code,404)

    def test_logout_and_expired_tokens_cannot_reuse_access(self):
        self.assertEqual(self.client.post('/api/logout',headers=self.headers()).status_code,204)
        self.assertEqual(self.client.get('/api/features',headers=self.headers()).status_code,401)
        self.clock.now+=1001
        self.assertEqual(self.client.get('/api/features',headers=self.headers('bob')).status_code,401)

    def test_tokens_stored_as_hash_and_storage_permissions_are_private(self):
        token=self.tokens['alice'];self.assertNotIn(token.encode(),self.store.db.read_bytes())
        self.assertEqual(self.store.root.stat().st_mode&0o777,0o700)
        self.assertEqual(self.store.db.stat().st_mode&0o777,0o600)
        job=self.create();self.upload(job)
        row=self.store.owned(job,self.store.authenticate(token));item=json.loads(row['inputs'])['data']
        self.assertEqual((self.store.job_path(row)/'inputs'/item['stored_name']).stat().st_mode&0o777,0o600)

    def test_traversal_and_unsupported_types_are_rejected(self):
        job=self.create()
        for filename in ['../../.env','data.xlsm','data.exe','/tmp/data.csv']:
            self.assertEqual(self.upload(job,filename=filename).status_code,422)
        self.assertEqual(self.upload(job,data=b'PK-not-a-workbook',filename='data.xlsx').status_code,422)
        self.assertEqual(self.upload(job,data=b'abc\x00def').status_code,422)

    def test_wrong_input_slot_and_raw_owner_headers_do_not_change_scope(self):
        job=self.create()
        self.assertIn(self.upload(job,slot='../../secret').status_code,(404,405))
        self.assertEqual(self.upload(job,slot='gl').status_code,422)
        self.assertEqual(self.upload(job,who='bob').status_code,404)

    def test_oversize_stream_is_aborted_and_partial_file_removed(self):
        job=self.create();limit=self.store.config.max_upload_bytes
        def chunks():
            for _ in range(22):yield b'x'*(1024*1024)
        r=self.client.put(f'/api/jobs/{job}/inputs/data',content=chunks(),headers={**self.headers(),'X-Filename':'data.csv'})
        self.assertEqual(r.status_code,413)
        row=self.store.owned(job,self.store.authenticate(self.tokens['alice']))
        self.assertEqual(row['status'],'created')
        self.assertEqual(list((self.store.job_path(row)/'inputs').iterdir()),[])

    def test_job_quota_and_expired_jobs_do_not_block_new_uploads(self):
        for _ in range(3):self.create()
        self.assertEqual(self.client.post('/api/jobs',json={'module':'data_cleansing'},headers=self.headers()).status_code,429)
        self.clock.now+=101
        self.create()

    def test_real_analysis_pipeline_provides_private_review_zip(self):
        job=self.create(parameters={'date_columns':['Date'],'amount_columns':['Amount']})
        self.assertEqual(self.upload(job,data=b'Date,Amount\n20070230,bad\n').status_code,200)
        self.assertEqual(self.client.post(f'/api/jobs/{job}/run',headers=self.headers()).status_code,202)
        result=self.wait_done(job)
        data=self.client.get(f"/api/jobs/{job}/downloads/{result['artifact']['artifact_id']}",headers=self.headers()).content
        with zipfile.ZipFile(BytesIO(data)) as z:
            self.assertIn('review/working_paper.md',z.namelist())
            summary=json.loads(z.read('review/analysis/summary.json'))
            self.assertEqual(summary['summary']['issue_count'],2)
            self.assertFalse(any('spec.json' in n or '/inputs/' in n or '_preview' in n for n in z.namelist()))
        self.assertEqual(self.client.post(f'/api/jobs/{job}/run',headers=self.headers()).status_code,409)

    def test_missing_inputs_produce_review_instead_of_http_500(self):
        job=self.create(module='jet',parameters={'company':'3000','fiscal_year':'2007'})
        self.client.post(f'/api/jobs/{job}/run',headers=self.headers());result=self.wait_done(job)
        response=self.client.get(f"/api/jobs/{job}/downloads/{result['artifact']['artifact_id']}",headers=self.headers())
        with zipfile.ZipFile(BytesIO(response.content)) as z:
            summary=json.loads(z.read('review/analysis/summary.json'))
            self.assertEqual(summary['metadata']['execution_status'],'not_executed_input_issue')
            self.assertIn('REQUIRED_INPUT_MISSING',z.read('review/analysis/validation_issues.csv').decode('utf-8-sig'))

    def test_jet_and_other_analysis_pages_use_the_same_private_download_flow(self):
        from test_analysis_features import gl_sample,log_ads
        cases=[
            ('jet',{'company':'3000','fiscal_year':'2007'},
             {'gl':gl_sample().to_csv(index=False).encode(),'log':log_ads().to_csv(index=False).encode()},
             'log_amount_reconciliation_status','basis_information_missing'),
            ('cash_proofing',{},
             {'bank':b'Row_ID,Bank_Account,Currency,Date,Amount\nb1,A,USD,20070101,100\n',
              'cash_gl':b'Row_ID,Bank_Account,Currency,Date,Amount\ng1,A,USD,20070101,100\n'},'matched_count',1),
            ('inventory',{'as_of':'20071231'},
             {'movements':b'Item_ID,Date,Quantity_In,Quantity_Out\nA,20070101,10,2\n',
              'opening':b'Item_ID,Opening_Quantity\nA,5\n'},'item_count',1),
        ]
        for module,parameters,files,field,expected in cases:
            with self.subTest(module=module):
                job=self.create(module,parameters)
                for slot,content in files.items():self.assertEqual(self.upload(job,slot=slot,data=content,filename=slot+'.csv').status_code,200)
                self.client.post(f'/api/jobs/{job}/run',headers=self.headers());result=self.wait_done(job)
                response=self.client.get(f"/api/jobs/{job}/downloads/{result['artifact']['artifact_id']}",headers=self.headers())
                with zipfile.ZipFile(BytesIO(response.content)) as z:
                    summary=json.loads(z.read('review/analysis/summary.json'))
                    self.assertEqual(summary['summary'][field],expected)
                self.client.delete('/api/jobs/'+job,headers=self.headers())

    def test_paid_ai_is_not_enabled_by_client_flag(self):
        job=self.create('kyc',{'company':'가상회사','start_date':'20250101','end_date':'20261031','with_ai':True})
        self.client.post(f'/api/jobs/{job}/run',headers=self.headers());result=self.wait_done(job)
        response=self.client.get(f"/api/jobs/{job}/downloads/{result['artifact']['artifact_id']}",headers=self.headers())
        with zipfile.ZipFile(BytesIO(response.content)) as z:
            self.assertIn('AI_DISABLED',z.read('review/analysis/validation_issues.csv').decode('utf-8-sig'))

    def test_timed_out_worker_is_stopped_and_returns_processing_issue(self):
        self.app.state.manager.max_run_seconds=0.01
        job=self.create();self.client.post(f'/api/jobs/{job}/run',headers=self.headers());result=self.wait_done(job)
        response=self.client.get(f"/api/jobs/{job}/downloads/{result['artifact']['artifact_id']}",headers=self.headers())
        with zipfile.ZipFile(BytesIO(response.content)) as z:
            self.assertEqual(json.loads(z.read('review/processing_issue.json'))['code'],'PROCESSING_TIMEOUT')

    def test_restart_recovery_exposes_interruption_not_fake_success(self):
        job=self.create();self.store.update_status(job,'running');self.app.state.manager.recover()
        result=self.client.get('/api/jobs/'+job,headers=self.headers()).json()
        response=self.client.get(f"/api/jobs/{job}/downloads/{result['artifact']['artifact_id']}",headers=self.headers())
        with zipfile.ZipFile(BytesIO(response.content)) as z:self.assertEqual(json.loads(z.read('review/processing_issue.json'))['code'],'SERVER_RESTARTED')

    def test_delete_during_execution_does_not_recreate_job_files(self):
        job=self.create();row=self.store.owned(job,self.store.authenticate(self.tokens['alice']));folder=self.store.job_path(row)
        self.client.post(f'/api/jobs/{job}/run',headers=self.headers())
        self.assertEqual(self.client.delete('/api/jobs/'+job,headers=self.headers()).status_code,204)
        self.assertFalse(folder.exists())
        self.assertEqual(self.client.get('/api/jobs/'+job,headers=self.headers()).status_code,404)

    def test_cleanup_failure_keeps_record_for_retry_and_access_stays_denied(self):
        job=self.create();row=self.store.owned(job,self.store.authenticate(self.tokens['alice']))
        folder=self.store.job_path(row);self.clock.now+=101
        with patch('backend.app.storage.shutil.rmtree',side_effect=PermissionError('blocked')):
            self.app.state.manager.cleanup()
        self.assertTrue(folder.exists())
        self.assertEqual(self.client.get('/api/jobs/'+job,headers=self.headers()).status_code,404)
        self.app.state.manager.cleanup();self.assertFalse(folder.exists())

    def test_minimal_events_do_not_contain_file_names_body_or_tokens(self):
        job=self.create();self.upload(job,data=b'PrivateField\nclient-secret-value\n',filename='sensitive-client-name.csv')
        with self.store.connection() as db:text=json.dumps([dict(r) for r in db.execute('SELECT * FROM events')])
        for sensitive in ['sensitive-client-name','client-secret-value',self.tokens['alice']]:self.assertNotIn(sensitive,text)

    def test_strict_ai_flag_and_unknown_parameters_are_rejected(self):
        for payload in [{'module':'kyc','parameters':{'with_ai':'false'}},{'module':'jet','parameters':{'api_key':'do-not-log'}}]:
            r=self.client.post('/api/jobs',json=payload,headers=self.headers());self.assertEqual(r.status_code,422)
            self.assertNotIn('do-not-log',r.text)

class AutomaticCleanupTests(unittest.TestCase):
    def test_periodic_cleanup_runs_without_user_request(self):
        with tempfile.TemporaryDirectory() as folder:
            clock=Clock()
            config=AppConfig(StorageConfig(Path(folder)/'private',job_ttl_seconds=1,token_ttl_seconds=100),cleanup_interval_seconds=.02)
            app=create_app(config,clock=clock);store=app.state.store
            token=store.issue_token('A','alice');principal=store.authenticate(token)
            with TestClient(app) as client:
                row=store.create_job(principal,'data_cleansing',{});directory=store.job_path(row)
                clock.now+=2
                deadline=time.monotonic()+2
                while directory.exists() and time.monotonic()<deadline:time.sleep(.01)
                self.assertFalse(directory.exists())
                self.assertEqual(client.get('/api/jobs/'+row['id'],headers={'Authorization':'Bearer '+token}).status_code,404)

    def test_startup_removes_previously_expired_jobs(self):
        with tempfile.TemporaryDirectory() as folder:
            clock=Clock();config=AppConfig(StorageConfig(Path(folder)/'private',job_ttl_seconds=1))
            app=create_app(config,clock=clock);store=app.state.store
            principal=store.authenticate(store.issue_token('A','alice'))
            row=store.create_job(principal,'data_cleansing',{});directory=store.job_path(row)
            clock.now+=2
            with TestClient(app):self.assertFalse(directory.exists())

class StorageRecoveryTests(unittest.TestCase):
    def test_startup_orphan_and_expired_event_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            clock=Clock();store=PrivateStore(StorageConfig(Path(folder)/'private',job_ttl_seconds=10,event_ttl_seconds=10),clock=clock)
            token=store.issue_token('A','alice',ttl=100);p=store.authenticate(token)
            job=store.create_job(p,'data_cleansing',{});path=store.job_path(job)
            with store.connection() as db:db.execute('DELETE FROM jobs WHERE id=?',(job['id'],))
            clock.now+=11;store.prune_and_orphans();self.assertFalse(path.exists())
            with store.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0],0)

    def test_multiple_servers_cannot_share_private_store(self):
        with tempfile.TemporaryDirectory() as folder:
            a=PrivateStore(StorageConfig(Path(folder)/'private'));b=PrivateStore(StorageConfig(Path(folder)/'private'))
            a.acquire_server_lock()
            try:
                with self.assertRaises(RuntimeError):b.acquire_server_lock()
            finally:a.release_server_lock()

    def test_xlsx_compression_limits_and_macros_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'input.xlsx'
            for member in ['xl/vbaProject.bin','xl/externalLinks/externalLink1.xml']:
                with zipfile.ZipFile(p,'w') as z:
                    z.writestr('[Content_Types].xml','<Types/>');z.writestr('xl/workbook.xml','<workbook/>');z.writestr(member,'bad')
                with self.assertRaises(ServiceError):validate_upload(p,'.xlsx')
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('[Content_Types].xml','<Types/>');z.writestr('xl/workbook.xml','<!DOCTYPE x [<!ENTITY y "bad">]><workbook/>')
            with self.assertRaises(ServiceError) as caught:validate_upload(p,'.xlsx')
            self.assertEqual(caught.exception.code,'UNSAFE_XML')
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('[Content_Types].xml','<Types/>');z.writestr('xl/workbook.xml','x'*1000)
            with self.assertRaises(ServiceError):validate_upload(p,'.xlsx',max_uncompressed=100)

if __name__=='__main__':unittest.main(verbosity=2)
