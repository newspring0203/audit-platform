"""Deployment boundary tests using only synthetic inputs and HTTPS cookies."""
from pathlib import Path
from io import BytesIO
import os, sys, tempfile, time, unittest, zipfile, json
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.config import AppConfig
from backend.app.storage import StorageConfig
from backend.app.demo import COOKIE
from backend.app.contracts import MODULES
FIXTURES=json.loads((ROOT/'data/demo/cases.json').read_text())

ORIGIN='https://demo.example.test'
HEADERS={'Origin':ORIGIN,'X-Audit-Request':'1'}

class DeploymentTests(unittest.TestCase):
    def make_app(self, tmp, **kwargs):
        return create_app(AppConfig(StorageConfig(Path(tmp)/'runtime'), mode='demo', public_origin=ORIGIN, requests_per_minute=10000, **kwargs))

    def test_cookie_csrf_and_all_modules_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=self.make_app(tmp)
            with TestClient(app, base_url=ORIGIN) as client:
                self.assertEqual(client.get('/api/features').status_code,401)
                self.assertEqual(client.post('/demo/session').status_code,403)
                self.assertEqual(client.post('/demo/session',headers=HEADERS|{'Origin':'https://evil.example'}).status_code,403)
                response=client.post('/demo/session',headers=HEADERS)
                self.assertEqual(response.json(),{'status':'connected'})
                cookie=response.headers['set-cookie']
                for flag in ['HttpOnly','Secure','SameSite=strict','Path=/','Max-Age=3600']: self.assertIn(flag,cookie)
                token=client.cookies.get(COOKIE)
                self.assertNotIn(token,response.text)
                self.assertEqual(client.post('/demo/session',headers=HEADERS).status_code,200)
                self.assertEqual(client.cookies.get(COOKIE),token)
                features=client.get('/api/features').json()['features']
                self.assertEqual({f['module'] for f in features},set(MODULES))
                self.assertEqual(client.post('/api/jobs',headers=HEADERS,json={'module':'kyc','parameters':{}}).status_code,201)
                self.assertEqual(client.post('/api/jobs',headers=HEADERS,json={'module':'sap_preprocessing','parameters':{}}).status_code,201)
                self.assertEqual(client.put('/api/jobs/'+'a'*32+'/inputs/gl',headers=HEADERS,content=b'not-a-real-file').status_code,404)
                self.assertEqual(client.post('/api/logout',headers=HEADERS).status_code,204)
                self.assertEqual(client.get('/api/features').status_code,401)
                self.assertEqual(app.state.store.connection is not None,True)

    def test_all_demo_modules_download_isolation_and_deleted_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=self.make_app(tmp)
            bob=TestClient(app,base_url=ORIGIN)
            self.addCleanup(bob.close)
            with TestClient(app,base_url=ORIGIN) as alice:
                self.assertEqual(alice.post('/demo/session',headers=HEADERS).status_code,200)
                self.assertEqual(bob.post('/demo/session',headers=HEADERS).status_code,200)
                for module,fixture in FIXTURES.items():
                    with self.subTest(module=module):
                        response=alice.post('/api/jobs',headers=HEADERS,json={'module':module,'parameters':fixture['parameters']})
                        self.assertEqual(response.status_code,201,response.text)
                        job=response.json();base='/api/jobs/'+job['job_id']
                        self.assertEqual(job['parameters'],fixture['parameters'])
                        self.assertEqual(bob.get(base).status_code,404)
                        self.assertEqual(job['uploaded_slots'],[])
                        for slot,name in fixture['inputs'].items():
                            data=(ROOT/'data/demo'/name).read_bytes()
                            response=alice.put(base+'/inputs/'+slot,headers=HEADERS|{'X-Filename':Path(name).name},content=data)
                            self.assertEqual(response.status_code,200,response.text)
                            self.assertEqual(bob.put(base+'/inputs/'+slot,headers=HEADERS|{'X-Filename':Path(name).name},content=data).status_code,404)
                        self.assertEqual(alice.post(base+'/run',headers=HEADERS).status_code,202)
                        deadline=time.monotonic()+20
                        while time.monotonic()<deadline:
                            job=alice.get(base).json()
                            if job['status']=='completed':break
                            time.sleep(.05)
                        self.assertEqual(job['status'],'completed')
                        review=alice.get(base+'/review')
                        self.assertEqual(review.status_code,200,review.text)
                        download=base+'/downloads/'+job['artifact']['artifact_id']
                        self.assertEqual(bob.get(download).status_code,404)
                        response=alice.get(download)
                        self.assertEqual(response.status_code,200)
                        with zipfile.ZipFile(BytesIO(response.content)) as archive:
                            self.assertIsNone(archive.testzip())
                            self.assertIn('review/analysis/summary.json',archive.namelist())
                            self.assertNotIn('review/processing_issue.json',archive.namelist())
                        self.assertEqual(alice.delete(base,headers=HEADERS).status_code,204)
                        self.assertEqual(alice.get(download).status_code,404)

    def test_session_limit_and_expired_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=self.make_app(tmp,max_demo_sessions=1)
            with TestClient(app,base_url=ORIGIN) as client:
                self.assertEqual(client.post('/demo/session',headers=HEADERS).status_code,200)
                client.cookies.clear()
                self.assertEqual(client.post('/demo/session',headers=HEADERS).status_code,429)
                with app.state.store.connection() as db: db.execute('UPDATE tokens SET expires=0')
                self.assertEqual(client.post('/demo/session',headers=HEADERS).status_code,200)
                with app.state.store.connection() as db: db.execute('UPDATE tokens SET expires=0')
                self.assertEqual(client.get('/api/features').status_code,401)

    def test_deployment_env_fails_closed_and_ai_requires_explicit_setting(self):
        with patch.dict(os.environ,{'AUDIT_MODE':'demo'},clear=True):
            with self.assertRaises(ValueError):AppConfig.from_env()
        with patch.dict(os.environ,{'AUDIT_MODE':'demo','AUDIT_PUBLIC_ORIGIN':ORIGIN,'AUDIT_ALLOW_AI':'true'},clear=True):
            config=AppConfig.from_env()
            self.assertTrue(config.allow_ai)
            self.assertEqual(config.storage.root,Path('/tmp/audit-platform'))
        with patch.dict(os.environ,{'AUDIT_MODE':'demo','AUDIT_PUBLIC_ORIGIN':ORIGIN,'AUDIT_ANALYSIS_WORKERS':'0'},clear=True):
            with self.assertRaises(ValueError):AppConfig.from_env()

    def test_expired_job_is_inaccessible_and_cleanup_removes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=self.make_app(tmp)
            with TestClient(app,base_url=ORIGIN) as client:
                client.post('/demo/session',headers=HEADERS)
                job=client.post('/api/jobs',headers=HEADERS,json={'module':'cash_proofing','parameters':{}}).json()
                path=app.state.store.job_path(app.state.store._row(job['job_id']))
                with app.state.store.connection() as db:db.execute('UPDATE jobs SET expires=0')
                self.assertEqual(client.get('/api/jobs/'+job['job_id']).status_code,404)
                app.state.manager.cleanup()
                self.assertFalse(path.exists())

    def test_user_parameters_are_preserved_and_no_inputs_are_injected(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=self.make_app(tmp)
            with TestClient(app,base_url=ORIGIN) as client:
                client.post('/demo/session',headers=HEADERS)
                params={'date_tolerance_days':7,'as_of':'20261015','aging_days':14}
                response=client.post('/api/jobs',headers=HEADERS,json={'module':'cash_proofing','parameters':params})
                self.assertEqual(response.status_code,201)
                self.assertEqual(response.json()['parameters'],params)
                self.assertEqual(response.json()['uploaded_slots'],[])

    def test_dart_key_is_job_scoped_and_not_persisted(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            app=self.make_app(tmp)
            with TestClient(app,base_url=ORIGIN) as client:
                client.post('/demo/session',headers=HEADERS)
                params={'company':'가상회사','start_date':'20260101','end_date':'20261031','with_ai':False}
                job=client.post('/api/jobs',headers=HEADERS,json={'module':'kyc','parameters':params}).json()
                base='/api/jobs/'+job['job_id']
                self.assertEqual(client.post(base+'/run',headers=HEADERS).status_code,422)
                invalid='never-print-this-value'
                response=client.post(base+'/run',headers=HEADERS,json={'dart_api_key':invalid})
                self.assertEqual(response.status_code,422);self.assertNotIn(invalid,response.text)
                key='V'*40
                row=app.state.store._row(job['job_id'])
                with patch.object(app.state.manager,'start',return_value=row) as start:
                    response=client.post(base+'/run',headers=HEADERS,json={'dart_api_key':key})
                    self.assertEqual(response.status_code,202)
                    self.assertEqual(start.call_args.kwargs['dart_api_key'],key)
                self.assertNotIn(key,response.text)
                self.assertNotIn(key,client.get(base).text)
                for path in Path(tmp).rglob('*'):
                    if path.is_file():self.assertNotIn(key.encode(),path.read_bytes(),str(path))
                response=client.post('/api/jobs',headers=HEADERS,json={'module':'kyc','parameters':params|{'dart_api_key':key}})
                self.assertEqual(response.status_code,422);self.assertNotIn(key,response.text)

    def test_worker_uses_supplied_key_and_omits_it_from_all_artifacts(self):
        from backend.app.worker import run
        from test_kyc_integration import fake_dart, CORP
        from audit_data_lab.kyc_live import run_live_kyc
        key='V'*40
        def provider(*args,**kwargs):
            self.assertEqual(kwargs['settings'].dart_api_key,key)
            return run_live_kyc(*args,**kwargs,dart_transport=fake_dart)
        with tempfile.TemporaryDirectory() as tmp:
            spec={'directory':tmp,'job_id':'test-visitor-key','module':'kyc','inputs':{},'parameters':{'company':CORP,'start_date':'20250101','end_date':'20261031','with_ai':False},'allow_ai':False}
            with patch('audit_data_lab.kyc_live.run_live_kyc',side_effect=provider):run(spec,dart_api_key=key)
            for path in Path(tmp).rglob('*'):
                if path.is_file():self.assertNotIn(key.encode(),path.read_bytes(),str(path))
            with zipfile.ZipFile(Path(tmp)/'bundle.zip') as archive:
                for name in archive.namelist():self.assertNotIn(key.encode(),archive.read(name),name)

    def test_key_reaches_only_worker_stdin_not_argv_env_or_spec(self):
        from unittest.mock import patch
        import io,subprocess
        class FakeProcess:
            pid=999999
            returncode=0
            def __init__(self):self.stdin=io.BytesIO();self.received=None
            def wait(self,timeout=None):return 0
        key='V'*40
        with tempfile.TemporaryDirectory() as tmp:
            app=self.make_app(tmp)
            token=app.state.store.issue_token('test','test')
            principal=app.state.store.authenticate(token)
            row=app.state.store.create_job(principal,'kyc',{'company':'가상회사'})
            app.state.store.update_status(row['id'],'queued')
            received=[]
            class Pipe:
                def write(self,value):received.append(value)
                def close(self):pass
            process=FakeProcess();process.stdin=Pipe()
            with patch('backend.app.jobs.subprocess.Popen',return_value=process) as popen:
                with patch.object(app.state.store,'finalize',return_value=True):
                    app.state.manager._execute(row['id'],dart_api_key=key)
            self.assertEqual(received,[key.encode()])
            self.assertEqual(popen.call_args.kwargs['stdin'],subprocess.PIPE)
            self.assertNotIn(key,str(popen.call_args.args))
            self.assertNotIn(key,str(popen.call_args.kwargs['env']))
            self.assertNotIn('DART_API_KEY',popen.call_args.kwargs['env'])
            for path in Path(tmp).rglob('*'):
                if path.is_file():self.assertNotIn(key.encode(),path.read_bytes())
            app.state.manager.shutdown()
