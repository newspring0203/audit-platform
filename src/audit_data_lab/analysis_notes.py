"""조서에 제공하는 분석 설명. 계산 규칙과 분리한다."""

ANALYSIS_NOTES = {'analytical_review': {'ratio_formulas': {'Current_Ratio': '유동자산 / 유동부채',
                                          'Working_Capital': '유동자산 - 유동부채',
                                          'Debt_To_Equity': '(유동부채 + 비유동부채) / 자본'},
                       'basis': 'GL 순변동과 TB 잔액을 구분합니다. 관측 기간 일치는 추출 완전성을 입증하지 않습니다. 지표는 제출한 분류·부호 '
                                '정의에 따른 초안이며 업종 기준 또는 감사 결론을 자동 판단하지 않습니다.'},
 'cash_proofing': {'matching_basis': '동일 계좌·통화·부호 금액과 설정한 일자 차이의 상호 유일 후보만 연결. 중복·후보 한도 초과 그룹은 자동 '
                                     '연결하지 않음.',
                   'sign_convention': '입금/현금 증가 양수, 출금/현금 감소 음수. 입력 전에 통일해야 합니다.',
                   'balance_formula': '조정 후 은행잔액 = Bank_Balance + 사용자가 근거와 함께 제출한 Bank_Adjustment. '
                                      'GL_Balance와 산술 비교.',
                   'limitation': '미연결·장기 미연결은 통제 미비 확정이 아닙니다. 잔액 산술 일치는 조정 근거의 적정성·완전성 검증을 대신하지 '
                                 '않습니다.'}}
