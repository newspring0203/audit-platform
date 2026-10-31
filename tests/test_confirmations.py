from pathlib import Path
import sys,json,tempfile,unittest,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
import pandas as pd
from audit_data_lab.confirmations import ar_confirmation_review,bank_confirmation_review
from audit_data_lab.validation import DataValidationError
from audit_data_lab.traceability import attach_traceability
from backend.app.main import create_app,AppConfig
from backend.app.storage import StorageConfig
from backend.app.worker import run
from fastapi.testclient import TestClient


def fixture(prefix='AR'):
    return [pd.read_csv(ROOT/'data/demo/confirmations'/f'{prefix}_{slot}.csv',dtype='string') for slot in ['ledger','requests','replies']]


class ConfirmationTests(unittest.TestCase):
    def test_ar_states_and_original_unchanged(self):
        frames=fixture();before=[x.copy(deep=True) for x in frames]
        r=ar_confirmation_review(*frames,as_of='20261031')
        rows=r.tables['confirmation_comparison'];self.assertEqual(rows.Status.tolist(),['matched','difference','no_reply','partial','date_mismatch','not_requested'])
        self.assertEqual(rows.Difference.iloc[1],100)
        self.assertTrue(rows.Difference.iloc[2:].isna().all())
        for a,b in zip(frames,before):pd.testing.assert_frame_equal(a,b)

    def test_empty_replies_are_missing_not_zero(self):
        l,q,a=fixture();r=ar_confirmation_review(l,q,a.iloc[:0],as_of='20261031')
        self.assertEqual(r.summary['no_reply_count'],5)
        self.assertTrue(r.tables['confirmation_comparison'].Confirmed_Balance.isna().all())

    def test_reply_scope_and_currency_mismatch_not_compared(self):
        l,q,a=fixture();a.loc[0,'Currency']='USD';a.loc[1,'Counterparty_ID']='OTHER'
        r=ar_confirmation_review(l,q,a,as_of='20261031')
        self.assertEqual(r.tables['confirmation_comparison'].Status.iloc[:2].tolist(),['scope_mismatch','scope_mismatch'])
        self.assertTrue(r.tables['confirmation_comparison'].Difference.iloc[:2].isna().all())

    def test_duplicate_reply_rejected(self):
        l,q,a=fixture()
        with self.assertRaises(DataValidationError):ar_confirmation_review(l,q,pd.concat([a,a.iloc[:1]]),as_of='20261031')

    def test_duplicate_ledger_scope_rejected(self):
        l,q,a=fixture()
        with self.assertRaises(DataValidationError):ar_confirmation_review(pd.concat([l,l.iloc[:1]]),q,a,as_of='20261031')

    def test_scope_date_rejected(self):
        with self.assertRaises(DataValidationError):ar_confirmation_review(*fixture(),as_of='20261231')

    def test_missing_confirmed_amount_rejected(self):
        l,q,a=fixture();a.loc[0,'Confirmed_Balance']=pd.NA
        with self.assertRaises(DataValidationError):ar_confirmation_review(l,q,a,as_of='20261031')

    def test_unknown_reply_retained(self):
        l,q,a=fixture();a.loc[0,'Request_ID']='UNKNOWN'
        r=ar_confirmation_review(l,q,a,as_of='20261031')
        self.assertEqual(r.summary['orphan_reply_count'],1)
        self.assertEqual(r.tables['unlinked_replies'].Request_ID.iloc[0],'UNKNOWN')

    def test_tolerance_not_exact_match(self):
        r=ar_confirmation_review(*fixture(),as_of='20261031',amount_tolerance=100)
        self.assertEqual(r.tables['confirmation_comparison'].Status.iloc[1],'within_tolerance')
        self.assertEqual(r.summary['matched_count'],1)
        self.assertEqual(len(r.tables['review_items']),5)

    def test_bank_terms_not_inferred_and_new_item_retained(self):
        l,q,a=fixture('BANK');a.loc[0,'Guarantees']=''
        r=bank_confirmation_review(l.iloc[1:],q,a,as_of='20261031')
        self.assertEqual(r.tables['confirmation_comparison'].Status.iloc[0],'difference')
        self.assertIn('ledger_missing',r.tables['confirmation_comparison'].Status.tolist())
        terms=r.tables['terms_review']
        self.assertEqual(terms.loc[(terms.Request_ID=='BANK2')&(terms.Field=='Collateral'),'Status'].iloc[0],'text_difference')
        self.assertEqual(terms.loc[(terms.Request_ID=='BANK1')&(terms.Field=='Guarantees'),'Status'].iloc[0],'not_provided')

    def test_bank_terms_difference_retained_even_when_balance_matches(self):
        l,q,a=fixture('BANK');a.loc[0,'Collateral']='추가 담보'
        r=bank_confirmation_review(l,q,a,as_of='20261031')
        self.assertEqual(r.tables['confirmation_comparison'].Status.iloc[0],'matched')
        self.assertIn('BANK1',r.tables['review_items'].Request_ID.tolist())

    def test_api_both_modules_with_csv_worker_trace_and_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            app=create_app(AppConfig(StorageConfig(Path(temp)/'runtime'),cleanup_interval_seconds=3600))
            store=app.state.store;token=store.issue_token('demo','owner');h={'Authorization':'Bearer '+token}
            with TestClient(app) as client:
                features=client.get('/api/features',headers=h).json()['features']
                for prefix,module in [('AR','ar_confirmation'),('BANK','bank_confirmation')]:
                    self.assertTrue(any(f['module']==module for f in features))
                    params={'as_of':'20261031','amount_tolerance':0}
                    response=client.post('/api/jobs',json={'module':module,'parameters':params},headers=h)
                    self.assertEqual(response.status_code,201,response.text)
                    job=response.json()['job_id'];base='/api/jobs/'+job
                    for slot,frame in zip(['ledger','requests','replies'],fixture(prefix)):
                        response=client.put(base+'/inputs/'+slot,content=frame.to_csv(index=False).encode(),headers=h|{'X-Filename':slot+'.csv'})
                        self.assertEqual(response.status_code,200,response.text)
                    row=store.owned(job,store.authenticate(token));folder=store.job_path(row)
                    run({'directory':str(folder),'parameters':params,'inputs':json.loads(row['inputs']),'module':module,'job_id':job})
                    store.finalize(job)
                    review=client.get(base+'/review',headers=h).json()
                    self.assertEqual(review['metadata']['execution_status'],'completed')
                    table=client.get(base+'/review/tables/confirmation_comparison',headers=h).json()
                    trace=client.get(base+'/review/trace/'+table['rows'][0]['review_id'],headers=h).json()
                    self.assertEqual({s['slot'] for s in trace['sources']},{'ledger','requests','replies'})
                    with zipfile.ZipFile(folder/'bundle.zip') as z:self.assertTrue(any(n.endswith('/confirmation_comparison.csv') for n in z.namelist()))
