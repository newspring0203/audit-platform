from pathlib import Path
from io import BytesIO
from datetime import datetime
import sys,json,tempfile,time,unittest,zipfile
from xml.sax.saxutils import escape
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
import pandas as pd
from audit_data_lab import reshape_quickbooks_report,execute_analysis
from audit_data_lab.quickbooks import REPORT_FIELDS
from audit_data_lab.traceability import attach_traceability,records
from backend.app.main import create_app,AppConfig
from backend.app.storage import StorageConfig
from fastapi.testclient import TestClient

def row(head=None,**kwargs):
    values=[None]*13
    if head is not None:values[0]=head
    for key,value in kwargs.items():values[5+REPORT_FIELDS.index(key)]=value
    return values

def report():
    return pd.DataFrame([[None]*5+REPORT_FIELDS,row('1000 · Cash'),row('Beginning Balance',Balance='10.00'),
        row(Type='Deposit',Date='2026-10-01',Num='0001',Name='Customer',Memo='=1+1',Split='Sales',Amount='1,000.50',Balance='1,010.50'),
        row(Type='Check',Date='2026-10-02',Num='0002',Name='Vendor',Amount='(20.50)',Balance='990.00'),
        row('Total Cash',Amount='980.00',Balance='990.00'),row('2000 · Sales'),
        row(Type='Invoice',Date='2026-10-01',Num='0001',Name='Customer',Amount='(1,000.50)',Balance='(1,000.50)'),row()])

def xlsx_fixture(frame):
    # 최소 XLSX 테스트 바이트. 실제 사용자용 파일 작성기가 아니다.
    rows=[]
    for r,values in enumerate(frame.values.tolist(),1):
        cells=[]
        for c,value in enumerate(values):
            if value is None or pd.isna(value):continue
            cells.append(f'<c r="{chr(65+c)}{r}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        rows.append(f'<row r="{r}">'+''.join(cells)+'</row>')
    files={'[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
      '_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
      'xl/workbook.xml':'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="GL report" sheetId="1" r:id="rId1"/></sheets></workbook>',
      'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
      'xl/worksheets/sheet1.xml':'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+''.join(rows)+'</sheetData></worksheet>'}
    data=BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        for name,value in files.items():z.writestr(name,value)
    return data.getvalue()

class QuickBooksTests(unittest.TestCase):
    def test_flatten_preserves_account_num_and_source_without_mutation(self):
        raw=report();before=raw.copy(deep=True);result=reshape_quickbooks_report(raw);flat=result.tables['modified_gl']
        self.assertEqual(result.summary['conversion_status'],'completed_flattening');self.assertEqual(result.summary['transaction_row_count'],3)
        self.assertEqual(flat['Account Description'].tolist(),['1000 · Cash','1000 · Cash','2000 · Sales'])
        self.assertEqual(flat.Amount.tolist(),['1000.50','-20.50','-1000.50']);self.assertEqual(flat.Num.tolist(),['0001','0002','0001'])
        self.assertEqual(flat.QuickBooks_Source_Row.tolist(),[4,5,8]);self.assertEqual(flat.Account_Source_Row.tolist(),[2,2,7]);pd.testing.assert_frame_equal(raw,before)
        self.assertEqual(result.summary['ads_status'],'not_converted');self.assertNotIn('Amount_Currency',flat)
    def test_all_report_rows_are_classified(self):
        raw=report();r=reshape_quickbooks_report(raw);d=r.tables['row_dispositions']
        self.assertEqual(d.QuickBooks_Source_Row.tolist(),list(range(1,len(raw)+1)))
        self.assertEqual(r.summary['transaction_row_count']+r.summary['excluded_nontransaction_row_count']+r.summary['review_row_count'],len(raw))
    def test_unknown_row_does_not_carry_account_past_boundary(self):
        raw=report();raw.iloc[4]=row(Memo='Unknown footer')
        r=execute_analysis('quickbooks_preprocessing',lambda:reshape_quickbooks_report(raw))
        self.assertEqual(r.summary['conversion_status'],'incomplete_review_required');self.assertEqual(r.metadata['execution_status'],'completed_with_limitations')
        self.assertIn(5,r.tables['review_rows'].QuickBooks_Source_Row.tolist())
    def test_total_resets_account_and_invalid_transactions_not_silently_deleted(self):
        raw=report();raw.iloc[6]=row(Type='Invoice',Date='2026-10-03',Amount='12')
        r=reshape_quickbooks_report(raw);self.assertIn('QUICKBOOKS_ACCOUNT_MISSING',r.tables['module_issues'].code.tolist());self.assertIn(7,r.tables['review_rows'].QuickBooks_Source_Row.tolist())
    def test_date_format_explicit_and_excel_serial_not_guessed(self):
        raw=report();raw.iloc[3,6]='10/01/2026';bad=reshape_quickbooks_report(raw);self.assertIn('INVALID_DATE',bad.tables['module_issues'].code.tolist())
        raw.iloc[4,6]='10/02/2026';raw.iloc[7,6]='10/01/2026';good=reshape_quickbooks_report(raw,date_format='%m/%d/%Y');self.assertEqual(len(good.tables['modified_gl']),3)
        raw.iloc[3,6]=46300;bad=reshape_quickbooks_report(raw,date_format='%m/%d/%Y');self.assertIn('INVALID_DATE',bad.tables['module_issues'].code.tolist())
    def test_actual_excel_date_object(self):
        raw=report();raw.iloc[3,6]=datetime(2026,10,1);r=reshape_quickbooks_report(raw);self.assertEqual(r.tables['modified_gl'].iloc[0].Date,'2026-10-01')
    def test_invalid_money_not_converted_to_zero(self):
        for value in ['$100','1,00','(abc)','1.234']:
            raw=report();raw.iloc[3,11]=value;r=reshape_quickbooks_report(raw)
            self.assertIn('INVALID_AMOUNT',r.tables['module_issues'].code.tolist());self.assertNotIn(4,r.tables['modified_gl'].QuickBooks_Source_Row.tolist())
    def test_layout_mismatch_is_structured_input_issue(self):
        for raw in [report().iloc[:,:12],report().iloc[1:].reset_index(drop=True)]:
            r=execute_analysis('quickbooks_preprocessing',lambda:reshape_quickbooks_report(raw));self.assertEqual(r.metadata['execution_status'],'not_executed_input_issue')
    def test_exact_trace_includes_transaction_and_actual_account_heading(self):
        raw=report();r=reshape_quickbooks_report(raw);m=attach_traceability(r,{'quickbooks':raw},{'quickbooks':{'first_data_row':1}},run_id='qb')
        record=m['tables']['modified_gl']['rows'][0];refs=m['trace'][record['review_id']]['sources'];self.assertEqual([ref['rows'] for ref in refs],[[4],[2]])
        self.assertEqual(m['datasets']['quickbooks']['first_data_row'],1)
    def test_formula_csv_export_is_escaped_original_unchanged(self):
        r=reshape_quickbooks_report(report())
        with tempfile.TemporaryDirectory() as tmp:
            r.save(tmp);flat=pd.read_csv(Path(tmp)/'modified_gl.csv',dtype='string');self.assertEqual(flat.Memo.iloc[0],"'=1+1");self.assertEqual(r.tables['modified_gl'].Memo.iloc[0],'=1+1')

class QuickBooksApiTests(unittest.TestCase):
    def test_xlsx_upload_to_zip_and_exact_first_row_source_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(AppConfig(StorageConfig(Path(tmp)/'runtime'),cleanup_interval_seconds=3600));token=app.state.store.issue_token('test','reviewer');h={'Authorization':'Bearer '+token}
            with TestClient(app) as client:
                response=client.post('/api/jobs',headers=h,json={'module':'quickbooks_preprocessing','parameters':{}});self.assertEqual(response.status_code,201,response.text)
                job=response.json()['job_id'];base='/api/jobs/'+job
                uploaded=client.put(base+'/inputs/quickbooks',headers=h|{'X-Filename':'quickbooks.xlsx'},content=xlsx_fixture(report()));self.assertEqual(uploaded.status_code,200,uploaded.text)
                self.assertEqual(client.post(base+'/run',headers=h).status_code,202)
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    status=client.get(base,headers=h).json()
                    if status['status']=='completed':break
                    time.sleep(.05)
                self.assertEqual(status['status'],'completed')
                bundle=client.get(base+'/downloads/'+status['artifact']['artifact_id'],headers=h)
                with zipfile.ZipFile(BytesIO(bundle.content)) as z:
                    self.assertIn('review/analysis/modified_gl.csv',z.namelist());data=pd.read_csv(BytesIO(z.read('review/analysis/modified_gl.csv')),dtype='string');self.assertEqual(len(data),3)
                    snapshot=json.loads(z.read('review/review_snapshot.json'));self.assertEqual(snapshot['summary']['ads_status'],'not_converted')
                    record=snapshot['tables']['modified_gl']['rows'][0];rid=record['review_id']
                sources=client.get(base+'/review/sources/quickbooks',params={'review_id':rid},headers=h).json()
                self.assertEqual(sources['dataset']['sheet'],'GL report');self.assertEqual(sources['total'],2)
                selected=next(row for row in sources['rows'] if row['source_row']==4);self.assertEqual(selected['values']['7'],'0001')
