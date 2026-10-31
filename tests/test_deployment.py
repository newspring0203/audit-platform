"""Deployment boundary tests using only synthetic inputs and HTTPS cookies."""
from pathlib import Path
from io import BytesIO
import os, sys, tempfile, time, unittest, zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.config import AppConfig
from backend.app.storage import StorageConfig
from backend.app.demo import COOKIE, FIXTURES

ORIGIN='https://demo.example.test'
HEADERS={'Origin':ORIGIN,'X-Audit-Request':'1'}

class DeploymentTests(unittest.TestCase):
    def make_app(self, tmp, **kwargs):
        return create_app(AppConfig(StorageConfig(Path(tmp)/'runtime'), mode='demo', public_origin=ORIGIN, requests_per_minute=10000, **kwargs))

    def test_cookie_csrf_upload_and_external_module_boundaries(self):
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
                self.assertEqual({f['module'] for f in features},set(FIXTURES))
                self.assertEqual(client.post('/api/jobs',headers=HEADERS,json={'module':'kyc','parameters':{}}).status_code,403)
                self.assertEqual(client.post('/api/jobs',headers=HEADERS,json={'module':'sap_preprocessing','parameters':{}}).status_code,403)
                self.assertEqual(client.put('/api/jobs/'+'a'*32+'/inputs/gl',headers=HEADERS,content=b'real data').status_code,403)
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
                        response=alice.post('/api/jobs',headers=HEADERS,json={'module':module,'parameters':{}})
                        self.assertEqual(response.status_code,201,response.text)
                        job=response.json();base='/api/jobs/'+job['job_id']
                        self.assertEqual(job['parameters'],fixture['parameters'])
                        self.assertEqual(bob.get(base).status_code,404)
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

    def test_deployment_env_fails_closed_and_disables_ai(self):
        with patch.dict(os.environ,{'AUDIT_MODE':'demo'},clear=True):
            with self.assertRaises(ValueError):AppConfig.from_env()
        with patch.dict(os.environ,{'AUDIT_MODE':'demo','AUDIT_PUBLIC_ORIGIN':ORIGIN,'AUDIT_ALLOW_AI':'true'},clear=True):
            config=AppConfig.from_env()
            self.assertFalse(config.allow_ai)
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
