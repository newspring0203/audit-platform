from pathlib import Path
import sys,tempfile,unittest,json,zipfile,time
from io import BytesIO
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT))
import pandas as pd
from audit_data_lab import split_gl_by_user,execute_analysis
from audit_data_lab.traceability import attach_traceability
from backend.app.main import create_app,AppConfig
from backend.app.storage import StorageConfig
from fastapi.testclient import TestClient

class SplitGlTests(unittest.TestCase):
    def sample(self):return pd.DataFrame({'Journal_ID':['JE1','JE1','JE2','JE3','JE4','JE5'],'Entered_By':['001','Bob','001',None,'  ','../../=SUM(1)'],'Amount':['100','-100','0002','3','4','=1+1']})
    def test_partition_preserves_every_row_values_order_and_input(self):
        gl=self.sample();before=gl.copy(deep=True);r=split_gl_by_user(gl);index=r.tables['group_index']
        self.assertEqual(r.summary['input_row_count'],6);self.assertEqual(r.summary['exported_row_count'],6);self.assertEqual(index.Row_Count.sum(),6)
        self.assertEqual(r.summary['missing_user_row_count'],2);self.assertEqual(r.summary['user_group_count'],3)
        frames=[r.tables[name] for name in index.Group_ID];combined=pd.concat(frames).sort_values('Split_Source_Row').drop(columns='Split_Source_Row').reset_index(drop=True)
        pd.testing.assert_frame_equal(combined,gl);pd.testing.assert_frame_equal(gl,before)
        first=r.tables[index.iloc[0].Group_ID];self.assertEqual(first.Split_Source_Row.tolist(),[2,4]);self.assertEqual(first.Entered_By.tolist(),['001','001'])
    def test_missing_user_is_reported_and_partial_not_deleted(self):
        r=execute_analysis('gl_user_split',lambda:split_gl_by_user(self.sample()))
        self.assertEqual(r.metadata['execution_status'],'completed_with_limitations')
        self.assertEqual(r.tables['module_issues'].source_row.tolist(),[5,6]);self.assertEqual(len(r.tables['unassigned_user']),2)
    def test_safe_paths_and_export_formula_escaping(self):
        gl=self.sample();r=split_gl_by_user(gl)
        with tempfile.TemporaryDirectory() as tmp:
            r.save(tmp)
            for name in r.tables['group_index'].Output_File:self.assertTrue((Path(tmp)/name).is_file());self.assertNotIn('/',name)
            name=r.tables['group_index'].iloc[-1].Output_File
            exported=pd.read_csv(Path(tmp)/name,dtype='string')
            self.assertEqual(exported.Amount.iloc[0],"'=1+1");self.assertEqual(gl.Amount.iloc[-1],'=1+1')
    def test_missing_column_empty_and_group_limit_return_structured_issue(self):
        for frame,kwargs,code in [(pd.DataFrame({'X':[1]}),{},'MISSING_COLUMN'),(pd.DataFrame({'Entered_By':[]}),{},'EMPTY_INPUT'),(self.sample(),{'max_groups':1},'SPLIT_GROUP_LIMIT')]:
            result=execute_analysis('gl_user_split',lambda:split_gl_by_user(frame,**kwargs))
            self.assertEqual(result.tables['validation_issues'].iloc[0]['code'],code)
    def test_custom_column_and_similar_user_codes_not_merged(self):
        frame=pd.DataFrame({'User':['001','1',' A','A','a']});r=split_gl_by_user(frame,user_column='User');self.assertEqual(r.summary['user_group_count'],5)
    def test_source_rows_match_groups_and_output_records(self):
        gl=self.sample();r=split_gl_by_user(gl);manifest=attach_traceability(r,{'gl':gl},{},run_id='test')
        group=manifest['tables']['group_index']['rows'][0];self.assertEqual(manifest['trace'][group['review_id']]['sources'][0]['rows'],[2,4])
        detail=manifest['tables']['user_0001']['rows'][1];self.assertEqual(manifest['trace'][detail['review_id']]['sources'][0]['rows'],[4])

class SplitGlApiTests(unittest.TestCase):
    def test_real_job_zip_contains_user_files_and_matching_trace_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(AppConfig(StorageConfig(Path(tmp)/'runtime'),cleanup_interval_seconds=3600));token=app.state.store.issue_token('test','reviewer');h={'Authorization':'Bearer '+token}
            with TestClient(app) as client:
                features=client.get('/api/features',headers=h).json()['features'];self.assertIn('gl_user_split',[f['module'] for f in features])
                job=client.post('/api/jobs',headers=h,json={'module':'gl_user_split','parameters':{}}).json()['job_id'];base='/api/jobs/'+job
                self.assertEqual(client.put(base+'/inputs/gl',headers=h|{'X-Filename':'gl.csv'},content=b'Journal_ID,Entered_By,Amount\nJ1,A,100\nJ1,B,-100\nJ2,A,10\n').status_code,200)
                self.assertEqual(client.post(base+'/run',headers=h).status_code,202)
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    status=client.get(base,headers=h).json()
                    if status['status']=='completed':break
                    time.sleep(.05)
                self.assertEqual(status['status'],'completed')
                downloaded=client.get(base+'/downloads/'+status['artifact']['artifact_id'],headers=h)
                self.assertEqual(downloaded.status_code,200)
                with zipfile.ZipFile(BytesIO(downloaded.content)) as bundle:
                    self.assertIn('review/analysis/user_0001.csv',bundle.namelist());self.assertIn('review/analysis/user_0002.csv',bundle.namelist())
                    a=pd.read_csv(BytesIO(bundle.read('review/analysis/user_0001.csv')),dtype='string');self.assertEqual(a.Entered_By.tolist(),['A','A'])
                    manifest=json.loads(bundle.read('review/review_snapshot.json'));rid=manifest['tables']['user_0001']['rows'][0]['review_id'];self.assertEqual(a.Review_Record_ID.iloc[0],rid)
                trace=client.get(base+'/review/trace/'+rid,headers=h).json();self.assertEqual(trace['sources'][0]['rows'],[2])
