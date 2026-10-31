"""문제가 있어도 원인·후속 검토를 담은 산출물을 만들 수 있는지 확인한다."""
import json
from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from audit_data_lab import execute_analysis,execute_batch,run_jet,generate_working_paper
from audit_data_lab.common import fail
from audit_data_lab.excel_reports import build_review_payload
from test_analysis_features import gl_sample,log_ads

class ReviewServiceTests(unittest.TestCase):
    def test_missing_basis_is_a_partial_result_and_exportable(self):
        r=execute_analysis('jet',lambda:run_jet(gl_sample(),log_ads()))
        self.assertEqual(r.metadata['execution_status'],'completed_with_limitations')
        payload=build_review_payload(r,entity='가상회사',period='2007')
        self.assertEqual(payload['summary'][-1][1],None)
        self.assertGreater(len(payload['tables']['검토대상']['records']),0)
        self.assertEqual(payload['issues'][0]['오류 코드'],'BASIS_INFORMATION_MISSING')
        json.dumps(payload,allow_nan=False)
        with tempfile.TemporaryDirectory() as folder:
            p=generate_working_paper(r,Path(folder)/'paper',entity='가상회사',period='2007',prepared_by='테스트')
            self.assertIn('로그 대사 미실행',p.read_text())

    def test_input_error_returns_report_instead_of_raising(self):
        r=execute_analysis('analytical_review',lambda:fail('COMPARISON_PERIOD_MISSING','Fiscal_Year','전기 자료가 없습니다.'))
        self.assertEqual(r.metadata['execution_status'],'not_executed_input_issue')
        self.assertFalse(r.summary['calculation_performed'])
        self.assertIn('두 기간',r.tables['validation_issues']['suggested_review'].iloc[0])
        with tempfile.TemporaryDirectory() as folder:
            p=generate_working_paper(r,Path(folder)/'paper',entity='가상회사',period='2007',prepared_by='테스트')
            self.assertIn('계산 미실행',p.read_text())
            self.assertTrue((p.parent/'analysis/validation_issues.csv').exists())

    def test_missing_file_returns_input_issue(self):
        def missing():raise FileNotFoundError('/private/internal/file.csv')
        r=execute_analysis('jet',missing)
        self.assertEqual(r.tables['validation_issues']['code'].iloc[0],'INPUT_FILE_UNAVAILABLE')
        self.assertNotIn('/private/internal',json.dumps(r.to_dict()))

    def test_internal_error_does_not_expose_secrets(self):
        def internal():raise RuntimeError('key=secret-token, path=/private/internal')
        r=execute_analysis('jet',internal)
        self.assertEqual(r.metadata['execution_status'],'not_executed_system_issue')
        self.assertNotIn('secret-token',json.dumps(r.to_dict()))

    def test_one_module_failure_does_not_cancel_other_results(self):
        results=execute_batch({'analytical_review':lambda:fail('COMPARISON_PERIOD_MISSING','Fiscal_Year','자료 없음'),
            'jet':lambda:run_jet(gl_sample(),log_ads())})
        self.assertEqual(set(results),{'jet','analytical_review'})
        self.assertEqual(results['analytical_review'].metadata['execution_status'],'not_executed_input_issue')
        self.assertGreater(results['jet'].summary['rule_hit_count'],0)

    def test_excel_payload_has_editable_review_fields_without_false_zero(self):
        r=execute_analysis('jet',lambda:fail('MISSING_COLUMN','Amount','금액 컬럼 없음'))
        p=build_review_payload(r,entity='가상회사',period='2007')
        self.assertIn('계산 미실행',p['execution_status'])
        self.assertEqual(p['issues'][0]['검토 상태'],'미검토')
        self.assertEqual(p['tables']['검토대상']['records'],[])
        self.assertTrue(all(v is None for k,v in p['summary'] if k=='입력 상세행'))
        json.dumps(p,allow_nan=False)

if __name__=='__main__':unittest.main(verbosity=2)
