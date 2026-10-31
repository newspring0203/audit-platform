"""분석 결과의 JSON·CSV 출력."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import json
import re
import pandas as pd
from .csv_safety import spreadsheet_safe_copy


@dataclass
class AnalysisResult:
    name: str
    summary: dict
    tables: dict[str, pd.DataFrame]
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return {'module': self.name, 'summary': self.summary, 'metadata': self.metadata, 'tables': {name: json.loads(frame.to_json(orient='records', date_format='iso', force_ascii=False)) for name, frame in self.tables.items()}}

    def save(self, directory):
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        for name, frame in self.tables.items():
            if not re.fullmatch('[a-z][a-z0-9_]*', name):
                raise ValueError('잘못된 결과 테이블 이름')
            spreadsheet_safe_copy(frame).to_csv(path / f'{name}.csv', index=False, encoding='utf-8-sig')
        (path / 'summary.json').write_text(json.dumps({'module': self.name, 'summary': self.summary, 'metadata': {**self.metadata, 'csv_export_policy': '수식으로 해석될 수 있는 문자열은 다운로드 CSV에서 작은따옴표로 이스케이프합니다. 원본·분석 값은 변경하지 않습니다.'}}, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        return path
