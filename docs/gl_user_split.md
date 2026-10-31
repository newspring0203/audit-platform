# 입력 사용자별 GL 분할

웹에서 **입력 사용자별 GL 분할**을 선택하고 gl 슬롯에 전처리 GL CSV를 올립니다. 기본 조건은 `{ "user_column": "Entered_By", "max_groups": 500 }`입니다. 실행 후 분석 시점 ZIP의 `review/analysis/`에 사용자별 `user_0001.csv` 등과 `group_index.csv`가 포함됩니다. `group_index.csv`가 사용자와 파일의 대응표입니다.

`unassigned_user.csv`는 사용자 누락 행이 있을 때만 생성합니다. 해당 행을 삭제하지 않고 오류·후속 확인 목록에도 남깁니다. 분할 행 전체 합계가 입력 행 수와 일치하도록 유지합니다. 원본 값·사용자 문자열·그룹 내 행 순서는 보존합니다. 사용자명으로 파일 경로를 만들지 않습니다.

각 파일에 Split_Source_Row를 추가하고 웹에서는 결과 ID를 원본 GL 행과 연결합니다. 행 번호는 헤더 1행을 기준으로 한 논리 레코드 번호입니다. CSV 출력에는 기존 수식 방지 정책을 적용하며 CSV는 Excel의 자동 숫자 변환을 강제 제어하지 못하므로 사용자·계정 코드는 텍스트로 가져오세요.

이 기능은 **사용자별 GL 행 분할**입니다. 한 전표의 행에 여러 입력 사용자가 있으면 전표가 파일들로 나뉩니다. 사용자 파일 하나만으로 전표 차대변 균형을 검사하지 마세요. 회사·기간·통화를 추가 집계하거나 금액을 재계산하지 않습니다.

학습 예제: notebooks/split_gl_by_user.ipynb. 실제 파일을 지정하기 전에는 입력 경로 안내와 함께 멈추도록 했으며 임의로 고객 자료를 선택하지 않습니다. 기존 Split Dataframe with Groupby.ipynb는 변경하지 않았습니다.

Python 사용:

```python
from audit_data_lab import split_gl_by_user
result = split_gl_by_user(gl)
result.tables['group_index']
result.save(new_output_directory)
```

웹 업로드·다운로드·자동 삭제·사용자 격리는 기존 작업 정책을 그대로 따릅니다. 노트북의 outputs 저장은 로컬 학습용이며 웹의 자동 삭제 대상과 다릅니다.
