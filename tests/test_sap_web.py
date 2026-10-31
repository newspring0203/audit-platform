from pathlib import Path
import sys,json,tempfile,unittest,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
import pandas as pd
from fastapi.testclient import TestClient
from backend.app.main import create_app,AppConfig
from backend.app.storage import StorageConfig
from backend.app.worker import run
from audit_data_lab.sap import convert_sap_data
from audit_data_lab.validation import DataValidationError
import test_sap_to_ads as sap_notebook_tests
fixtures=sap_notebook_tests.fixtures

class SapWebTests(unittest.TestCase):
    def test_web_function_matches_notebook_gl_tb_and_reconciliation(self):
        b,h,t=fixtures();before=b.copy(deep=True)
        result=convert_sap_data(b,h,t,company='3000',year='2007')
        sap_notebook_tests.SapToAdsTests.setUpClass()
        notebook=sap_notebook_tests.SapToAdsTests();expected=notebook.run_pipeline(b,h,t)
        try:
            for name,var in [('gl','gl'),('tb','tb'),('gl_tb_reconciliation','reconciliation')]:
                pd.testing.assert_frame_equal(result.tables[name],expected[var])
            pd.testing.assert_frame_equal(b,before)
            self.assertEqual(result.tables['sap_lineage']['BSEG_Source_Row'].tolist(),[2,3])
        finally:notebook.doCleanups()

    def test_missing_sap_columns_are_reported(self):
        b,h,t=fixtures()
        with self.assertRaises(DataValidationError):convert_sap_data(b.drop(columns=b.columns[-1]),h,t,company='3000',year='2007')

    def test_browser_api_upload_txt_execute_review_and_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            app=create_app(AppConfig(StorageConfig(Path(temp)/'runtime'),cleanup_interval_seconds=3600))
            token=app.state.store.issue_token('demo','reviewer');headers={'Authorization':'Bearer '+token}
            with TestClient(app) as client:
                features=client.get('/api/features',headers=headers)
                self.assertEqual(features.status_code,200)
                self.assertTrue(any(f['module']=='sap_preprocessing' for f in features.json()['features']))
                params={'company':'3000','fiscal_year':'2007','ledger':'0','record_type':'0','version':'1'}
                created=client.post('/api/jobs',json={'module':'sap_preprocessing','parameters':params},headers=headers)
                self.assertEqual(created.status_code,201,created.text)
                job=created.json()['job_id'];base='/api/jobs/'+job
                for slot,frame in zip(['bseg','bkpf','glt0'],fixtures()):
                    suffix='txt' if slot=='bkpf' else 'csv';sep='|' if slot=='bkpf' else ','
                    response=client.put(base+'/inputs/'+slot,content=frame.to_csv(index=False,sep=sep).encode(),headers=headers|{'X-Filename':slot+'.'+suffix})
                    self.assertEqual(response.status_code,200,response.text)
                store=app.state.store;row=store.owned(job,store.authenticate(token));folder=store.job_path(row)
                run({'directory':str(folder),'parameters':params,'inputs':json.loads(row['inputs']),'module':'sap_preprocessing','job_id':job})
                store.finalize(job)
                review=client.get(base+'/review',headers=headers).json()
                self.assertEqual(review['summary']['gl_output_rows'],2)
                self.assertEqual(review['summary']['tb_output_rows'],32)
                self.assertEqual(review['metadata']['execution_status'],'completed')
                table=client.get(base+'/review/tables/gl',headers=headers).json()
                trace=client.get(base+'/review/trace/'+table['rows'][0]['review_id'],headers=headers).json()
                self.assertEqual({ref['slot'] for ref in trace['sources']},{'bseg','bkpf'})
                with zipfile.ZipFile(folder/'bundle.zip') as archive:
                    names=archive.namelist()
                    self.assertTrue(any(n.endswith('/gl.csv') for n in names))
                    self.assertTrue(any(n.endswith('/tb.csv') for n in names))
