"""작업 입력의 해시·형식·크기를 확인하고 파싱한다."""
from pathlib import Path
import hashlib
import pandas as pd
from audit_data_lab.common import fail


class JobInputs:
    def __init__(self, spec):
        self.folder = Path(spec["directory"])
        self.module = spec["module"]
        self.assets = spec["inputs"]
        self.frames = {}
        self.sources = {}

    def optional(self, slot):
        return self.read(slot) if slot in self.assets else None

    def read(self, slot, *, raw_report=False):
        inputs = self.assets
        folder = self.folder
        module = self.module
        if slot not in inputs:
            fail('REQUIRED_INPUT_MISSING', slot, '필요한 입력 파일이 제출되지 않았습니다.', table=module)
        item = inputs[slot]
        path = folder / 'inputs' / item['stored_name']
        if item.get('sha256') and hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            fail('SOURCE_HASH_MISMATCH', slot, '업로드 이후 자료가 달라졌습니다. 다시 업로드하세요.', table=module)
        if item['suffix'] == '.xlsx':
            with pd.ExcelFile(path) as book:
                item = {**item, 'sheet': book.sheet_names[0]}
                frame = pd.read_excel(book, sheet_name=0, dtype=object if raw_report else 'string', header=None if raw_report else 0, nrows=100001)
        else:
            raw = path.read_bytes()
            for encoding in ('utf-8-sig', 'cp949'):
                try:
                    raw.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            separator = '|' if module=='sap_preprocessing' and item['suffix']=='.txt' else ','
            frame = pd.read_csv(path, sep=separator, dtype='string', encoding=encoding, header=None if raw_report else 0, nrows=100001)
        if len(frame) > 100000 or len(frame.columns) > 256:
            fail('DATASET_LIMIT', slot, '행 또는 컬럼 한도를 초과했습니다.', table=module)
        if raw_report:
            item = {**item, 'first_data_row': 1, 'row_basis': 'QuickBooks 전체 보고서를 header=None으로 읽음. 첫 논리 레코드=1이며 제목·헤더·합계도 포함합니다.'}
        self.frames[slot] = frame.copy()
        self.sources[slot] = item
        return frame
