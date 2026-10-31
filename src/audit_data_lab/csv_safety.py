"""분석 결과 CSV를 스프레드시트에서 열 때 수식으로 실행하지 않게 한다."""
import re


def safe_cell(value):
    if not isinstance(value,str):return value
    stripped=value.lstrip()
    if value.startswith(('\t','\r','\n')) or stripped.startswith(('=','+','@')):
        return "'"+value
    if stripped.startswith('-') and not re.fullmatch(r'-\d+(?:\.\d+)?',stripped):
        return "'"+value
    return value


def spreadsheet_safe_copy(frame):
    # 원본 DataFrame은 변경하지 않고 다운로드용 복사본만 이스케이프한다.
    return frame.map(safe_cell)
