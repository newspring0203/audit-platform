"""현금 거래의 후보 연결과 미대사 검토."""
from bisect import bisect_left, bisect_right
import pandas as pd
from .analysis_notes import ANALYSIS_NOTES
from .common import AnalysisResult, columns, date_values, fail, money, text
from .cash_balances import review_balances


def cash_proofing(bank, cash_gl, *, date_tolerance_days=0, as_of=None,
                  aging_days=30, balances=None, max_candidate_links=10000):
    for name, value in [('date_tolerance_days', date_tolerance_days), ('aging_days', aging_days)]:
        if isinstance(value, bool) or not isinstance(value, int) or (not 0 <= value <= 3650):
            fail('INVALID_PARAMETER', name, '일수 조건은 0~3650의 정수여야 합니다.', table='Cash')
    if not isinstance(max_candidate_links, int) or not 1 <= max_candidate_links <= 100000:
        raise ValueError('후보 연결 한도를 확인하세요.')
    b = _prepare_transactions(bank, 'Bank', as_of)
    g = _prepare_transactions(cash_gl, 'Cash_GL', as_of)
    links, bank_counts, gl_counts, limited = _build_candidates(
        b, g, date_tolerance_days, max_candidate_links,
    )
    matched, candidate_frame, matched_b, matched_g = _build_matches(
        b, g, links, bank_counts, gl_counts,
    )
    unmatched_b, unmatched_g, review_frame = _review_unmatched(
        b, g, matched_b, matched_g, bank_counts, gl_counts, limited, as_of, aging_days,
    )
    issues = []
    for account, currency, amount in limited:
        issues.append({'code': 'CANDIDATE_LIMIT', 'field': 'Amount', 'message': '중복 후보 한도를 초과한 그룹을 자동 연결에서 제외했습니다.', 'source_file': 'Cash', 'Bank_Account': account, 'Currency': currency, 'suggested_review': '해당 그룹에 전표 참조번호 등 추가 식별자를 확보하세요.'})
    balance_result, balance_status, balance_issues = review_balances(balances, as_of)
    issues.extend(balance_issues)
    clean=lambda f:f.drop(columns=['_date'],errors='ignore')
    return AnalysisResult('cash_proofing',{'bank_row_count':len(b),'gl_row_count':len(g),'matched_count':len(matched),
        'timing_match_count':int(matched['Date_Difference_Days'].ne(0).sum()),
        'unmatched_bank_count':len(unmatched_b),'unmatched_gl_count':len(unmatched_g),'ambiguous_candidate_count':int(candidate_frame['Candidate_Status'].eq('ambiguous').sum()),
        'candidate_limit_group_count':len(limited),'balance_reconciliation_status':balance_status},
        {'matches':matched,'candidate_links':candidate_frame,'unmatched_bank':clean(unmatched_b),'unmatched_gl':clean(unmatched_g),
         'review_items':review_frame,'balance_reconciliation':balance_result,'module_issues':pd.DataFrame(issues)},
        {'date_tolerance_days':date_tolerance_days,'as_of':as_of,'aging_days':aging_days,
         'matching_basis':ANALYSIS_NOTES['cash_proofing']['matching_basis'],
         'sign_convention':ANALYSIS_NOTES['cash_proofing']['sign_convention'],
         'balance_formula':ANALYSIS_NOTES['cash_proofing']['balance_formula'],
         'limitation':ANALYSIS_NOTES['cash_proofing']['limitation']})


def _prepare_transactions(frame, table, as_of):
    columns(frame, ['Row_ID', 'Bank_Account', 'Currency', 'Date', 'Amount'], table)
    f = frame.copy().reset_index(drop=True)
    for c in ['Row_ID', 'Bank_Account', 'Currency', 'Date']:
        f[c] = text(f, c, table)
    if f['Row_ID'].duplicated().any():
        fail('DUPLICATE_KEY', 'Row_ID', '거래 행 ID가 중복됩니다.', table=table)
    if not f['Currency'].str.fullmatch('[A-Z]{3}').all():
        fail('INVALID_CURRENCY', 'Currency', '통화 형식을 확인하세요.', table=table)
    f['_date'] = pd.to_datetime(date_values(f['Date'], 'Date', table))
    f['_amount_cents'] = money(f['Amount'], 'Amount', table)
    f['Source_Row'] = range(2, len(f) + 2)
    if as_of is not None:
        end = date_values(pd.Series([as_of]), 'As_Of', 'Config').iloc[0]
        if f['_date'].gt(end).any():
            fail('DATE_SCOPE_MISMATCH', 'Date', '기준일 이후 거래가 포함되어 있습니다.', table=table)
    return f


def _build_candidates(b, g, date_tolerance_days, max_candidate_links):
    keys = ['Bank_Account', 'Currency', '_amount_cents']
    links = []
    bank_counts = {}
    gl_counts = {}
    limited = []
    grouped_g = {key: part.sort_values(['_date', 'Row_ID']) for key, part in g.groupby(keys)}
    for key, part in b.groupby(keys):
        other = grouped_g.get(key)
        if other is None:
            continue
        gd = [pd.Timestamp(value) for value in other['_date']]
        gi = other.index.tolist()
        local_links = []
        limit_hit = False
        for bi, row in part.iterrows():
            left = bisect_left(gd, pd.Timestamp(row['_date']) - pd.Timedelta(days=date_tolerance_days))
            right = bisect_right(gd, pd.Timestamp(row['_date']) + pd.Timedelta(days=date_tolerance_days))
            if len(links) + len(local_links) + right - left > max_candidate_links:
                limit_hit = True
                break
            for pos in range(left, right):
                gj = gi[pos]
                local_links.append((bi, gj, int((g.loc[gj, '_date'] - row['_date']).days)))
        if limit_hit:
            limited.append(key)
            continue
        links.extend(local_links)
    for bi, gj, days in links:
        bank_counts[bi] = bank_counts.get(bi, 0) + 1
        gl_counts[gj] = gl_counts.get(gj, 0) + 1
    return links, bank_counts, gl_counts, limited


def _build_matches(b, g, links, bank_counts, gl_counts):
    matches = []
    candidates = []
    matched_b = set()
    matched_g = set()
    for bi, gj, days in links:
        unique = bank_counts[bi] == 1 and gl_counts[gj] == 1
        row = {'Row_ID_Bank': b.loc[bi, 'Row_ID'], 'Row_ID_GL': g.loc[gj, 'Row_ID'], 'Bank_Account': b.loc[bi, 'Bank_Account'], 'Currency': b.loc[bi, 'Currency'], 'Date_Bank': b.loc[bi, 'Date'], 'Date_GL': g.loc[gj, 'Date'], 'Amount': int(b.loc[bi, '_amount_cents']) / 100, 'Date_Difference_Days': days, 'Match_Basis': '동일일자 유일 후보' if days == 0 else '설정 시차 이내 상호 유일 후보', 'Candidate_Status': 'unique' if unique else 'ambiguous'}
        candidates.append(row)
        if unique:
            matches.append(row)
            matched_b.add(bi)
            matched_g.add(gj)
    header = ['Row_ID_Bank', 'Row_ID_GL', 'Bank_Account', 'Currency', 'Date_Bank', 'Date_GL', 'Amount', 'Date_Difference_Days', 'Match_Basis', 'Candidate_Status']
    matched = pd.DataFrame(matches, columns=header)
    candidate_frame = pd.DataFrame(candidates, columns=header)
    return matched, candidate_frame, matched_b, matched_g


def _review_unmatched(b, g, matched_b, matched_g, bank_counts, gl_counts, limited, as_of, aging_days):
    keys = ['Bank_Account', 'Currency', '_amount_cents']
    unmatched_b = b.loc[~b.index.isin(matched_b)].copy()
    unmatched_g = g.loc[~g.index.isin(matched_g)].copy()
    review = []
    for side, frame, counts in [('Bank', unmatched_b, bank_counts), ('GL', unmatched_g, gl_counts)]:
        frame['Candidate_Count'] = [counts.get(i, 0) for i in frame.index]
        frame['Review_Reason'] = '설정 조건에 맞는 상대 거래 없음: 시차·수수료·누락·분할 여부 확인'
        frame.loc[frame['Candidate_Count'].gt(0), 'Review_Reason'] = '중복 후보가 있어 자동으로 연결하지 않음'
        for i, row in frame.iterrows():
            if tuple((row[k] for k in keys)) in limited:
                frame.loc[i, 'Review_Reason'] = '후보 연결 한도 초과로 이 금액 그룹은 자동 대사하지 않음'
        frame['Days_Unmatched'] = None
        if as_of is not None:
            frame['Days_Unmatched'] = (pd.to_datetime(as_of, format='%Y%m%d') - frame['_date']).dt.days
        frame['Aged_Unmatched'] = frame['Days_Unmatched'].ge(aging_days) if as_of is not None else False
        for _, row in frame.iterrows():
            review.append({'Side': side, 'Row_ID': row['Row_ID'], 'Source_Row': row['Source_Row'], 'Bank_Account': row['Bank_Account'], 'Currency': row['Currency'], 'Date': row['Date'], 'Amount': int(row['_amount_cents']) / 100, 'Candidate_Count': row['Candidate_Count'], 'Days_Unmatched': row['Days_Unmatched'], 'Aged_Unmatched': row['Aged_Unmatched'], 'Review_Reason': row['Review_Reason'], 'Suggested_Review': '은행명세·전표·입출금 시점과 증빙을 확인하고 연결 여부 기록'})
    review_frame = pd.DataFrame(review, columns=['Side', 'Row_ID', 'Source_Row', 'Bank_Account', 'Currency', 'Date', 'Amount', 'Candidate_Count', 'Days_Unmatched', 'Aged_Unmatched', 'Review_Reason', 'Suggested_Review'])
    return unmatched_b, unmatched_g, review_frame
