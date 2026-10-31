"""미확인 기준으로 금액 대사를 실행하지 않는지 확인한다."""
from dataclasses import replace
import hashlib,json
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from audit_data_lab import run_jet,adapt_legacy_log
from audit_data_lab.reconciliation_basis import EvidenceFile,LogBasisConfirmation,frame_fingerprint
from audit_data_lab.validation import DataValidationError
from test_analysis_features import gl_sample,log_ads,log_sample


def fixture_confirmation(gl,log,folder,**changes):
    """가상 데이터 전용. 실제 회사의 확인 근거로 사용하지 않는다."""
    file=Path(folder)/'test_only_definition.txt'
    file.write_text('TEST ONLY: synthetic company 3000, year 2007, ledger 0; both fields DMBTR, functional USD.',encoding='utf-8')
    c=LogBasisConfirmation(gl_source_amount_field='DMBTR',log_source_amount_field='DMBTR',
        gl_currency_basis='functional',log_currency_basis='functional',company='3000',fiscal_year='2007',ledger='0',
        period_start='20070101',period_end='20071231',extraction_description='가상 데이터 테스트 전용 추출 범위',
        gl_fingerprint=frame_fingerprint(gl),log_fingerprint=frame_fingerprint(log),
        confirmed_by='가상 자료 담당자',reviewed_by='가상 검토자',reviewed_at='2026-10-31',currency_mode='row_currency',
        evidence_files=(EvidenceFile(file.name,hashlib.sha256(file.read_bytes()).hexdigest(),'가상 테스트용 필드 명세'),))
    return replace(c,**changes)

class LogBasisTests(unittest.TestCase):
    def test_default_blocks_even_if_currency_column_exists_and_amounts_match(self):
        r=run_jet(gl_sample(),log_ads())
        self.assertEqual(r.summary['log_amount_reconciliation_status'],'basis_information_missing')
        self.assertIsNone(r.summary['log_control_exception_count'])
        self.assertIsNone(r.summary['log_population_difference_count'])
        self.assertTrue(r.tables['log_control_exceptions'].empty)
        self.assertEqual(r.tables['log_basis_issues']['code'].iloc[0],'BASIS_INFORMATION_MISSING')
        self.assertGreater(r.summary['rules']['NIGHT_ENTRY']['row_count'],0)
        self.assertGreater(r.summary['rules']['WEEKEND_ENTRY']['row_count'],0)
        self.assertIsNone(json.loads(json.dumps(r.to_dict(),allow_nan=False))['summary']['log_control_exception_count'])

    def test_legacy_adapter_does_not_invent_currency(self):
        original=log_sample();before=original.copy(deep=True)
        out=adapt_legacy_log(original,company='3000',fiscal_year='2007')
        self.assertNotIn('Amount_Currency',out)
        pd.testing.assert_frame_equal(original,before)
        self.assertEqual(run_jet(gl_sample(),out).summary['log_amount_reconciliation_status'],'basis_information_missing')

    def test_old_currency_argument_is_rejected(self):
        with self.assertRaises(DataValidationError) as caught:adapt_legacy_log(log_sample(),company='3000',fiscal_year='2007',currency='USD')
        self.assertEqual(caught.exception.issues[0].code,'UNVERIFIED_CURRENCY_OVERRIDE')

    def test_checkbox_or_incomplete_record_cannot_enable_reconciliation(self):
        for confirmation in [True,{'confirmed':True,'currency':'USD'},LogBasisConfirmation()]:
            with self.subTest(confirmation=confirmation):
                r=run_jet(gl_sample(),log_ads(),log_basis=confirmation)
                self.assertEqual(r.summary['log_amount_reconciliation_status'],'basis_information_missing')
                self.assertIsNone(r.summary['log_control_exception_count'])

    def test_real_evidence_and_review_record_enable_matching(self):
        g,l=gl_sample(),log_ads()
        with tempfile.TemporaryDirectory() as folder:
            c=fixture_confirmation(g,l,folder)
            r=run_jet(g,l,log_basis=c,evidence_root=folder)
        self.assertEqual(r.summary['log_amount_reconciliation_status'],'matched')
        self.assertEqual(r.summary['log_control_exception_count'],0)
        self.assertEqual(r.metadata['log_basis_confirmation']['reviewed_by'],'가상 검토자')

    def test_confirmed_difference_is_reported_not_hidden_by_tolerance(self):
        g,l=gl_sample(),log_ads();l.loc[0,'Total']='100.02'
        with tempfile.TemporaryDirectory() as folder:
            r=run_jet(g,l,log_basis=fixture_confirmation(g,l,folder),evidence_root=folder)
        self.assertEqual(r.summary['log_amount_reconciliation_status'],'differences_found')
        self.assertEqual(r.tables['log_control_exceptions']['Difference_Cents'].tolist(),[-2])

    def test_changed_gl_or_log_needs_new_review(self):
        for which in ['GL','Log']:
            g,l=gl_sample(),log_ads()
            with tempfile.TemporaryDirectory() as folder:
                c=fixture_confirmation(g,l,folder)
                if which=='GL':g.loc[0,'Amount']='101.00'
                else:l.loc[0,'Total']='101.00'
                r=run_jet(g,l,log_basis=c,evidence_root=folder)
            self.assertEqual(r.summary['log_amount_reconciliation_status'],'basis_evidence_invalid')
            self.assertIn('REVIEWED_INPUT_CHANGED',r.tables['log_basis_issues']['code'].tolist())
            self.assertIsNone(r.summary['log_control_exception_count'])

    def test_missing_or_changed_evidence_blocks(self):
        for action in ['delete','change']:
            g,l=gl_sample(),log_ads()
            with tempfile.TemporaryDirectory() as folder:
                c=fixture_confirmation(g,l,folder)
                p=Path(folder)/c.evidence_files[0].relative_path
                if action=='delete':p.unlink()
                else:p.write_text('changed')
                r=run_jet(g,l,log_basis=c,evidence_root=folder)
            self.assertEqual(r.summary['log_amount_reconciliation_status'],'basis_evidence_invalid')

    def test_different_amount_or_currency_basis_blocks(self):
        g,l=gl_sample(),log_ads()
        for changes in [{'log_source_amount_field':'PSWBT'},{'log_currency_basis':'transaction'}]:
            with tempfile.TemporaryDirectory() as folder:
                c=fixture_confirmation(g,l,folder,**changes)
                r=run_jet(g,l,log_basis=c,evidence_root=folder)
            self.assertEqual(r.summary['log_amount_reconciliation_status'],'basis_not_comparable')
            self.assertIsNone(r.summary['log_control_exception_count'])

    def test_scope_mismatch_blocks(self):
        g,l=gl_sample(),log_ads()
        with tempfile.TemporaryDirectory() as folder:
            c=fixture_confirmation(g,l,folder,company='4000')
            r=run_jet(g,l,log_basis=c,evidence_root=folder)
        self.assertIn('BASIS_SCOPE_MISMATCH',r.tables['log_basis_issues']['code'].tolist())

    def test_currency_missing_needs_explicit_verified_single_currency(self):
        g=gl_sample();l=adapt_legacy_log(log_sample(),company='3000',fiscal_year='2007')
        with tempfile.TemporaryDirectory() as folder:
            c=fixture_confirmation(g,l,folder)
            blocked=run_jet(g,l,log_basis=c,evidence_root=folder)
            self.assertEqual(blocked.summary['log_amount_reconciliation_status'],'basis_information_missing')
            c=replace(c,currency_mode='confirmed_single_currency',confirmed_currency='USD')
            matched=run_jet(g,l,log_basis=c,evidence_root=folder)
        self.assertEqual(matched.summary['log_amount_reconciliation_status'],'matched')
        self.assertNotIn('Amount_Currency',l)

    def test_existing_currency_is_never_overwritten(self):
        g,l=gl_sample(),log_ads();l['Amount_Currency']='EUR'
        with tempfile.TemporaryDirectory() as folder:
            c=fixture_confirmation(g,l,folder,currency_mode='confirmed_single_currency',confirmed_currency='USD')
            r=run_jet(g,l,log_basis=c,evidence_root=folder)
        self.assertIn('LOG_CURRENCY_CONFLICT',r.tables['log_basis_issues']['code'].tolist())
        self.assertEqual(l['Amount_Currency'].unique().tolist(),['EUR'])

    def test_evidence_path_cannot_escape_root(self):
        g,l=gl_sample(),log_ads()
        with tempfile.TemporaryDirectory() as folder:
            c=fixture_confirmation(g,l,folder)
            e=replace(c.evidence_files[0],relative_path='../outside.txt')
            r=run_jet(g,l,log_basis=replace(c,evidence_files=(e,)),evidence_root=folder)
        self.assertIn('INVALID_EVIDENCE_PATH',r.tables['log_basis_issues']['code'].tolist())

    def test_nondefault_dataframe_index_is_supported(self):
        g,l=gl_sample(),log_ads();g.index=[9,20];l.index=[15,30]
        with tempfile.TemporaryDirectory() as folder:
            c=fixture_confirmation(g,l,folder)
            r=run_jet(g,l,log_basis=c,evidence_root=folder)
        self.assertEqual(r.summary['log_amount_reconciliation_status'],'matched')

    def test_unconfirmed_log_amounts_are_not_compared(self):
        l=log_ads();l.loc[0,'Total']='bad'
        with patch('audit_data_lab.jet.money',wraps=__import__('audit_data_lab.jet',fromlist=['money']).money) as convert:
            r=run_jet(gl_sample(),l)
            self.assertFalse(any(len(c.args)>1 and c.args[1]=='Total' for c in convert.call_args_list))
        self.assertEqual(r.summary['log_amount_reconciliation_status'],'basis_information_missing')

if __name__=='__main__':unittest.main(verbosity=2)
