"""계산 실패도 검토 결과로 반환하는 서비스 계층. 웹 요청을 예외 화면으로 끝내지 않는다."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
from .common import AnalysisResult
from .validation import DataValidationError, ValidationIssue

NEXT_ACTIONS={
    'BASIS_INFORMATION_MISSING':'금액·통화·범위의 추출 명세와 확인·검토 기록을 확보하세요.',
    'MISSING_COLUMN':'원본 컬럼과 매핑 설정을 확인하고 필요한 컬럼을 포함해 다시 제출하세요.',
    'REVIEWED_INPUT_CHANGED':'검토한 원본과 현재 파일을 비교하고 변경분을 재검토하세요.',
    'COMPARISON_PERIOD_MISSING':'비교할 두 기간의 자료를 모두 제출하세요.',
    'DISCLOSURE_NOT_FOUND':'회사와 조회 기간을 확인하고 공시 존재 여부를 확인하세요.',
}


def execute_analysis(name,operation,*,context=None):
    """operation 안에 입력 읽기·검사·계산을 넣는다. 예상 오류는 결과표로 반환한다.

    실제 계산을 못 한 경우 계산 결과를 만들어내지 않는다. 예기치 않은 내부 예외는
    사용자에게 내부 경로·인증정보를 노출하지 않고 문의용 코드만 반환한다.
    """
    if not re.fullmatch(r'[a-z][a-z0-9_]*',name):raise ValueError('분석 식별자를 확인하세요.')
    safe_context={k:v for k,v in (context or {}).items() if k in {'company','fiscal_year','period','input_files','request_id'}}
    try:
        result=operation()
        if not isinstance(result,AnalysisResult):raise TypeError('AnalysisResult 반환 필요')
        result.metadata['request_context']=safe_context
        blocked=result.summary.get('log_amount_reconciliation_status','')
        has_issues=any(name in result.tables and not result.tables[name].empty for name in ['module_issues','log_basis_issues'])
        status='completed_with_limitations' if blocked.startswith('basis_') or has_issues else 'completed'
        result.metadata['execution_status']=status
        result.metadata['review_status']='미검토'
        return result
    except DataValidationError as error:
        issues=error.to_frame()
        issues['suggested_review']=[NEXT_ACTIONS.get(i.code,'원본 값과 검사 조건을 확인하고 재실행하세요.') for i in error.issues]
        status='not_executed_input_issue'
    except FileNotFoundError:
        issues=DataValidationError([ValidationIssue(code='INPUT_FILE_UNAVAILABLE',field='Input',
            message='필요한 입력 파일을 찾을 수 없습니다. 제출 파일을 확인하세요.',source_table=name,source_file=name)]).to_frame()
        issues['suggested_review']='필요한 입력 파일을 제출하세요.'
        status='not_executed_input_issue'
    except Exception:
        issues=DataValidationError([ValidationIssue(code='INTERNAL_PROCESSING_ERROR',field='System',
            message='내부 처리 문제로 계산하지 못했습니다. 담당자에게 실행 기록 확인을 요청하세요.',source_table=name,source_file=name)]).to_frame()
        issues['suggested_review']='담당자에게 모듈명·실행 식별자를 전달하세요. 원본 또는 키를 채팅에 보내지 마세요.'
        status='not_executed_system_issue'
    return AnalysisResult(name,{'execution_status':status,'issue_count':len(issues),
        'calculation_performed':False}, {'validation_issues':issues},
        {'execution_status':status,'review_status':'미검토','request_context':safe_context,
         'limitation':'계산 미실행 결과입니다. 빈 분석 결과를 정상 또는 차이 없음으로 해석하지 마세요.'})


def execute_batch(operations,*,context=None):
    """서로 독립적인 모듈은 하나가 실패해도 나머지 결과를 수집한다."""
    return {name:execute_analysis(name,operation,context=context) for name,operation in operations.items()}
