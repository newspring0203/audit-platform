import json
from pathlib import Path
import sys,tempfile,unittest
import pandas as pd
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from audit_data_lab.excel_reports import export_review_excel
from audit_data_lab.common import AnalysisResult
from audit_data_lab.validation import DataValidationError,ValidationIssue,save_validation_report

class CsvSafetyTests(unittest.TestCase):
    def test_download_copy_escapes_formulas_without_changing_analysis_or_negative_money(self):
        source=pd.DataFrame({'value':['=1+2','+SUM(1,2)','@SUM(1,2)','-1+2',' -1+2','\t=1+2','-100.00','00100']})
        before=source.copy(deep=True)
        r=AnalysisResult('test_report',{}, {'details':source})
        with tempfile.TemporaryDirectory() as folder:
            r.save(folder);saved=pd.read_csv(Path(folder)/'details.csv',dtype='string')
        self.assertTrue(saved['value'].iloc[:6].str.startswith("'").all())
        self.assertEqual(saved['value'].iloc[6],'-100.00')
        self.assertEqual(saved['value'].iloc[7],'00100')
        pd.testing.assert_frame_equal(source,before)
        self.assertEqual(r.to_dict()['tables']['details'][0]['value'],'=1+2')

    def test_excel_renderer_does_not_inherit_api_keys(self):
        result=AnalysisResult('jet',{}, {})
        with tempfile.TemporaryDirectory() as folder:
            modules=Path(folder)/'modules';modules.mkdir()
            with patch.dict('os.environ',{'OPENAI_API_KEY':'do-not-forward','DART_API_KEY':'do-not-forward'}):
                with patch('audit_data_lab.excel_reports.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='',stderr='')) as run:
                    export_review_excel(result,Path(folder)/'report.xlsx',entity='가상회사',period='2007',node_executable='/test/node',artifact_modules=modules)
                    self.assertNotIn('OPENAI_API_KEY',run.call_args.kwargs['env'])
                    self.assertNotIn('DART_API_KEY',run.call_args.kwargs['env'])

    def test_error_csv_also_escapes_untrusted_values(self):
        issue=ValidationIssue(code='INVALID_AMOUNT',field='Amount',message='금액 오류',source_table='GL',source_file='GL',value='=WEBSERVICE("https://invalid.example")')
        with tempfile.TemporaryDirectory() as folder:
            save_validation_report(folder,DataValidationError([issue]))
            saved=pd.read_csv(Path(folder)/'validation_errors.csv',dtype='string')
            self.assertTrue(saved['value'].iloc[0].startswith("'="))
            original=json.loads((Path(folder)/'validation_errors.json').read_text())
            self.assertEqual(original['errors'][0]['value'],issue.value)

if __name__=='__main__':unittest.main(verbosity=2)
