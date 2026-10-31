"""작업 조건을 검증하고 해당 분석 함수를 호출한다."""
from pathlib import Path
from audit_data_lab import (
    JetConfig, adapt_legacy_log, run_jet, analytical_review,
    cash_proofing, inventory_analysis, cleanse_data,
    split_gl_by_user, reshape_quickbooks_report, convert_sap_data, ar_confirmation_review, bank_confirmation_review,
)
from audit_data_lab.common import fail


class AnalysisContext:
    def __init__(self, spec, inputs):
        self.spec = spec
        self.inputs = inputs
        self.parameters = spec["parameters"]
        self.module = spec["module"]

    def required(self, name):
        value = self.parameters.get(name)
        if value is None or value == "":
            fail("PARAMETER_REQUIRED", name, "필요한 분석 조건이 없습니다.", table=self.module)
        return value

    def number(self, name, default, minimum=0, maximum=1_000_000_000, *, integer=False):
        value = self.parameters.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum:
            fail("INVALID_PARAMETER", name, "분석 조건의 숫자 범위를 확인하세요.", table=self.module)
        if integer and int(value) != value:
            fail("INVALID_PARAMETER", name, "정수 조건을 입력하세요.", table=self.module)
        return int(value) if integer else value


def sap(context):
    return convert_sap_data(context.inputs.read('bseg'),context.inputs.read('bkpf'),context.inputs.read('glt0'),company=str(context.required('company')),year=str(context.required('fiscal_year')),ledger=str(context.parameters.get('ledger','0')),record_type=str(context.parameters.get('record_type','0')),version=str(context.parameters.get('version','1')))


def quickbooks(context):
    return reshape_quickbooks_report(
        context.inputs.read("quickbooks", raw_report=True),
        date_format=context.parameters.get("date_format", "%Y-%m-%d"),
    )


def gl_split(context):
    return split_gl_by_user(
        context.inputs.read("gl"),
        user_column=context.parameters.get("user_column", "Entered_By"),
        max_groups=context.number("max_groups", 500, 1, 2000, integer=True),
    )


def jet(context):
    gl = context.inputs.read("gl")
    log = context.inputs.read("log")
    indicator = "Amount_Credit_Debit_Indicator"
    if indicator in log and log[indicator].dropna().isin(["S", "H"]).all():
        log = adapt_legacy_log(
            log, company=str(context.required("company")),
            fiscal_year=str(context.required("fiscal_year")),
        )
    config = JetConfig(
        combined_rule_min=context.number("combined_rule_min", 2, 2, 100, integer=True),
        round_unit=context.number("round_unit", 1000, 1, integer=True),
        rare_user_max=context.number("rare_user_max", 10, integer=True),
        rare_account_max=context.number("rare_account_max", 3, integer=True),
    )
    # 대사 근거를 웹 요청만으로 승인하지 않는다.
    return run_jet(gl, log, config, log_basis=None)


def analytical(context):
    return analytical_review(
        context.inputs.read("gl"),
        current_year=str(context.required("current_year")),
        prior_year=str(context.required("prior_year")),
        change_threshold_pct=context.number("change_threshold_pct", 30),
        tb=context.inputs.optional("tb"),
        account_mapping=context.inputs.optional("account_mapping"),
        tb_period=context.parameters.get("tb_period"),
        tb_sign_basis=context.parameters.get("tb_sign_basis"),
    )


def cash(context):
    return cash_proofing(
        context.inputs.read("bank"), context.inputs.read("cash_gl"),
        date_tolerance_days=context.number("date_tolerance_days", 0, 0, 365, integer=True),
        as_of=context.parameters.get("as_of"),
        aging_days=context.number("aging_days", 30, 0, 3650, integer=True),
        balances=context.inputs.optional("balances"),
    )


def inventory(context):
    return inventory_analysis(
        context.inputs.read("movements"), context.inputs.read("opening"),
        as_of=str(context.required("as_of")),
        stale_days=context.number("stale_days", 180, integer=True),
        lot_snapshot=context.inputs.optional("lot_snapshot"),
    )


def cleansing(context):
    columns = {key: context.parameters.get(key, []) for key in
               ["required_columns", "date_columns", "amount_columns"]}
    return cleanse_data(
        context.inputs.read("data"), mapping=context.inputs.optional("mapping"), **columns,
    )


def kyc(context):
    if context.parameters.get("with_ai") and not context.spec.get("allow_ai"):
        fail("AI_DISABLED", "with_ai", "서버에서 AI 호출이 비활성화되어 있습니다.", table="KYC")
    from audit_data_lab.kyc_live import run_live_kyc
    return run_live_kyc(
        str(context.required("company")),
        start_date=str(context.required("start_date")),
        end_date=str(context.required("end_date")),
        max_reports=context.number("max_reports", 1, 1, 5, integer=True),
        with_ai=bool(context.parameters.get("with_ai", False)),
        archive_dir=Path(context.spec["directory"]) / "public_sources",
        report_type=context.parameters.get("report_type", "A001"),
    )


def confirmation(context):
    function=ar_confirmation_review if context.module=='ar_confirmation' else bank_confirmation_review
    return function(context.inputs.read('ledger'),context.inputs.read('requests'),context.inputs.read('replies'),as_of=str(context.required('as_of')),amount_tolerance=context.number('amount_tolerance',0))


HANDLERS = {
    'ar_confirmation': confirmation,
    'bank_confirmation': confirmation,
    "sap_preprocessing": sap,
    "quickbooks_preprocessing": quickbooks,
    "gl_user_split": gl_split,
    "jet": jet,
    "analytical_review": analytical,
    "cash_proofing": cash,
    "inventory": inventory,
    "data_cleansing": cleansing,
    "kyc": kyc,
}


def run_analysis(context):
    handler = HANDLERS.get(context.module)
    if handler is None:
        fail("UNKNOWN_MODULE", "Module", "지원하지 않는 기능입니다.", table=context.module)
    return handler(context)
