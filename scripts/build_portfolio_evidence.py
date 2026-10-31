"""합성 자료를 재실행하여 README의 결과 CSV와 그림을 생성한다."""
from pathlib import Path
from datetime import datetime, timezone
from html import escape
import argparse
import hashlib
import json
import sys


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def result_svg(path, title, subtitle, headers, rows, widths, note):
    width = 1280
    top, row_height = 146, 62
    bottom = top + row_height * (len(rows) + 1)
    height = bottom + 108
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
             f'<title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle + " " + note)}</desc>',
             '<rect width="100%" height="100%" fill="#ffffff"/>',
             '<g font-family="Arial Unicode MS, Apple SD Gothic Neo, sans-serif" fill="#173c30">',
             f'<text x="38" y="50" font-size="27" font-weight="bold">{escape(title)}</text>',
             f'<text x="38" y="90" font-size="18" fill="#52665d">{escape(subtitle)}</text>']
    x_positions = [38]
    for col_width in widths[:-1]:
        x_positions.append(x_positions[-1] + col_width)
    parts.append(f'<rect x="28" y="{top}" width="1224" height="{row_height}" fill="#e9f0ec"/>')
    for x, value in zip(x_positions, headers):
        parts.append(f'<text x="{x}" y="{top+39}" font-size="20" font-weight="bold">{escape(value)}</text>')
    for index, values in enumerate(rows):
        y = top + (index + 1) * row_height
        if index % 2 == 0:
            parts.append(f'<rect x="28" y="{y}" width="1224" height="{row_height}" fill="#f7f9f8"/>')
        for x, value in zip(x_positions, values):
            parts.append(f'<text x="{x}" y="{y+39}" font-size="20">{escape(str(value))}</text>')
        parts.append(f'<path d="M28 {y+row_height}H1252" stroke="#dae3dd"/>')
    parts += [f'<text x="38" y="{bottom+42}" font-size="19">{escape(note)}</text>',
              f'<text x="38" y="{bottom+77}" font-size="16" fill="#52665d">합성 입력 자료를 Python 함수로 재실행한 결과 표이다. 웹 화면 캡처가 아니다.</text>', '</g></svg>']
    path.write_text('\n'.join(parts), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = args.output_dir.resolve() if args.output_dir else root / 'docs/portfolio'
    sys.path.insert(0, str(root / 'src'))
    import pandas as pd
    from audit_data_lab import cash_proofing, ar_confirmation_review
    evidence = output / 'evidence'
    images = output / 'images'
    evidence.mkdir(parents=True, exist_ok=True)
    images.mkdir(parents=True, exist_ok=True)
    files = ['data/demo/v1/bank.csv', 'data/demo/v1/cash_gl.csv', 'data/demo/v1/balances.csv']
    files += [f'data/demo/confirmations/AR_{slot}.csv' for slot in ['ledger','requests','replies']]
    frames = [pd.read_csv(root / name, dtype='string') for name in files]
    cash_config = {'date_tolerance_days':1, 'as_of':'20261031', 'aging_days':30}
    cash = cash_proofing(*frames[:2], **cash_config, balances=frames[2])
    ar_config = {'as_of':'20261031', 'amount_tolerance':0}
    ar = ar_confirmation_review(*frames[3:], **ar_config)
    for label, result in [('cash',cash),('ar',ar)]:
        for table_name, table in result.tables.items():
            table.to_csv(evidence / f'{label}_{table_name}.csv', index=False)
    # Expected outcomes come from the deliberately constructed fixtures.
    assert cash.summary['matched_count'] == 2
    assert cash.summary['ambiguous_candidate_count'] == 2
    assert ar.tables['confirmation_comparison'].Status.tolist() == ['matched','difference','no_reply','partial','date_mismatch','not_requested']
    assert ar.tables['confirmation_comparison'].Difference.iloc[2:].isna().all()
    cash_rows = []
    for row in cash.tables['candidate_links'].itertuples():
        cash_rows.append([row.Row_ID_Bank, row.Row_ID_GL, f'{row.Amount:,.0f}', f'{abs(row.Date_Difference_Days)}일',
                          '자동 연결' if row.Candidate_Status == 'unique' else '중복 후보 · 미연결'])
    result_svg(images/'cash-result.svg', '자금 대사에서 중복 후보를 자동 연결하지 않는 처리',
               '기준일 2026-10-31 · KRW · 허용 시차 1일 · 은행 5행 / 장부 4행',
               ['은행 행','장부 행','금액','일자 차이','처리 결과'], cash_rows, [175,175,220,170,484],
               '유일 후보 2쌍만 연결한다. 3,000원 후보 2개는 원본 증빙을 확인할 대상으로 남긴다.')
    status = {'matched':'일치','difference':'금액 차이','no_reply':'미회신','partial':'부분 회신',
              'date_mismatch':'기준일 차이','not_requested':'미요청'}
    def number(value):
        return '—' if pd.isna(value) else f'{value:,.0f}'
    ar_rows = []
    for row in ar.tables['confirmation_comparison'].itertuples():
        ar_rows.append([row.Request_ID or '요청 없음',number(row.Book_Balance),number(row.Confirmed_Balance),
                        number(row.Difference),status[row.Status]])
    result_svg(images/'ar-result.svg', '매출채권 조회 회신에서 금액과 비교 가능 여부를 구분',
               '기준일 2026-10-31 · KRW · 장부 6행 / 요청 5행 / 회신 4행',
               ['요청 ID','장부 잔액','회신 잔액','계산 차이','회신 상태'], ar_rows,[195,220,220,200,389],
               '부분 회신·기준일 차이는 금액이 같아도 차이를 계산하지 않는다. —는 0이 아니다.')
    sources = ['src/audit_data_lab/cash.py','src/audit_data_lab/confirmations.py','src/audit_data_lab/common.py',
               'src/audit_data_lab/validation.py','src/audit_data_lab/cash_balances.py','scripts/build_portfolio_evidence.py']
    manifest = {'generated_at_utc':datetime.now(timezone.utc).isoformat(), 'data_kind':'synthetic',
                'cash':{'parameters':cash_config,'summary':cash.summary}, 'ar':{'parameters':ar_config,'summary':ar.summary},
                'input_sha256':{name:sha256(root/name) for name in files},
                'source_sha256':{name:sha256(root/name) for name in sources if (root/name).is_file()},
                'generated_files_sha256':{str(p.relative_to(output)):sha256(p) for p in [*sorted(evidence.glob('*.csv')),images/'cash-result.svg',images/'ar-result.svg']}}
    (evidence/'run_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Synthetic evidence regenerated: cash 2 matches, AR 6 comparison states.')


if __name__ == '__main__':
    main()
