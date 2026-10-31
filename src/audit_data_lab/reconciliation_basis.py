"""금액 대사 실행 전 확인 근거와 입력 데이터의 연결을 검사한다.
첨부 근거의 의미상 적정성은 감사 담당자의 검토 사항이며 이 검사가 대신하지 않는다.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
import hashlib
from pathlib import Path
import re
import pandas as pd
from .validation import ValidationIssue


def frame_fingerprint(frame):
    """입력 컬럼·행 순서·값에 결합한다. 검토 후 데이터 변경 시 재확인이 필요하다."""
    normalized=frame.astype('string')
    raw=normalized.to_json(orient='split',index=False,force_ascii=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

@dataclass(frozen=True)
class EvidenceFile:
    relative_path: str
    sha256: str
    description: str

@dataclass(frozen=True)
class LogBasisConfirmation:
    gl_source_amount_field: str=''
    log_source_amount_field: str=''
    gl_currency_basis: str=''
    log_currency_basis: str=''
    company: str=''
    fiscal_year: str=''
    ledger: str=''
    period_start: str=''
    period_end: str=''
    extraction_description: str=''
    gl_fingerprint: str=''
    log_fingerprint: str=''
    confirmed_by: str=''
    reviewed_by: str=''
    reviewed_at: str=''
    currency_mode: str=''  # row_currency 또는 confirmed_single_currency
    confirmed_currency: str=''
    evidence_files: tuple[EvidenceFile,...]=field(default_factory=tuple)

@dataclass
class BasisCheck:
    status: str
    issues: list
    log_currency: pd.Series | None=None
    metadata: dict=field(default_factory=dict)

    def to_frame(self):
        return pd.DataFrame([asdict(i) for i in self.issues],columns=ValidationIssue.__dataclass_fields__)


def check_log_basis(gl,log,confirmation=None,*,evidence_root=None):
    issues=[]
    def issue(code,field,message):
        issues.append(ValidationIssue(code=code,field=field,message=message,
            source_table='LogBasis',source_file='대사 기준 확인서'))
    if confirmation is None:
        issue('BASIS_INFORMATION_MISSING','LogBasis','금액 필드·통화·범위의 확인 근거와 검토 기록이 없어 로그 대사를 실행하지 않았습니다.')
        return BasisCheck('basis_information_missing',issues)
    if not isinstance(confirmation,LogBasisConfirmation):
        issue('BASIS_INFORMATION_MISSING','LogBasis','올바른 형식의 대사 기준 확인서가 필요합니다.')
        return BasisCheck('basis_information_missing',issues)
    c=confirmation
    required=['gl_source_amount_field','log_source_amount_field','gl_currency_basis','log_currency_basis',
        'company','fiscal_year','ledger','period_start','period_end','extraction_description',
        'gl_fingerprint','log_fingerprint','confirmed_by','reviewed_by','reviewed_at','currency_mode']
    for name in required:
        if not isinstance(getattr(c,name),str) or not getattr(c,name).strip():
            issue('BASIS_INFORMATION_MISSING',name,'대사 기준 확인서에 필요한 정보가 없습니다.')
    if not c.evidence_files:issue('BASIS_INFORMATION_MISSING','evidence_files','추출 명세·보고서 설정 등 확인 근거 파일이 필요합니다.')
    if evidence_root is None:issue('BASIS_INFORMATION_MISSING','evidence_root','확인 근거 보관 위치가 지정되지 않았습니다.')
    if issues:return BasisCheck('basis_information_missing',issues)
    # 모든 조건을 수집하며, 형식이나 파일이 확인되지 않으면 숫자 대사를 하지 않는다.
    if c.gl_source_amount_field!=c.log_source_amount_field:
        issue('AMOUNT_BASIS_MISMATCH','source_amount_field','GL과 로그의 원본 금액 필드가 다릅니다. 자동 변환·환산을 지원하지 않습니다.')
    if c.gl_currency_basis not in ('functional','group') or c.log_currency_basis!=c.gl_currency_basis:
        issue('CURRENCY_BASIS_MISMATCH','currency_basis','같은 기능통화 또는 그룹통화 기준이 확인되지 않았습니다.')
    try:
        start=datetime.strptime(c.period_start,'%Y%m%d');end=datetime.strptime(c.period_end,'%Y%m%d')
        valid=bool(re.fullmatch(r'\d{8}',c.period_start) and re.fullmatch(r'\d{8}',c.period_end)) and start<=end
    except (ValueError,TypeError):valid=False
    if not valid:issue('INVALID_BASIS_PERIOD','period','확인서의 조회 기간이 잘못됐습니다.')
    try:
        datetime.strptime(c.reviewed_at,'%Y-%m-%d')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',c.reviewed_at):raise ValueError
    except (ValueError,TypeError):issue('INVALID_REVIEW_DATE','reviewed_at','검토일은 YYYY-MM-DD 형식이어야 합니다.')
    if c.gl_fingerprint!=frame_fingerprint(gl):issue('REVIEWED_INPUT_CHANGED','gl_fingerprint','검토한 GL과 현재 입력이 다릅니다. 재검토가 필요합니다.')
    if c.log_fingerprint!=frame_fingerprint(log):issue('REVIEWED_INPUT_CHANGED','log_fingerprint','검토한 로그와 현재 입력이 다릅니다. 재검토가 필요합니다.')
    expected_prefix=c.company+':'+c.fiscal_year+':'
    for name,frame in [('GL',gl),('Log',log)]:
        ids=frame['Journal_ID'].astype('string')
        if not ids.str.startswith(expected_prefix).fillna(False).all():
            issue('BASIS_SCOPE_MISMATCH',name,'전표의 회사·회계연도와 확인서 범위가 다릅니다.')
    if not gl['Fiscal_Year'].astype('string').eq(c.fiscal_year).all():
        issue('BASIS_SCOPE_MISMATCH','Fiscal_Year','GL 회계연도와 확인서가 다릅니다.')
    if valid:
        dates=pd.to_datetime(gl['Effective_Date'].astype('string'),format='%Y%m%d',errors='coerce')
        if not dates.between(start,end).fillna(False).all():issue('BASIS_SCOPE_MISMATCH','Effective_Date','확인 범위 밖의 GL 전기일이 있습니다.')
    root=Path(evidence_root).resolve();verified=[]
    for evidence in c.evidence_files:
        if not isinstance(evidence,EvidenceFile):
            issue('INVALID_EVIDENCE_REFERENCE','evidence_files','근거 파일 참조 형식이 잘못됐습니다.');continue
        if not evidence.description.strip() or not re.fullmatch(r'[a-f0-9]{64}',evidence.sha256):
            issue('INVALID_EVIDENCE_REFERENCE','evidence_files','근거 설명 또는 SHA-256이 잘못됐습니다.');continue
        relative=Path(evidence.relative_path)
        target=(root/relative).resolve()
        if relative.is_absolute() or root not in target.parents:
            issue('INVALID_EVIDENCE_PATH','evidence_files','지정된 근거 폴더 밖의 파일은 사용할 수 없습니다.');continue
        try:
            if not target.is_file():raise OSError
            actual=hashlib.sha256(target.read_bytes()).hexdigest()
        except OSError:
            issue('EVIDENCE_FILE_UNAVAILABLE','evidence_files','확인 근거 파일을 읽을 수 없습니다.');continue
        if actual!=evidence.sha256:issue('EVIDENCE_FILE_CHANGED','evidence_files','확인 근거 파일이 변경됐습니다. 재검토가 필요합니다.')
        else:verified.append(asdict(evidence))
    currency=None
    if c.currency_mode=='row_currency':
        if 'Amount_Currency' not in log:issue('BASIS_INFORMATION_MISSING','Amount_Currency','통화별 로그 컬럼이 없습니다.')
        else:
            currency=log['Amount_Currency'].astype('string').str.strip()
            if not currency.str.fullmatch(r'[A-Z]{3}').fillna(False).all():issue('INVALID_LOG_CURRENCY','Amount_Currency','로그 통화 값이 비어 있거나 형식이 잘못됐습니다.')
            if c.confirmed_currency:issue('AMBIGUOUS_CURRENCY_MODE','currency_mode','행별 통화와 단일 통화 지정은 동시에 사용하지 않습니다.')
    elif c.currency_mode=='confirmed_single_currency':
        if not re.fullmatch(r'[A-Z]{3}',c.confirmed_currency):issue('BASIS_INFORMATION_MISSING','confirmed_currency','근거로 확인한 단일 통화 코드가 필요합니다.')
        else:
            currency=pd.Series(c.confirmed_currency,index=log.index,dtype='string')
            if 'Amount_Currency' in log:
                existing=log['Amount_Currency'].astype('string').str.strip()
                if not existing.eq(c.confirmed_currency).fillna(False).all():issue('LOG_CURRENCY_CONFLICT','Amount_Currency','로그의 기존 통화를 다른 값으로 덮어쓸 수 없습니다.')
            if not gl['Amount_Currency'].astype('string').eq(c.confirmed_currency).all():issue('GL_CURRENCY_CONFLICT','Amount_Currency','GL 통화가 확인된 단일 통화와 다릅니다.')
    else:issue('BASIS_INFORMATION_MISSING','currency_mode','행별 통화 또는 근거로 확인된 단일 통화 방식을 지정하세요.')
    if issues:
        if any(i.code=='BASIS_INFORMATION_MISSING' for i in issues):status='basis_information_missing'
        elif any(i.code in ('AMOUNT_BASIS_MISMATCH','CURRENCY_BASIS_MISMATCH','BASIS_SCOPE_MISMATCH','LOG_CURRENCY_CONFLICT','GL_CURRENCY_CONFLICT') for i in issues):status='basis_not_comparable'
        else:status='basis_evidence_invalid'
        return BasisCheck(status,issues)
    metadata=asdict(c);metadata['evidence_files']=verified
    metadata['limitation']='근거 파일·검토 기록과 입력 연결을 확인했습니다. 근거 내용의 적정성이나 감사증거 충분성을 자동 보증하지 않습니다.'
    return BasisCheck('ready',[],currency,metadata)
