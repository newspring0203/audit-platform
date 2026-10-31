"""네트워크·유료 AI 호출 없이 공식 API 응답 형태와 오류 처리를 검증한다."""
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlparse,parse_qs
from urllib.error import HTTPError
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from audit_data_lab.kyc_dart import OpenDartClient,document_text,archive_members
from audit_data_lab.kyc_ai import OpenAISummarizer,select_chunks
from audit_data_lab.kyc_live import run_live_kyc
from audit_data_lab.kyc_settings import KycSettings,load_project_env
from audit_data_lab.kyc_transport import request_bytes
from audit_data_lab.validation import DataValidationError

KEY='K'*40
RECEIPT='20260318000001'
CORP='00123456'
TEXT='회사는 제품을 제조하고 판매합니다. 주요 제품의 매출과 위험관리 상황을 확인해야 합니다.'

def zipped(name,body):
    buffer=BytesIO()
    with zipfile.ZipFile(buffer,'w') as z:z.writestr(name,body)
    return buffer.getvalue()


def fake_dart(url,**kwargs):
    path=urlparse(url).path
    if path.endswith('corpCode.xml'):
        return zipped('CORPCODE.xml',f'<result><list><corp_code>{CORP}</corp_code><corp_name>테스트회사</corp_name><stock_code>123456</stock_code></list></result>')
    if path.endswith('list.json'):
        assert parse_qs(urlparse(url).query)['pblntf_detail_ty']==['A001']
        return json.dumps({'status':'000','total_page':1,'list':[{'corp_code':CORP,'report_nm':'사업보고서 (2025.12)','rcept_no':RECEIPT,'rcept_dt':'20260318'}]}).encode()
    if path.endswith('document.xml'):return zipped(RECEIPT+'.xml','<DOCUMENT><TITLE>사업의 내용</TITLE><P>'+TEXT+'</P><script>숨겨진 코드</script></DOCUMENT>')
    raise AssertionError('예상하지 못한 엔드포인트')


def fake_ai(url,**kwargs):
    payload=json.loads(kwargs['body']);inputs=json.loads(payload['input'])
    chunk=inputs['untrusted_disclosure_excerpts'][0]
    insight={'insight':'제품 제조·판매 사업을 영위한다고 공시함.','category':'회사이해','suggested_review':'제품별 매출 원문 확인',
        'evidence':[{'source_id':chunk['source_id'],'chunk_id':chunk['chunk_id'],'quote':TEXT[:20]}]}
    assert payload['store'] is False
    assert payload['text']['format']['strict'] is True
    return json.dumps({'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'insights':[insight]},ensure_ascii=False)}]}]}).encode()


def docs():return [{'source_id':'S0001','title':'사업보고서','url':'https://dart.fss.or.kr/','published_at':'20260318','text':TEXT}]

class KycIntegrationTests(unittest.TestCase):
    def test_company_lookup_and_live_collection_contract(self):
        client=OpenDartClient(KEY,transport=fake_dart)
        self.assertEqual(client.find_companies('테스트')[0]['corp_code'],CORP)
        self.assertEqual(client.resolve_company('123456')['corp_name'],'테스트회사')
        result=client.fetch_documents('테스트회사',start_date='20250101',end_date='20261031')
        self.assertEqual(len(result),1);self.assertIn(TEXT,result[0]['text'])
        self.assertNotIn('숨겨진 코드',result[0]['text'])
        self.assertIn(RECEIPT,result[0]['url']);self.assertEqual(len(result[0]['document_sha256']),64)

    def test_source_only_run_does_not_call_ai(self):
        with tempfile.TemporaryDirectory() as folder:
            r=run_live_kyc('테스트회사',start_date='20250101',end_date='20261031',settings=KycSettings(KEY),
                archive_dir=folder,dart_transport=fake_dart,ai_transport=lambda *a,**k:self.fail('AI 호출 금지'))
            self.assertEqual(r.metadata['ai_status'],'not_configured')
            self.assertEqual(r.summary['source_count'],1)
            self.assertTrue((Path(folder)/(RECEIPT+'.txt')).exists())
            self.assertNotIn(KEY,json.dumps(r.to_dict(),ensure_ascii=False))

    def test_full_pipeline_preserves_quote_and_coverage(self):
        r=run_live_kyc('테스트회사',start_date='20250101',end_date='20261031',with_ai=True,
            settings=KycSettings(KEY,'not-a-real-openai-key','example-model'),dart_transport=fake_dart,ai_transport=fake_ai)
        self.assertEqual(r.summary['insight_count'],1)
        self.assertEqual(r.tables['evidence']['Quote'].iloc[0],TEXT[:20])
        self.assertEqual(r.tables['insights']['Review_Status'].iloc[0],'미검토')
        self.assertEqual(r.metadata['ai_processing']['coverage'][0]['selected_fraction'],1)
        self.assertNotIn(KEY,json.dumps(r.to_dict(),ensure_ascii=False))

    def test_no_ai_key_fails_before_network(self):
        with self.assertRaises(DataValidationError) as caught:
            run_live_kyc('테스트회사',start_date='20250101',end_date='20261031',with_ai=True,settings=KycSettings(KEY),dart_transport=lambda *a,**k:self.fail('선행 설정 검사 필요'))
        self.assertEqual(caught.exception.issues[0].code,'OPENAI_KEY_REQUIRED')

    def test_secret_values_are_not_in_settings_repr(self):
        value=KycSettings(KEY,'secret-ai','model')
        self.assertNotIn(KEY,repr(value));self.assertNotIn('secret-ai',repr(value))

    def test_dart_status_errors_do_not_echo_server_message_or_key(self):
        def failed(url,**kwargs):return json.dumps({'status':'010','message':KEY}).encode()
        with self.assertRaises(DataValidationError) as caught:OpenDartClient(KEY,transport=failed).companies()
        self.assertEqual(caught.exception.issues[0].code,'DART_010');self.assertNotIn(KEY,str(caught.exception))

    def test_http_errors_redact_query_secret(self):
        class BadOpener:
            def open(self,request,timeout):raise HTTPError('https://opendart.fss.or.kr/api/list.json?crtfc_key='+KEY,401,KEY,None,None)
        with patch('audit_data_lab.kyc_transport.build_opener',return_value=BadOpener()):
            with self.assertRaises(DataValidationError) as caught:request_bytes('https://opendart.fss.or.kr/api/list.json?crtfc_key='+KEY)
        self.assertNotIn(KEY,str(caught.exception))

    def test_wrong_company_in_disclosure_response_is_rejected(self):
        def wrong(url,**kwargs):
            if urlparse(url).path.endswith('list.json'):
                return json.dumps({'status':'000','list':[{'corp_code':'99999999','rcept_no':RECEIPT}]}).encode()
            return fake_dart(url,**kwargs)
        with self.assertRaises(DataValidationError) as caught:
            OpenDartClient(KEY,transport=wrong).fetch_documents('테스트회사',start_date='20250101',end_date='20261031')
        self.assertEqual(caught.exception.issues[0].code,'COMPANY_MISMATCH')

    def test_no_results_is_not_a_fabricated_summary(self):
        def empty(url,**kwargs):
            if urlparse(url).path.endswith('list.json'):return b'{"status":"013"}'
            return fake_dart(url,**kwargs)
        with self.assertRaises(DataValidationError) as caught:
            run_live_kyc('테스트회사',start_date='20250101',end_date='20261031',settings=KycSettings(KEY),dart_transport=empty)
        self.assertEqual(caught.exception.issues[0].code,'DISCLOSURE_NOT_FOUND')

    def test_invalid_quote_is_rejected(self):
        def unsupported(url,**kwargs):
            response=json.loads(fake_ai(url,**kwargs))
            parsed=json.loads(response['output'][0]['content'][0]['text'])
            parsed['insights'][0]['evidence'][0]['quote']='원문에 없는 허위 근거 문장입니다.'
            response['output'][0]['content'][0]['text']=json.dumps(parsed)
            return json.dumps(response).encode()
        with self.assertRaises(DataValidationError) as caught:OpenAISummarizer('fake','example-model',transport=unsupported)(docs())
        self.assertEqual(caught.exception.issues[0].code,'AI_UNSUPPORTED_EVIDENCE')

    def test_refusal_and_incomplete_response_are_errors(self):
        for response in [{'status':'incomplete','output':[]},{'status':'completed','output':[{'content':[{'type':'refusal','refusal':'no'}]}]}]:
            with self.subTest(response=response),self.assertRaises(DataValidationError):
                OpenAISummarizer('fake','example-model',transport=lambda *a,**k:json.dumps(response).encode())(docs())

    def test_excerpt_budget_records_partial_coverage(self):
        d=docs();d[0]['text']=TEXT*1000
        chunks,coverage=select_chunks(d,max_chars=4400)
        self.assertLessEqual(sum(len(c['text']) for c in chunks),4400)
        self.assertLess(coverage[0]['selected_fraction'],1)
        for chunk in chunks:self.assertEqual(chunk['text'],d[0]['text'][chunk['start_char']:chunk['end_char']])

    def test_archive_paths_are_not_extracted(self):
        raw=zipped('../../outside.xml','<P>'+TEXT+'</P>')
        self.assertIn(TEXT,document_text(raw))

    def test_env_loader_does_not_override_existing_values_or_execute_shell(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'.env').write_text('DART_API_KEY="'+KEY+'"\nOPENAI_MODEL=$(touch should_not_exist)\nHOME=/unsafe\n')
            with patch.dict(os.environ,{'DART_API_KEY':'already-set'},clear=True):
                load_project_env(folder)
                self.assertEqual(os.environ['DART_API_KEY'],'already-set')
                self.assertEqual(os.environ['OPENAI_MODEL'],'$(touch should_not_exist)')
                self.assertNotIn('HOME',os.environ)

    def test_unsafe_xml_and_invalid_date_range_rejected(self):
        raw=zipped('corp.xml','<!DOCTYPE result [<!ENTITY x "bad">]><result>&x;</result>')
        with self.assertRaises(DataValidationError):OpenDartClient(KEY,transport=lambda *a,**k:raw).companies()
        with self.assertRaises(DataValidationError):OpenDartClient(KEY,transport=fake_dart).disclosures(CORP,start_date='20260230',end_date='20261031')

if __name__=='__main__':unittest.main(verbosity=2)
