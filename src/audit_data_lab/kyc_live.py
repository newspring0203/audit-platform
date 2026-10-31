"""OpenDART와 선택적 OpenAI 공급자를 기존 KYC 결과 형식에 연결한다."""
from .kyc import kyc_review
from .kyc_settings import KycSettings
from .kyc_dart import OpenDartClient
from .kyc_ai import OpenAISummarizer
from .kyc_transport import request_bytes


def run_live_kyc(company,*,start_date,end_date,max_reports=1,with_ai=False,report_type="A001",settings=None,
                 archive_dir=None,dart_transport=request_bytes,ai_transport=request_bytes):
    settings=settings or KycSettings.from_env()
    settings.require(with_ai=with_ai)
    dart=OpenDartClient(settings.dart_api_key,transport=dart_transport,archive_dir=archive_dir)
    ai=OpenAISummarizer(settings.openai_api_key,settings.model,transport=ai_transport) if with_ai else None
    result=kyc_review(company,fetch_documents=lambda query:dart.fetch_documents(query,
        start_date=start_date,end_date=end_date,max_reports=max_reports,report_type=report_type),summarize=ai)
    result.metadata.update({'source_provider':'OpenDART','report_type':{'A001':'사업보고서','A002':'반기보고서','A003':'분기보고서'}.get(report_type,report_type),
        'requested_start_date':start_date,'requested_end_date':end_date,
        'max_reports':max_reports,'ai_enabled':with_ai})
    if ai:result.metadata['ai_processing']=ai.last_metadata
    return result
