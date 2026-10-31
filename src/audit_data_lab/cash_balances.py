"""제출 잔액과 조정액의 산술 대사."""
import pandas as pd
from .common import columns, fail, money, text
from .validation import DataValidationError


def review_balances(balances, as_of):
    issues = []
    balance_result = pd.DataFrame()
    balance_status = 'not_provided'
    if balances is not None:
        try:
            columns(balances, ['Bank_Account', 'Currency', 'As_Of_Date', 'Bank_Balance', 'GL_Balance', 'Bank_Adjustment', 'Adjustment_Reference'], 'Balances')
            s = balances.copy().reset_index(drop=True)
            if as_of is None:
                fail('AS_OF_REQUIRED', 'As_Of', '잔액 대사에는 기준일이 필요합니다.', table='Balances')
            for c in ['Bank_Account', 'Currency', 'As_Of_Date']:
                s[c] = text(s, c, 'Balances')
            if not s['As_Of_Date'].eq(as_of).all():
                fail('BALANCE_DATE_MISMATCH', 'As_Of_Date', '잔액 기준일이 일치하지 않습니다.', table='Balances')
            if not s['Currency'].str.fullmatch('[A-Z]{3}').all():
                fail('INVALID_CURRENCY', 'Currency', '잔액 통화 형식을 확인하세요.', table='Balances')
            if s.duplicated(['Bank_Account', 'Currency']).any():
                fail('DUPLICATE_BALANCE', 'Bank_Account', '동일 계좌·통화의 잔액이 중복됩니다.', table='Balances')
            for c in ['Bank_Balance', 'GL_Balance', 'Bank_Adjustment']:
                s[c + '_Cents'] = money(s[c], c, 'Balances')
            s['Adjusted_Bank_Balance'] = (s['Bank_Balance_Cents'] + s['Bank_Adjustment_Cents']) / 100
            s['Difference_Cents'] = s['Bank_Balance_Cents'] + s['Bank_Adjustment_Cents'] - s['GL_Balance_Cents']
            s['Difference'] = s['Difference_Cents'] / 100
            missing = s['Bank_Adjustment_Cents'].ne(0) & s['Adjustment_Reference'].astype('string').fillna('').str.strip().eq('')
            s['Status'] = 'difference'
            s.loc[s['Difference_Cents'].eq(0), 'Status'] = 'arithmetic_match'
            s.loc[missing, 'Status'] = 'adjustment_evidence_missing'
            balance_result = s
            balance_status = 'review_required' if missing.any() or s['Difference_Cents'].ne(0).any() else 'arithmetic_match'
        except DataValidationError as error:
            balance_status = 'not_executed_input_issue'
            issues.extend(error.to_dict()['errors'])
    return balance_result, balance_status, issues
