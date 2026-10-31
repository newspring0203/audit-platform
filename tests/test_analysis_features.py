"""작은 정답 데이터로 7개 모듈의 계산·오류·보고 동작을 확인한다."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
# staging 및 최종 프로젝트 모두에서 같은 테스트를 실행할 수 있다.
sys.path.insert(0,str(ROOT/'src') if (ROOT/'src').is_dir() else str(ROOT))
from audit_data_lab import (JetConfig, adapt_legacy_log, run_jet, analytical_review,
    cash_proofing, inventory_analysis, profile_data, kyc_review, generate_working_paper, FEATURES)
from audit_data_lab.validation import DataValidationError

def gl_sample():
    return pd.DataFrame([
        {'Journal_ID':'3000:2007:0001','Journal_ID_Line_Number':'001','GL_Account_Number':'0100',
         'Business_Unit_Code':'3000:01','Fiscal_Year':'2007','Period':'01','Amount':'100.00',
         'Amount_Currency':'USD','Amount_Credit_Debit_Indicator':'D','Effective_Date':'20070131',
         'Entered_Date':'20070203','Entered_Time':'2100','Entered_By':'u1','Source':'SA'},
        {'Journal_ID':'3000:2007:0001','Journal_ID_Line_Number':'002','GL_Account_Number':'0400',
         'Business_Unit_Code':'3000:01','Fiscal_Year':'2007','Period':'01','Amount':'100.00',
         'Amount_Currency':'USD','Amount_Credit_Debit_Indicator':'C','Effective_Date':'20070131',
         'Entered_Date':'20070203','Entered_Time':'2100','Entered_By':'u1','Source':'SA'},
    ])

def log_sample():
    return pd.DataFrame({'Journal_ID':['0001','0001'],'Amount_Credit_Debit_Indicator':['S','H'],'Total':['100.00','100.00']})

def log_ads():
    result=log_sample()
    result['Journal_ID']='3000:2007:'+result['Journal_ID']
    result['Amount_Credit_Debit_Indicator']=result['Amount_Credit_Debit_Indicator'].map({'S':'D','H':'C'})
    result['Amount_Currency']='USD'
    return result

# 기존 계산 테스트는 가상 데이터 전용 확인 근거로 명시적으로 실행한다.
_original_run_jet=run_jet
def run_jet(gl,log,config=None):
    from test_log_basis import fixture_confirmation
    with tempfile.TemporaryDirectory() as folder:
        confirmation=fixture_confirmation(gl,log,folder)
        return _original_run_jet(gl,log,config,log_basis=confirmation,evidence_root=folder)


class AnalysisFeatureTests(unittest.TestCase):
    def test_registered_features_have_unique_ids_and_explicit_status(self):
        ids=[f['id'] for f in FEATURES]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue({'jet','analytical_review','working_paper','kyc','cash_proofing','inventory','data_cleansing','gl_user_split','quickbooks_preprocessing'}<=set(ids))
        self.assertTrue(all(f.get('status') and f.get('entrypoint') for f in FEATURES))
        self.assertEqual(next(f for f in FEATURES if f['id']=='kyc')['status'],'credentials_required')

    def test_log_adapter_preserves_zeros_and_maps_dc(self):
        result=adapt_legacy_log(log_sample(),company='3000',fiscal_year='2007');self.assertEqual(result['Journal_ID'].iloc[0],'3000:2007:0001')
        self.assertNotIn('Amount_Currency',result)
        self.assertEqual(result['Amount_Credit_Debit_Indicator'].tolist(),['D','C'])
        self.assertEqual(log_sample()['Journal_ID'].iloc[0],'0001')

    def test_jet_population_balances_and_rule_reasons(self):
        r=run_jet(gl_sample(),log_ads(),JetConfig(round_unit=100,large_amounts={'USD':100},manual_sources=('SA',),closing_dates=('20070131',)))
        self.assertEqual(r.summary['log_population_difference_count'],0)
        self.assertEqual(r.summary['log_control_exception_count'],0)
        self.assertEqual(r.summary['rules']['UNBALANCED_JOURNAL']['row_count'],0)
        for rule in ['WEEKEND_ENTRY','NIGHT_ENTRY','ROUND_AMOUNT','LARGE_AMOUNT','CLOSING_MANUAL']:
            self.assertEqual(r.summary['rules'][rule]['row_count'],2)
        self.assertEqual(r.summary['flagged_row_count'],2)
        self.assertTrue(r.tables['flagged_lines']['Selection_Reason'].str.len().gt(0).all())
        json.dumps(r.to_dict(),allow_nan=False)

    def test_log_missing_zero_total_is_still_a_population_exception(self):
        g=gl_sample();g['Amount']='0.00';l=log_ads().iloc[:0].copy()
        r=run_jet(g,l)
        self.assertEqual(r.summary['log_population_difference_count'],1)
        self.assertEqual(r.summary['log_control_exception_count'],2)

    def test_log_amount_difference_is_exact(self):
        l=log_ads();l.loc[0,'Total']='90.00';r=run_jet(gl_sample(),l)
        bad=r.tables['log_control_exceptions']
        self.assertEqual(len(bad),1);self.assertEqual(bad['Difference_Cents'].iloc[0],1000)

    def test_unbalanced_journal_is_flagged(self):
        g=gl_sample();g.loc[0,'Amount']='110.00';r=run_jet(g,log_ads())
        self.assertEqual(r.summary['rules']['UNBALANCED_JOURNAL']['journal_count'],1)

    def test_repeated_lines_within_one_journal_are_not_duplicate_journals(self):
        g=gl_sample();extra=g.iloc[:1].copy();extra['Journal_ID_Line_Number']='003'
        r=run_jet(pd.concat([g,extra],ignore_index=True),log_ads())
        self.assertEqual(r.summary['rules']['REPEATED_ACCOUNT_AMOUNT']['row_count'],0)

    def test_sequence_gap_uses_sorted_unique_scoped_ids(self):
        g=gl_sample();extra=g.copy();extra['Journal_ID']='3000:2007:0003'
        r=run_jet(pd.concat([extra,g,g],ignore_index=True),log_ads())
        self.assertEqual(r.tables['sequence_gaps']['Missing_Count'].tolist(),[1])

    def test_invalid_ads_dc_has_structured_error(self):
        g=gl_sample();g.loc[0,'Amount_Credit_Debit_Indicator']='H'
        with self.assertRaises(DataValidationError) as caught:run_jet(g,log_ads())
        self.assertEqual(caught.exception.issues[0].code,'INVALID_DC_CODE')

    def test_optional_rules_are_explicitly_skipped(self):
        r=run_jet(gl_sample().drop(columns='Entered_Time'),log_ads())
        skipped={x['rule'] for x in r.metadata['skipped_rules']}
        self.assertTrue({'NIGHT_ENTRY','LARGE_AMOUNT','CLOSING_MANUAL','DOCUMENT_AFTER_ENTRY'}<=skipped)

    def test_analysis_is_pure_and_result_exports_csv(self):
        g=gl_sample();before=g.copy(deep=True);r=run_jet(g,log_ads());pd.testing.assert_frame_equal(g,before)
        with tempfile.TemporaryDirectory() as d:
            r.save(d);self.assertTrue((Path(d)/'flagged_lines.csv').is_file())
            self.assertEqual(json.loads((Path(d)/'summary.json').read_text())['module'],'jet')

    def test_analytical_review_keeps_currencies_separate_and_known_growth(self):
        current=gl_sample();prior=current.copy();prior['Fiscal_Year']='2006';prior['Amount']='50.00'
        prior['Journal_ID']='3000:2006:0001';prior['Effective_Date']='20060131';prior['Entered_Date']='20060203'
        r=analytical_review(pd.concat([current,prior],ignore_index=True),current_year='2007',prior_year='2006')
        self.assertEqual(r.summary['review_account_count'],2)
        self.assertEqual(r.tables['year_comparison']['Change_Pct'].tolist(),[100.0,-100.0])

    def test_analytical_review_zero_prior_is_not_infinite(self):
        current=gl_sample();prior=current.copy();prior['Fiscal_Year']='2006';prior['Amount']='0.00'
        r=analytical_review(pd.concat([current,prior],ignore_index=True),current_year='2007',prior_year='2006')
        self.assertTrue(r.tables['year_comparison']['Change_Pct'].isna().all())
        json.dumps(r.to_dict(),allow_nan=False)

    def test_cash_matches_unique_and_leaves_ambiguous_unmatched(self):
        bank=pd.DataFrame({'Row_ID':['b1','b2','b3'],'Bank_Account':['A']*3,'Currency':['USD']*3,
                           'Date':['20070101']*3,'Amount':['100.00','50.00','50.00']})
        ledger=bank.iloc[:2].copy();ledger['Row_ID']=['g1','g2']
        r=cash_proofing(bank,ledger)
        self.assertEqual(r.summary['matched_count'],1)
        self.assertEqual(r.summary['unmatched_bank_count'],2)
        self.assertEqual(r.summary['unmatched_gl_count'],1)

    def test_cash_does_not_match_other_currency(self):
        bank=pd.DataFrame({'Row_ID':['b1'],'Bank_Account':['A'],'Currency':['USD'],'Date':['20070101'],'Amount':['100']})
        ledger=bank.copy();ledger['Currency']='EUR';ledger['Row_ID']='g1'
        self.assertEqual(cash_proofing(bank,ledger).summary['matched_count'],0)

    def test_inventory_known_quantity_no_outflow_and_stale_are_distinct(self):
        m=pd.DataFrame({'Item_ID':['A','B'],'Date':['20070101']*2,'Quantity_In':[10,5],'Quantity_Out':[2,0]})
        opening=pd.DataFrame({'Item_ID':['A','B'],'Opening_Quantity':[5,0]})
        r=inventory_analysis(m,opening,as_of='20071231',stale_days=180)
        s=r.tables['item_summary'].set_index('Item_ID')
        self.assertEqual(s.loc['A','Ending_Quantity'],13)
        self.assertTrue(s.loc['A','Stale_Candidate'])
        self.assertTrue(s.loc['B','No_Outflow_In_Data']);self.assertFalse(s.loc['B','Stale_Candidate'])
        json.dumps(r.to_dict(),allow_nan=False)

    def test_inventory_rejects_missing_opening_and_bad_quantities(self):
        m=pd.DataFrame({'Item_ID':['A'],'Date':['20070101'],'Quantity_In':['bad'],'Quantity_Out':[0]})
        with self.assertRaises(DataValidationError):inventory_analysis(m,pd.DataFrame({'Item_ID':['B'],'Opening_Quantity':[0]}),as_of='20071231')
        with self.assertRaises(DataValidationError):inventory_analysis(m,pd.DataFrame({'Item_ID':['A'],'Opening_Quantity':[0]}),as_of='20071231')

    def test_cleansing_reports_errors_without_deleting_rows(self):
        f=pd.DataFrame({'Date':['20070230','20070230'],'Amount':['bad','bad']});before=f.copy(deep=True)
        r=profile_data(f,required_columns=['Missing'],date_columns=['Date'],amount_columns=['Amount'])
        self.assertEqual(r.summary['issue_count'],5);self.assertEqual(r.summary['duplicate_row_count'],2)
        pd.testing.assert_frame_equal(f,before)

    def test_kyc_requires_evidence_and_does_not_fake_ai(self):
        fetch=lambda company:[{'title':'공시 예제','url':'https://example.com/disclosure','published_at':'20070101','text':'테스트 본문'}]
        r=kyc_review('가상회사',fetch_documents=fetch)
        self.assertEqual(r.metadata['ai_status'],'not_configured');self.assertEqual(r.summary['insight_count'],0)
        good=kyc_review('가상회사',fetch_documents=fetch,summarize=lambda docs:[{'insight':'원문 검토 필요','source_ids':[docs[0]['source_id']]}])
        self.assertEqual(good.summary['insight_count'],1)
        with self.assertRaises(DataValidationError):kyc_review('가상회사',fetch_documents=fetch,summarize=lambda docs:[{'insight':'근거 없음','source_ids':['unknown']}])

    def test_working_paper_is_unreviewed_and_does_not_overwrite(self):
        r=run_jet(gl_sample(),log_ads())
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'paper';p=generate_working_paper(r,folder,entity='가상회사',period='2007',prepared_by='테스트')
            self.assertIn('검토 상태: 미검토',p.read_text())
            self.assertTrue((folder/'analysis/flagged_lines.csv').exists())
            with self.assertRaises(FileExistsError):generate_working_paper(r,folder,entity='가상회사',period='2007',prepared_by='테스트')

if __name__=='__main__':unittest.main(verbosity=2)
