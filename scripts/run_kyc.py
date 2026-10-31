"""공개 공시 KYC 실행. 기본값은 OpenDART 수집만, --with-ai일 때만 AI 호출."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from audit_data_lab.kyc_live import run_live_kyc
from audit_data_lab.kyc_settings import KycSettings,load_project_env
from audit_data_lab.kyc_dart import OpenDartClient
from audit_data_lab.kyc_transport import provider_error
from audit_data_lab.validation import DataValidationError,save_validation_report


def main():
    today=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d')
    parser=argparse.ArgumentParser(description='OpenDART 사업보고서 수집 및 선택적 AI KYC 요약')
    parser.add_argument('--company',help='선택한 정확한 회사명 또는 DART 8자리 고유번호')
    parser.add_argument('--find-company',help='회사명 일부 또는 종목코드로 후보 검색')
    parser.add_argument('--start',default=f'{int(today[:4])-1}0101')
    parser.add_argument('--end',default=today)
    parser.add_argument('--max-reports',type=int,default=1)
    parser.add_argument('--with-ai',action='store_true',help='OpenAI API를 실제 호출합니다. 사용 요금이 발생할 수 있습니다.')
    parser.add_argument('--check-config',action='store_true',help='키 값은 출력하지 않고 설정 여부만 확인')
    args=parser.parse_args()
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=ROOT/'outputs/kyc'/run_id
    try:
        load_project_env(ROOT)
        settings=KycSettings.from_env()
        if args.check_config:
            print(json.dumps({'dart_key_configured':bool(settings.dart_api_key),
                'openai_key_configured':bool(settings.openai_api_key),'openai_model_configured':bool(settings.model)},ensure_ascii=False,indent=2))
            return 0
        if args.find_company:
            settings.require()
            matches=OpenDartClient(settings.dart_api_key).find_companies(args.find_company)
            print(json.dumps({'companies':matches[:100],'total_count':len(matches)},ensure_ascii=False,indent=2))
            return 0
        if not args.company:
            provider_error('COMPANY_REQUIRED','--find-company로 회사를 검색한 뒤 --company에 회사명 또는 DART 고유번호를 지정하세요.','Config')
        result=run_live_kyc(args.company,start_date=args.start,end_date=args.end,max_reports=args.max_reports,
            with_ai=args.with_ai,settings=settings,archive_dir=ROOT/'data/raw/dart'/run_id)
        result.save(out)
        print(json.dumps(result.summary,ensure_ascii=False,indent=2))
        print('저장 위치:',out)
        return 0
    except DataValidationError as error:
        save_validation_report(out,error)
        print(json.dumps(error.to_dict(),ensure_ascii=False,indent=2))
        return 2

if __name__=='__main__':raise SystemExit(main())
