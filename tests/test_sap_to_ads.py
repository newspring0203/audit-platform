"""실제 노트북 셀을 작은 정답 데이터와 오류 데이터로 실행하는 회귀 테스트.
실행: python -m unittest discover -s tests -p 'test_*.py' -v
"""
import calendar
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
NOTEBOOK = PROJECT / 'notebooks/reshape_rename_sap_data.ipynb'
K = ['BUKRS (Company Code)', 'GJAHR (Fiscal Year)', 'BELNR (Accounting Document Number)']
LINE = 'BUZEI (Number of Line Item Within Accounting Document)'
ACCOUNT = 'HKONT (General Ledger Account)'
AMOUNT = 'DMBTR (Amount in Local Currency)'
DC = 'SHKZG (Debit/Credit Indicator)'
POST = 'BUDAT (Posting Date in the Document)'
PERIOD = 'MONAT (Fiscal Period)'
CUR = 'HWAER (Local Currency)'
OPEN = 'HSLVT (Balance carried forward in local currency (currency 2))'
def movement(n):
    return f'HSL{n:02d} (Total transactions in the period in local currency (curr 2))'

def fixtures():
    common = {K[0]:'3000', K[1]:'2007', K[2]:'000001', 'GSBER (Business Area)':'0001', 'SGTXT (Item Text)':'판매'}
    b = pd.DataFrame([
        dict(common, **{LINE:'001', ACCOUNT:'0100', AMOUNT:'100.00', DC:'S'}),
        dict(common, **{LINE:'002', ACCOUNT:'0400', AMOUNT:'100.00', DC:'H'}),
    ], dtype='string')
    h = pd.DataFrame([{
        **{k:common[k] for k in K}, 'BKTXT (Document Header Text)':'현금 매출',
        'BLART (Document Type)':'SA', POST:'20070131', 'BLDAT (Document Date in Document)':'20070130',
        'CPUDT (Day On Which Accounting Document Was Entered)':'20070201',
        'CPUTM (Time of Entry)':'090005', PERIOD:'01', 'USNAM (User name)':'tester', CUR:'USD',
    }], dtype='string')
    rows=[]
    for account,opening,change in [('0100','500.00','100.00'),('0400','0.00','-100.00')]:
        row={K[0]:'3000','RYEAR (Fiscal Year)':'2007','RLDNR (Ledger)':'0',
             'RRCTY (Record Type)':'0','RVERS (Version)':'1',
             'RACCT (Account Number)':account,'RBUSA (Business Area)':'0001',OPEN:opening}
        row.update({movement(n):change if n==1 else '0.00' for n in range(1,17)})
        rows.append(row)
    return b,h,pd.DataFrame(rows,dtype='string')

class SapToAdsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not NOTEBOOK.is_file():
            raise unittest.SkipTest('Private learning notebook is not distributed; synthetic SAP API tests still run.')
        notebook=json.loads(NOTEBOOK.read_text())
        cls.sources=[c['source'] if isinstance(c['source'],str) else ''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code']

    def run_pipeline(self,b=None,h=None,t=None):
        if b is None:b,h,t=fixtures()
        # 셀의 CSV 진단 출력도 임시 폴더에만 기록합니다.
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        path=Path(temp.name)
        scope=dict(ROOT=PROJECT,pd=pd,json=json,calendar=calendar,display=lambda *args:None,
                   COMPANY='3000',YEAR='2007',LEDGER='0',RECORD_TYPE='0',VERSION='1',
                   bseg=b.copy(deep=True),bkpf=h.copy(deep=True),glt0=t.copy(deep=True),
                   OUT=path,CHECKS=path)
        with contextlib.redirect_stdout(io.StringIO()):
            # 원본 읽기 및 설정 셀을 제외하고 실제 결합~저장 셀을 실행합니다.
            for source in self.sources[2:]:
                exec(compile(source,str(NOTEBOOK),'exec'),scope)
        return scope

    def test_valid_data_and_known_balances(self):
        r=self.run_pipeline();self.assertEqual(len(r['gl']),2)
        jan=r['tb'].loc[r['tb']['Period'].eq('01')].set_index('GL_Account_Number')
        self.assertEqual(jan.loc['0100','Amount_Beginning'],500)
        self.assertEqual(jan.loc['0100','Amount_Ending'],600)
        self.assertEqual(jan.loc['0400','Amount_Ending'],-100)
        self.assertEqual(r['summary']['reconciliation_difference_rows'],0)
        self.assertEqual(r['summary']['nonbalancing_journal_count'],0)
        self.assertEqual(r['gl']['Amount_Credit_Debit_Indicator'].tolist(),['D','C'])

    def test_identifiers_and_leading_zeroes_survive_csv(self):
        r=self.run_pipeline();g=r['saved_gl']
        self.assertEqual(g['GL_Account_Number'].tolist(),['0100','0400'])
        self.assertEqual(g['Journal_ID_Line_Number'].tolist(),['001','002'])
        self.assertEqual(g['Journal_ID'].unique().tolist(),['3000:2007:000001'])
        self.assertEqual(g['Business_Unit_Code'].unique().tolist(),['3000:0001'])

    def test_effective_date_is_posting_not_entry_date(self):
        r=self.run_pipeline();self.assertEqual(r['gl']['Effective_Date'].iloc[0],'20070131')
        self.assertEqual(r['gl']['Entered_Date'].iloc[0],'20070201')
        self.assertEqual(r['gl']['Entered_Time'].iloc[0],'0900')

    def test_same_journal_in_other_company_or_year_does_not_join(self):
        b,h,t=fixtures();other=h.copy();other[K[0]]='4000';other['BKTXT (Document Header Text)']='wrong company'
        old=h.copy();old[K[1]]='2006';old['BKTXT (Document Header Text)']='wrong year'
        r=self.run_pipeline(b,pd.concat([h,other,old],ignore_index=True),t)
        self.assertEqual(len(r['gl']),2)
        self.assertEqual(r['gl']['JE_Header_Description'].unique().tolist(),['현금 매출'])

    def test_duplicate_header_rejected(self):
        b,h,t=fixtures()
        with self.assertRaisesRegex(ValueError,'헤더 키가 중복'):self.run_pipeline(b,pd.concat([h,h],ignore_index=True),t)

    def test_duplicate_detail_rejected(self):
        b,h,t=fixtures()
        with self.assertRaisesRegex(ValueError,'상세행 키가 중복'):self.run_pipeline(pd.concat([b,b.iloc[:1]],ignore_index=True),h,t)

    def test_missing_header_rejected(self):
        b,h,t=fixtures();b.loc[1,K[2]]='999999'
        with self.assertRaisesRegex(ValueError,'헤더 미연결'):self.run_pipeline(b,h,t)

    def test_missing_journal_key_rejected(self):
        b,h,t=fixtures();b.loc[1,K[2]]=pd.NA
        with self.assertRaisesRegex(ValueError,'전표 키에 결측'):self.run_pipeline(b,h,t)

    def test_invalid_date_rejected(self):
        b,h,t=fixtures();h.loc[0,POST]='20070230'
        with self.assertRaises(ValueError):self.run_pipeline(b,h,t)

    def test_missing_date_rejected(self):
        b,h,t=fixtures();h.loc[0,POST]=pd.NA
        with self.assertRaisesRegex(ValueError,'전기일이 비어'):self.run_pipeline(b,h,t)

    def test_unknown_debit_credit_rejected(self):
        b,h,t=fixtures();b.loc[0,DC]='X'
        with self.assertRaisesRegex(ValueError,'차대변 코드'):self.run_pipeline(b,h,t)

    def test_invalid_amount_rejected(self):
        b,h,t=fixtures();b.loc[0,AMOUNT]='oops'
        with self.assertRaisesRegex(ValueError,'잘못된 금액'):self.run_pipeline(b,h,t)

    def test_missing_amount_rejected(self):
        b,h,t=fixtures();b.loc[0,AMOUNT]=pd.NA
        with self.assertRaisesRegex(ValueError,'금액에 결측'):self.run_pipeline(b,h,t)

    def test_fractional_cent_rejected(self):
        b,h,t=fixtures();b.loc[0,AMOUNT]='100.001'
        with self.assertRaisesRegex(ValueError,'소수 둘째 자리 초과'):self.run_pipeline(b,h,t)

    def test_negative_posting_sign_is_preserved(self):
        b,h,t=fixtures();b[AMOUNT]='-100.00';t.loc[0,movement(1)]='-100.00';t.loc[1,movement(1)]='100.00'
        r=self.run_pipeline(b,h,t)
        self.assertEqual(r['signed_cents'].tolist(),[-10000,10000])
        self.assertEqual(r['summary']['reconciliation_difference_rows'],0)

    def test_nonbalancing_journal_is_reported(self):
        b,h,t=fixtures();b.loc[0,AMOUNT]='110.00'
        r=self.run_pipeline(b,h,t);self.assertEqual(r['summary']['nonbalancing_journal_count'],1)
        self.assertEqual(r['nonbalancing']['Net_Cents'].iloc[0],1000)

    def test_tb_difference_is_reported_with_exact_amount(self):
        b,h,t=fixtures();t.loc[0,movement(1)]='90.00'
        r=self.run_pipeline(b,h,t);bad=r['reconciliation'].loc[r['reconciliation']['Difference_Cents'].ne(0)]
        self.assertEqual(len(bad),1);self.assertEqual(bad['Difference_Cents'].iloc[0],1000)

    def test_account_missing_from_tb_is_reported(self):
        b,h,t=fixtures();t=t.iloc[:1].copy();r=self.run_pipeline(b,h,t)
        bad=r['reconciliation'].loc[r['reconciliation']['Match_Status'].eq('left_only')]
        self.assertEqual(bad['GL_Account_Number'].unique().tolist(),['0400'])
        self.assertEqual(bad['Difference_Cents'].iloc[0],-10000)

    def test_special_period_amount_is_not_dropped(self):
        b,h,t=fixtures();t.loc[0,movement(13)]='25.00';r=self.run_pipeline(b,h,t)
        cash=r['tb'].loc[r['tb']['GL_Account_Number'].eq('0100')].set_index('Period')
        self.assertEqual(cash.loc['12','Amount_Ending'],600)
        self.assertEqual(cash.loc['13','Amount_Ending'],625)
        self.assertEqual(cash.loc['16','Amount_Ending'],625)
        self.assertEqual(cash.loc['13','Balance_AsOf_Date'],'20071231')

    def test_wrong_ledger_does_not_mix_into_tb(self):
        b,h,t=fixtures();extra=t.copy();extra['RLDNR (Ledger)']='L2';extra[movement(1)]='9999.00'
        r=self.run_pipeline(b,h,pd.concat([t,extra],ignore_index=True))
        self.assertEqual(r['summary']['tb_selected_input_rows'],2)
        self.assertEqual(r['summary']['reconciliation_difference_rows'],0)

    def test_invalid_time_rejected(self):
        b,h,t=fixtures();h.loc[0,'CPUTM (Time of Entry)']='250000'
        with self.assertRaises(ValueError):self.run_pipeline(b,h,t)

    def test_period_out_of_range_rejected(self):
        b,h,t=fixtures();h.loc[0,PERIOD]='17'
        with self.assertRaisesRegex(ValueError,'회계기간 범위'):self.run_pipeline(b,h,t)

    def test_fractional_period_rejected(self):
        b,h,t=fixtures();h.loc[0,PERIOD]='1.5'
        with self.assertRaises(ValueError):self.run_pipeline(b,h,t)

    def test_missing_currency_rejected(self):
        b,h,t=fixtures();h.loc[0,CUR]=pd.NA
        with self.assertRaisesRegex(ValueError,'통화'):self.run_pipeline(b,h,t)

    def test_invalid_currency_format_rejected(self):
        b,h,t=fixtures();h.loc[0,CUR]='US'
        with self.assertRaisesRegex(ValueError,'통화'):self.run_pipeline(b,h,t)

    def test_gl_period_month_mismatch_rejected(self):
        b,h,t=fixtures();h.loc[0,PERIOD]='02'
        with self.assertRaisesRegex(ValueError,'달력 월'):self.run_pipeline(b,h,t)

    def test_special_period_requires_year_end(self):
        b,h,t=fixtures();h.loc[0,PERIOD]='13'
        with self.assertRaises(ValueError):self.run_pipeline(b,h,t)

    def test_real_sap_sample(self):
        raw=PROJECT/'data/raw/sap'
        b=pd.read_excel(raw/'BSEG_0001_Accounting Document Segment.xlsx',dtype='string')
        h=pd.read_csv(raw/'SAP_BKPF_전표헤더.txt',sep='|',dtype='string')
        t=pd.read_excel(raw/'GLT0_0001_GL account master record transaction figures.xlsx',dtype='string')
        for frame in [b,h,t]:
            frame.columns=frame.columns.str.strip()
            for col in frame:frame[col]=frame[col].str.strip().replace('',pd.NA)
        r=self.run_pipeline(b,h,t)
        self.assertEqual(r['summary']['gl_output_rows'],28160)
        self.assertEqual(r['summary']['nonbalancing_journal_count'],0)
        self.assertEqual(r['summary']['reconciliation_difference_rows'],0)
        self.assertEqual(r['summary']['debit_amount'],464484735.89)
        self.assertEqual(r['summary']['credit_amount'],464484735.89)

if __name__=='__main__':unittest.main(verbosity=2)
