"""웹 API와 노트북에서 공유할 SAP 입력 검사. 파일 저장은 호출자가 담당한다."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import pandas as pd

SOURCE_ROW = '__source_row'
KEYS = ['BUKRS (Company Code)', 'GJAHR (Fiscal Year)', 'BELNR (Accounting Document Number)']
LINE = 'BUZEI (Number of Line Item Within Accounting Document)'
POST = 'BUDAT (Posting Date in the Document)'
PERIOD = 'MONAT (Fiscal Period)'
AMOUNT = 'DMBTR (Amount in Local Currency)'
CURRENCY = 'HWAER (Local Currency)'
OPENING = 'HSLVT (Balance carried forward in local currency (currency 2))'
FILES = {
    'BSEG': 'BSEG_0001_Accounting Document Segment.xlsx',
    'BKPF': 'SAP_BKPF_전표헤더.txt',
    'GLT0': 'GLT0_0001_GL account master record transaction figures.xlsx',
}

def plain(value):
    """pandas 결측값 및 numpy 값을 JSON 기본값으로 바꾼다."""
    if value is None or pd.isna(value):
        return None
    return str(value)

@dataclass(frozen=True)
class ValidationIssue:
    code: str
    field: str
    message: str
    source_table: str
    source_file: str
    source_row: int | None = None
    source_field: str | None = None
    value: str | None = None
    journal_id: str | None = None
    severity: str = 'error'

class DataValidationError(ValueError):
    """.to_dict()는 FastAPI 응답에, .to_frame()은 노트북 표에 사용한다."""
    def __init__(self, issues):
        self.issues = list(issues)
        super().__init__('; '.join(i.message for i in self.issues[:5]) +
                         (f' (총 {len(self.issues)}건)' if len(self.issues) > 5 else ''))

    def to_dict(self):
        return {'status': 'validation_failed', 'error_count': len(self.issues),
                'errors': [asdict(i) for i in self.issues]}

    def to_frame(self):
        return pd.DataFrame([asdict(i) for i in self.issues], columns=ValidationIssue.__dataclass_fields__)


def save_validation_report(directory, error=None):
    """빈 보고서도 저장하여 직전 실행의 오류 목록이 남지 않게 한다."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    result = error or DataValidationError([])
    payload = result.to_dict()
    if error is None:
        payload['status'] = 'input_validation_passed'
    (directory / 'validation_errors.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    from .csv_safety import spreadsheet_safe_copy
    spreadsheet_safe_copy(result.to_frame()).to_csv(directory / 'validation_errors.csv', index=False, encoding='utf-8-sig')


def validate_sap_inputs(bseg, bkpf, glt0, *, company, year, ledger, record_type, version):
    """전체 입력을 검사해 여러 오류를 모은다. 성공하면 출처 행을 보존한 복사본을 반환한다.

    source_row는 헤더를 1행으로 센 논리적 표 행 번호다(첫 데이터=2).
    TXT에 여러 줄 인용 필드가 있으면 물리적 파일 줄 번호와 다를 수 있다.
    """
    frames = {}
    issues = []
    def add(table, code, field, message, row=None, source_field=None):
        journal = None
        if row is not None and table in ('BSEG', 'BKPF') and all(k in row for k in KEYS):
            if all(pd.notna(row[k]) for k in KEYS):
                journal = ':'.join(str(row[k]) for k in KEYS)
        issues.append(ValidationIssue(
            code=code, field=field, message=message, source_table=table,
            source_file=FILES[table], source_row=int(row[SOURCE_ROW]) if row is not None else None,
            source_field=source_field, value=plain(row[source_field]) if row is not None and source_field in row else None,
            journal_id=journal))

    for table, original in [('BSEG', bseg), ('BKPF', bkpf), ('GLT0', glt0)]:
        frame = original.copy().reset_index(drop=True)
        frame.columns = frame.columns.str.strip()
        if frame.columns.duplicated().any():
            add(table, 'DUPLICATE_COLUMNS', '*', '중복된 컬럼명이 있습니다.')
            continue
        for c in frame:
            frame[c] = frame[c].astype('string').str.strip().replace('', pd.NA)
        # 외부에서 전달된 행 번호는 신뢰하지 않고 로딩 순서로 계산한다.
        frame[SOURCE_ROW] = range(2, len(frame) + 2)
        frames[table] = frame
    if issues:
        raise DataValidationError(issues)

    tb_scope = ['BUKRS (Company Code)', 'RYEAR (Fiscal Year)', 'RLDNR (Ledger)', 'RRCTY (Record Type)', 'RVERS (Version)']
    tb_periods = [f'HSL{n:02d} (Total transactions in the period in local currency (curr 2))' for n in range(1,17)]
    required = {
        'BSEG': KEYS + [LINE, 'GSBER (Business Area)', 'SGTXT (Item Text)', 'HKONT (General Ledger Account)', AMOUNT, 'SHKZG (Debit/Credit Indicator)'],
        'BKPF': KEYS + ['BKTXT (Document Header Text)', 'BLART (Document Type)', POST,
            'BLDAT (Document Date in Document)', 'CPUDT (Day On Which Accounting Document Was Entered)',
            'CPUTM (Time of Entry)', PERIOD, 'USNAM (User name)', CURRENCY],
        'GLT0': tb_scope + ['RACCT (Account Number)', 'RBUSA (Business Area)', OPENING] + tb_periods,
    }
    for table, columns in required.items():
        for c in columns:
            if c not in frames[table]:
                add(table, 'MISSING_COLUMN', c, f'필요한 컬럼이 없습니다: {c}', source_field=c)
    if issues:
        raise DataValidationError(issues)

    def check(table, frame, mask, code, field, message, column):
        for _, row in frame.loc[mask.fillna(False)].iterrows():
            add(table, code, field, message, row, column)

    # 범위 선택 전에 검사하여 회사/연도 누락 행이 조용히 사라지지 않게 한다.
    for table in ('BSEG', 'BKPF', 'GLT0'):
        f = frames[table]
        scope_keys = KEYS[:2] if table != 'GLT0' else tb_scope
        for c in scope_keys:
            check(table, f, f[c].isna(), 'MISSING_SCOPE_KEY', c, '범위 선택 키에 결측값이 있습니다.', c)
    b = frames['BSEG'].loc[frames['BSEG'][KEYS[0]].eq(company) & frames['BSEG'][KEYS[1]].eq(year)]
    h = frames['BKPF'].loc[frames['BKPF'][KEYS[0]].eq(company) & frames['BKPF'][KEYS[1]].eq(year)]
    t = frames['GLT0']
    mask = pd.Series(True, index=t.index)
    for c, value in zip(tb_scope, [company,year,ledger,record_type,version]):
        mask &= t[c].eq(value)
    t = t.loc[mask.fillna(False)]
    for table, f in [('BSEG',b),('BKPF',h),('GLT0',t)]:
        if f.empty:
            add(table, 'EMPTY_SCOPE', '*', f'선택 범위에 {table} 데이터가 없습니다.')

    for table, f in [('BSEG',b),('BKPF',h)]:
        for c in KEYS + ([LINE] if table == 'BSEG' else []):
            check(table,f,f[c].isna(),'MISSING_KEY', 'Journal_ID_Line_Number' if c==LINE else 'Journal_ID',
                  '전표 키에 결측값이 있습니다.', c)
        duplicate_keys = KEYS + ([LINE] if table == 'BSEG' else [])
        check(table,f,f.duplicated(duplicate_keys,keep=False),'DUPLICATE_DETAIL' if table=='BSEG' else 'DUPLICATE_HEADER',
              'Journal_ID', '상세행 키가 중복됩니다.' if table=='BSEG' else '헤더 키가 중복됩니다.', KEYS[2])
    header_keys = set(h[KEYS].dropna().itertuples(index=False,name=None))
    for _, row in b.dropna(subset=KEYS).iterrows():
        if tuple(row[k] for k in KEYS) not in header_keys:
            add('BSEG','HEADER_NOT_FOUND','Journal_ID','헤더 미연결 행이 있습니다.',row,KEYS[2])

    def amounts(table, f, column, field):
        for _, row in f.iterrows():
            value = row[column]
            if pd.isna(value):
                add(table,'MISSING_AMOUNT',field,'금액에 결측값이 있습니다.',row,column)
                continue
            try:
                amount = Decimal(str(value))
                if not amount.is_finite():
                    raise InvalidOperation
            except InvalidOperation:
                add(table,'INVALID_AMOUNT',field,'잘못된 금액입니다.',row,column)
                continue
            if amount * 100 != (amount * 100).to_integral_value():
                add(table,'AMOUNT_PRECISION',field,'소수 둘째 자리 초과 금액입니다.',row,column)
    amounts('BSEG',b,AMOUNT,'Amount')
    for c in [OPENING] + tb_periods:
        amounts('GLT0',t,c,'Amount_Beginning' if c==OPENING else 'Amount_Ending')
    check('BSEG',b,~b['SHKZG (Debit/Credit Indicator)'].isin(['S','H']),'INVALID_DC_CODE',
          'Amount_Credit_Debit_Indicator','알 수 없는 차대변 코드가 있습니다.','SHKZG (Debit/Credit Indicator)')
    for table,f,c in [('BSEG',b,'HKONT (General Ledger Account)'),('GLT0',t,'RACCT (Account Number)')]:
        check(table,f,f[c].isna(),'MISSING_ACCOUNT','GL_Account_Number','계정번호 누락이 있습니다.',c)
    check('BKPF',h,~h[CURRENCY].str.fullmatch(r'[A-Z]{3}').fillna(False),'INVALID_CURRENCY',
          'Amount_Currency','통화는 영문 대문자 3자리 코드여야 합니다.',CURRENCY)
    if h[CURRENCY].dropna().nunique() > 1:
        check('BKPF',h,pd.Series(True,index=h.index),'MULTIPLE_CURRENCIES','Amount_Currency','단일 기능통화 기준을 확인하세요.',CURRENCY)

    # 잘못된 날짜·기간을 강제 변환하지 않고, 서로 독립적으로 검사한다.
    date_columns=[(POST,'Effective_Date'),('CPUDT (Day On Which Accounting Document Was Entered)','Entered_Date')]
    for column,field in date_columns:
        parsed = pd.to_datetime(h[column],format='%Y%m%d',errors='coerce')
        valid = h[column].str.fullmatch(r'\d{8}').fillna(False) & parsed.notna()
        message = '전기일이 비어 있거나 날짜 형식이 잘못됐습니다.' if column==POST else '입력일이 비어 있거나 날짜 형식이 잘못됐습니다.'
        check('BKPF',h,~valid,'INVALID_DATE',field,message,column)
    posting = pd.to_datetime(h[POST],format='%Y%m%d',errors='coerce')
    period = pd.to_numeric(h[PERIOD],errors='coerce')
    period_valid = h[PERIOD].str.fullmatch(r'\d{1,2}').fillna(False) & period.between(1,16)
    check('BKPF',h,~period_valid,'INVALID_PERIOD','Period','회계기간 범위 또는 형식이 잘못됐습니다. 정수 1~16이어야 합니다.',PERIOD)
    check('BKPF',h,posting.notna() & posting.dt.year.ne(int(year)),'FISCAL_YEAR_MISMATCH',
          'Effective_Date','달력연도와 회계연도가 다릅니다.',POST)
    check('BKPF',h,period_valid & period.le(12) & posting.notna() & posting.dt.month.ne(period),
          'PERIOD_DATE_MISMATCH','Period','달력 월과 회계기간이 다릅니다. 회계 달력 설정을 확인하세요.',PERIOD)
    check('BKPF',h,period_valid & period.ge(13) & posting.notna() & ~((posting.dt.month==12)&(posting.dt.day==31)),
          'SPECIAL_PERIOD_DATE_MISMATCH','Effective_Date','달력연도 기준 특별기간의 전기일은 연말이어야 합니다.',POST)
    time_col='CPUTM (Time of Entry)'
    times=h[time_col].str.zfill(6)
    valid_time=times.str.fullmatch(r'\d{6}').fillna(False) & pd.to_datetime(times,format='%H%M%S',errors='coerce').notna()
    check('BKPF',h,~valid_time,'INVALID_TIME','Entered_Time','입력시간 형식이 잘못됐습니다.',time_col)
    if issues:
        raise DataValidationError(issues)
    return frames['BSEG'], frames['BKPF'], frames['GLT0']
