"""GL 순변동 비교와 선택적 TB 검토."""
import pandas as pd
from .analysis_notes import ANALYSIS_NOTES
from .common import AnalysisResult, fail, prepare_gl
from .financial_review import review_tb
from .validation import DataValidationError


def analytical_review(gl, *, current_year, prior_year, change_threshold_pct=30,
                      tb=None, account_mapping=None, tb_period=None, tb_sign_basis=None):
    g = prepare_gl(gl)
    _validate_scope(g, current_year, prior_year, change_threshold_pct)
    comparison = _year_comparison(g, current_year, prior_year, change_threshold_pct)
    monthly, monthly_compare = _monthly_comparison(g, current_year, prior_year)
    coverage_status, coverage = _period_coverage(g, current_year, prior_year)
    balances, ratios, components, tb_issues, ratio_status = _optional_tb(
        tb, account_mapping, current_year, prior_year, tb_period, tb_sign_basis,
    )
    issues = []
    if coverage_status != 'observed_periods_equal':
        issues.append({
            'code': 'COMPARISON_PERIOD_COVERAGE_DIFFERS', 'field': 'Period',
            'message': '당기·전기의 관측 기간이 다릅니다. 같은 기간인지 확인하세요.',
            'source_file': 'GL',
            'suggested_review': '추출 조건·기간 완전성을 확인하고 증감 원인을 검토하세요.',
        })
    issues.extend(tb_issues)
    return AnalysisResult('analytical_review',{'comparison_account_count':len(comparison),
        'review_account_count':int(comparison['Review_Required'].sum()),'period_coverage_status':coverage_status,'ratio_status':ratio_status},
        {'year_comparison':comparison,'monthly_movements':monthly,'monthly_comparison':monthly_compare,
         'period_coverage':coverage,'balance_comparison':balances,'financial_ratios':ratios,
         'ratio_components':components,'module_issues':pd.DataFrame(issues)},
        {'current_year':str(current_year),'prior_year':str(prior_year),'change_threshold_pct':change_threshold_pct,
         'tb_period':tb_period,'tb_sign_basis':tb_sign_basis,'ratio_status':ratio_status,
         'ratio_formulas':ANALYSIS_NOTES['analytical_review']['ratio_formulas'].copy(),
         'basis':ANALYSIS_NOTES['analytical_review']['basis']})


def _validate_scope(g, current_year, prior_year, change_threshold_pct):
    if current_year == prior_year or change_threshold_pct < 0:
        raise ValueError('비교 연도와 증감 기준을 확인하세요.')
    available = set(g['Fiscal_Year'])
    if not {str(current_year), str(prior_year)} <= available:
        fail('COMPARISON_PERIOD_MISSING', 'Fiscal_Year', '당기와 전기 GL 데이터가 모두 필요합니다.', table='GL')



def _year_comparison(g, current_year, prior_year, change_threshold_pct):
    keys = ['Business_Unit_Code', 'GL_Account_Number', 'Amount_Currency']
    yearly = []
    for year, name in [(str(current_year), 'Current_Cents'), (str(prior_year), 'Prior_Cents')]:
        yearly.append(g.loc[g['Fiscal_Year'].eq(year)].groupby(keys)['_net_cents'].sum().reset_index(name=name))
    comparison = yearly[0].merge(yearly[1], on=keys, how='outer', indicator=True)
    comparison['Presence'] = comparison.pop('_merge').astype('string')
    comparison[['Current_Cents', 'Prior_Cents']] = comparison[['Current_Cents', 'Prior_Cents']].astype('Int64')
    comparison['Current_Movement'] = comparison['Current_Cents'] / 100
    comparison['Prior_Movement'] = comparison['Prior_Cents'] / 100
    comparison['Change'] = comparison['Current_Movement'] - comparison['Prior_Movement']
    comparison['Change_Pct'] = (comparison['Current_Cents'] - comparison['Prior_Cents']) / comparison['Prior_Cents'].abs().where(comparison['Prior_Cents'].ne(0)) * 100
    comparison['Review_Required'] = comparison['Change_Pct'].abs().ge(change_threshold_pct) | comparison['Prior_Cents'].eq(0) & comparison['Current_Cents'].ne(0) | comparison['Presence'].ne('both')
    comparison['Reason'] = ''
    comparison.loc[comparison['Change_Pct'].abs().ge(change_threshold_pct), 'Reason'] = '설정 증감률 이상'
    comparison.loc[comparison['Prior_Cents'].eq(0) & comparison['Current_Cents'].ne(0), 'Reason'] = '전기 순변동 0: 증감률 계산 불가'
    comparison.loc[comparison['Presence'].ne('both'), 'Reason'] = '한 비교 연도에만 나타난 계정'
    return comparison


def _period_coverage(g, current_year, prior_year):
    current_periods = sorted(set(g.loc[g.Fiscal_Year.eq(str(current_year)), 'Period']))
    prior_periods = sorted(set(g.loc[g.Fiscal_Year.eq(str(prior_year)), 'Period']))
    coverage_status = 'observed_periods_equal' if current_periods == prior_periods else 'observed_periods_differ'
    coverage = pd.DataFrame([{'Fiscal_Year': str(current_year), 'Observed_Periods': ', '.join(current_periods)}, {'Fiscal_Year': str(prior_year), 'Observed_Periods': ', '.join(prior_periods)}])
    return coverage_status, coverage


def _monthly_comparison(g, current_year, prior_year):
    keys = ['Business_Unit_Code', 'GL_Account_Number', 'Amount_Currency']
    monthly = g.groupby(keys + ['Fiscal_Year', 'Period'])['_net_cents'].sum().reset_index(name='Movement_Cents')
    monthly['Movement'] = monthly['Movement_Cents'] / 100
    monthly_compare = monthly.loc[monthly.Fiscal_Year.eq(str(current_year)), keys + ['Period', 'Movement_Cents']].rename(columns={'Movement_Cents': 'Current_Cents'}).merge(monthly.loc[monthly.Fiscal_Year.eq(str(prior_year)), keys + ['Period', 'Movement_Cents']].rename(columns={'Movement_Cents': 'Prior_Cents'}), on=keys + ['Period'], how='outer', indicator=True)
    monthly_compare['Presence'] = monthly_compare.pop('_merge').astype('string')
    monthly_compare['Current_Movement'] = monthly_compare['Current_Cents'] / 100
    monthly_compare['Prior_Movement'] = monthly_compare['Prior_Cents'] / 100
    monthly_compare['Change'] = (monthly_compare['Current_Cents'] - monthly_compare['Prior_Cents']) / 100
    monthly_compare['Change_Pct'] = (monthly_compare['Current_Cents'] - monthly_compare['Prior_Cents']) / monthly_compare['Prior_Cents'].abs().where(monthly_compare['Prior_Cents'].ne(0)) * 100
    return monthly, monthly_compare


def _optional_tb(tb, account_mapping, current_year, prior_year, tb_period, tb_sign_basis):
    balances = pd.DataFrame()
    ratios = pd.DataFrame()
    components = pd.DataFrame()
    issues = []
    ratio_status = 'not_provided'
    if tb is not None:
        try:
            balances, ratios, components, ratio_issues, ratio_status = review_tb(tb, account_mapping, current_year=current_year, prior_year=prior_year, period=tb_period, sign_basis=tb_sign_basis)
            issues.extend(ratio_issues)
        except DataValidationError as error:
            ratio_status = 'not_executed_input_issue'
            issues.extend(error.to_dict()['errors'])
    return balances, ratios, components, issues, ratio_status
