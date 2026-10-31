from pathlib import Path
import sys,unittest
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from audit_data_lab import (cash_proofing,inventory_analysis,analytical_review,run_jet,JetConfig,cleanse_data,kyc_review,execute_analysis)
from audit_data_lab.common import fail
from test_analysis_features import gl_sample,log_ads

def cash_rows(side,dates,amounts):
    return pd.DataFrame({'Row_ID':[side+str(i) for i in range(len(dates))],'Bank_Account':['A']*len(dates),'Currency':['USD']*len(dates),'Date':dates,'Amount':amounts})

def inventory_rows():
    return pd.DataFrame({'Item_ID':['A','A'],'Date':['20070101','20070102'],'Quantity_In':[10,0],'Quantity_Out':[0,2]}),pd.DataFrame({'Item_ID':['A'],'Opening_Quantity':[0]})

def two_years():
    a=gl_sample();b=a.copy();b['Fiscal_Year']='2006';b['Journal_ID']='3000:2006:0001';b['Effective_Date']='20060131';b['Entered_Date']='20060131';b['Amount']='50.00'
    return pd.concat([a,b],ignore_index=True)

def tb_and_mapping():
    tb=[];mapping=[]
    values=[('0100','current_assets',200,1),('0200','noncurrent_assets',100,1),
            ('0300','current_liabilities',-100,-1),('0400','noncurrent_liabilities',-50,-1),('0500','equity',-150,-1)]
    for account,group,amount,sign in values:
        mapping.append({'Business_Unit_Code':'3000:01','GL_Account_Number':account,'Metric_Group':group,'Sign_Multiplier':sign})
        for year in ['2006','2007']:
            tb.append({'Business_Unit_Code':'3000:01','GL_Account_Number':account,'Fiscal_Year':year,'Period':'12','Amount_Currency':'USD','Amount_Ending':str(amount)})
    return pd.DataFrame(tb),pd.DataFrame(mapping)

class DeeperAnalyticsTests(unittest.TestCase):
    def test_cash_configured_timing_match_requires_unique_both_sides(self):
        b=cash_rows('b',['20070101'],['100']);g=cash_rows('g',['20070103'],['100'])
        self.assertEqual(cash_proofing(b,g).summary['matched_count'],0)
        r=cash_proofing(b,g,date_tolerance_days=2)
        self.assertEqual(r.summary['timing_match_count'],1)
        self.assertEqual(r.tables['matches']['Date_Difference_Days'].tolist(),[2])

    def test_cash_exact_date_does_not_override_multiple_timing_candidates(self):
        b=cash_rows('b',['20070101'],['100']);g=cash_rows('g',['20070101','20070102'],['100','100'])
        r=cash_proofing(b,g,date_tolerance_days=2)
        self.assertEqual(r.summary['matched_count'],0)
        self.assertEqual(r.summary['ambiguous_candidate_count'],2)
        self.assertEqual(len(r.tables['review_items']),3)

    def test_cash_candidate_limit_does_not_keep_partial_matches(self):
        b=cash_rows('b',['20070101']*3,['100']*3);g=cash_rows('g',['20070101']*3,['100']*3)
        r=cash_proofing(b,g,max_candidate_links=2)
        self.assertEqual(r.summary['matched_count'],0)
        self.assertEqual(r.summary['candidate_limit_group_count'],1)
        self.assertEqual(r.tables['module_issues']['code'].iloc[0],'CANDIDATE_LIMIT')

    def test_cash_balance_adjustment_needs_reference(self):
        b=cash_rows('b',['20070101'],['100']);g=b.copy()
        snapshot=pd.DataFrame({'Bank_Account':['A'],'Currency':['USD'],'As_Of_Date':['20070131'],
            'Bank_Balance':['900'],'GL_Balance':['1000'],'Bank_Adjustment':['100'],'Adjustment_Reference':['']})
        r=cash_proofing(b,g,as_of='20070131',balances=snapshot)
        self.assertEqual(r.tables['balance_reconciliation']['Difference'].iloc[0],0)
        self.assertEqual(r.summary['balance_reconciliation_status'],'review_required')
        self.assertEqual(r.tables['balance_reconciliation']['Status'].iloc[0],'adjustment_evidence_missing')
        snapshot['Adjustment_Reference']='사용자가 제출한 조정명세 A'
        self.assertEqual(cash_proofing(b,g,as_of='20070131',balances=snapshot).summary['balance_reconciliation_status'],'arithmetic_match')

    def test_cash_bad_optional_balance_keeps_transaction_results(self):
        b=cash_rows('b',['20070101'],['100'])
        r=cash_proofing(b,b,as_of='20070131',balances=pd.DataFrame({'Bad':[1]}))
        self.assertEqual(r.summary['matched_count'],1)
        self.assertEqual(r.summary['balance_reconciliation_status'],'not_executed_input_issue')

    def test_cash_unmatched_age_is_explicit(self):
        b=cash_rows('b',['20070101'],['100']);g=cash_rows('g',['20070101'],['90'])
        r=cash_proofing(b,g,as_of='20070301',aging_days=30)
        self.assertTrue(r.tables['review_items']['Aged_Unmatched'].all())

    def test_inventory_running_negative_can_recover_before_period_end(self):
        m=pd.DataFrame({'Item_ID':['A','A'],'Date':['20070101','20070102'],'Quantity_In':[0,10],'Quantity_Out':[2,0]})
        r=inventory_analysis(m,pd.DataFrame({'Item_ID':['A'],'Opening_Quantity':[0]}),as_of='20071231')
        self.assertEqual(r.summary['negative_stock_count'],0)
        self.assertEqual(r.summary['negative_movement_event_count'],1)
        self.assertEqual(r.tables['movement_timeline']['Running_Quantity'].tolist(),[-2,8])

    def test_inventory_lot_age_requires_reconciled_snapshot(self):
        m,o=inventory_rows()
        lots=pd.DataFrame({'Item_ID':['A'],'Lot_ID':['L1'],'Receipt_Date':['20070101'],'Snapshot_Date':['20071231'],'Remaining_Quantity':[8]})
        r=inventory_analysis(m,o,as_of='20071231',lot_snapshot=lots)
        self.assertEqual(r.summary['lot_aging_status'],'ready')
        self.assertEqual(r.tables['lot_aging']['Age_Days'].iloc[0],364)
        self.assertEqual(r.tables['aging_buckets']['Remaining_Quantity'].sum(),8)
        lots['Remaining_Quantity']=7
        r=inventory_analysis(m,o,as_of='20071231',lot_snapshot=lots)
        self.assertEqual(r.summary['lot_aging_status'],'quantity_review_required')
        self.assertTrue(r.tables['aging_buckets'].empty)

    def test_inventory_invalid_optional_lot_does_not_cancel_quantity_analysis(self):
        m,o=inventory_rows();r=inventory_analysis(m,o,as_of='20071231',lot_snapshot=pd.DataFrame({'bad':[1]}))
        self.assertEqual(r.tables['item_summary']['Ending_Quantity'].iloc[0],8)
        self.assertEqual(r.summary['lot_aging_status'],'not_executed_input_issue')

    def test_analytical_tb_ratios_are_calculated_from_explicit_classification(self):
        tb,mapping=tb_and_mapping()
        r=analytical_review(two_years(),current_year='2007',prior_year='2006',tb=tb,account_mapping=mapping,tb_period='12',tb_sign_basis='debit_positive')
        ratios=r.tables['financial_ratios'];current=ratios.loc[ratios.Fiscal_Year.eq('2007')].set_index('Metric')
        self.assertEqual(current.loc['Current_Ratio','Value'],2)
        self.assertEqual(current.loc['Working_Capital','Value'],100)
        self.assertEqual(current.loc['Debt_To_Equity','Value'],1)
        self.assertEqual(r.summary['ratio_status'],'calculated_draft')

    def test_analytical_missing_tb_basis_does_not_invent_ratios(self):
        tb,mapping=tb_and_mapping()
        r=analytical_review(two_years(),current_year='2007',prior_year='2006',tb=tb,tb_period='12')
        self.assertTrue(r.tables['financial_ratios'].empty)
        self.assertEqual(r.summary['ratio_status'],'basis_information_missing')
        self.assertGreater(len(r.tables['year_comparison']),0)

    def test_analytical_no_implicit_latest_tb_period(self):
        tb,mapping=tb_and_mapping()
        r=analytical_review(two_years(),current_year='2007',prior_year='2006',tb=tb,account_mapping=mapping,tb_sign_basis='debit_positive')
        self.assertEqual(r.summary['ratio_status'],'not_executed_input_issue')
        self.assertIn('TB_PERIOD_REQUIRED',r.tables['module_issues']['code'].tolist())

    def test_analytical_unmapped_account_blocks_ratio_not_zero_fills(self):
        tb,mapping=tb_and_mapping();mapping=mapping.iloc[:-1].copy()
        r=analytical_review(two_years(),current_year='2007',prior_year='2006',tb=tb,account_mapping=mapping,tb_period='12',tb_sign_basis='debit_positive')
        self.assertTrue(r.tables['financial_ratios']['Value'].isna().all())
        self.assertEqual(r.summary['ratio_status'],'partially_not_executed')

    def test_analytical_zero_denominator_stays_unavailable(self):
        tb,mapping=tb_and_mapping();tb.loc[tb.GL_Account_Number.eq('0300'),'Amount_Ending']='0'
        r=analytical_review(two_years(),current_year='2007',prior_year='2006',tb=tb,account_mapping=mapping,tb_period='12',tb_sign_basis='debit_positive')
        ratios=r.tables['financial_ratios'];self.assertTrue(ratios.loc[ratios.Metric.eq('Current_Ratio'),'Value'].isna().all())

    def test_analytical_period_coverage_difference_is_reported(self):
        g=two_years();g.loc[g.Fiscal_Year.eq('2007'),'Period']='02'
        r=analytical_review(g,current_year='2007',prior_year='2006')
        self.assertEqual(r.summary['period_coverage_status'],'observed_periods_differ')
        self.assertIn('COMPARISON_PERIOD_COVERAGE_DIFFERS',r.tables['module_issues']['code'].tolist())
        self.assertTrue(r.tables['monthly_comparison']['Change'].isna().all())

    def test_jet_rule_count_is_not_line_count_or_double_sided_amount(self):
        r=run_jet(gl_sample(),log_ads(),JetConfig(round_unit=100))
        q=r.tables['journal_review_queue'];self.assertEqual(len(q),1)
        self.assertEqual(q['Debit_Total'].iloc[0],100);self.assertEqual(q['Credit_Total'].iloc[0],100)
        self.assertEqual(q['Matched_Rule_Count'].iloc[0],5)
        self.assertTrue(q['Complex_Condition'].iloc[0])

    def test_mapping_suggestions_are_not_applied_without_explicit_mapping(self):
        f=pd.DataFrame({'BELNR':['001'],'HKONT':['0100'],'AUGDT':['20070101']})
        r=cleanse_data(f);self.assertNotIn('mapped_data',r.tables)
        suggested=r.tables['mapping_suggestions'].set_index('Target_Field')
        self.assertEqual(suggested.loc['Effective_Date','Status'],'not_found')
        self.assertEqual(suggested.loc['GL_Account_Number','Suggested_Source'],'HKONT')

    def test_mapping_ambiguous_and_collision_cases_are_not_guessed(self):
        f=pd.DataFrame({'HKONT':['0100'],'계정번호':['0200']})
        r=cleanse_data(f);self.assertEqual(r.tables['mapping_suggestions'].set_index('Target_Field').loc['GL_Account_Number','Status'],'ambiguous')
        f['GL_Account_Number']='0300'
        mapping=pd.DataFrame({'Target_Field':['GL_Account_Number'],'Source_Field':['HKONT']})
        r=cleanse_data(f,mapping=mapping)
        self.assertEqual(r.summary['mapping_status'],'not_applied_mapping_issue')
        self.assertNotIn('mapped_data',r.tables)

    def test_mapping_preserves_rows_and_original_values(self):
        f=pd.DataFrame({'BELNR':['001','002'],'SHKZG':['S','H']});before=f.copy(deep=True)
        mapping=pd.DataFrame({'Target_Field':['Journal_ID','Amount_Credit_Debit_Indicator'],'Source_Field':['BELNR','SHKZG']})
        r=cleanse_data(f,mapping=mapping)
        self.assertEqual(r.tables['mapped_data']['Journal_ID'].tolist(),['001','002'])
        self.assertEqual(r.tables['mapped_data']['Amount_Credit_Debit_Indicator'].tolist(),['S','H'])
        pd.testing.assert_frame_equal(f,before)

    def test_configured_missing_date_field_is_reported(self):
        r=cleanse_data(pd.DataFrame({'Amount':['100']}),date_columns=['Date'])
        self.assertIn('MISSING_COLUMN',r.tables['issues']['Code'].tolist())

    def test_kyc_ai_failure_preserves_public_sources_and_reports_reason(self):
        def fetch(company):return [{'title':'가상 공시','url':'https://example.com','published_at':'20070101','text':'공개 공시 가상 본문'}]
        r=execute_analysis('kyc',lambda:kyc_review('가상회사',fetch_documents=fetch,summarize=lambda docs:fail('AI_REFUSAL','API','AI 요약 미완료')))
        self.assertEqual(r.summary['source_count'],1);self.assertEqual(r.summary['insight_count'],0)
        self.assertEqual(r.metadata['ai_status'],'failed_sources_available')
        self.assertEqual(r.metadata['execution_status'],'completed_with_limitations')
        self.assertIn('AI_REFUSAL',r.tables['module_issues']['code'].tolist())

if __name__=='__main__':unittest.main(verbosity=2)
