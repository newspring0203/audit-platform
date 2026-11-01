# 입력 사용자별 GL 분할

웹에서 **입력 사용자별 GL 분할**을 선택하고 gl 슬롯에 전처리 GL CSV를 올립니다. 기본 조건은 `{ "user_column": "Entered_By", "max_groups": 500 }`입니다. 실행 후 분석 시점 ZIP의 `review/analysis/`에 사용자별 `user_0001.csv` 등과 `group_index.csv`가 포함됩니다. `group_index.csv`가 사용자와 파일의 대응표입니다.

`unassigned_user.csv`는 사용자 누락 행이 있을 때만 생성합니다. 해당 행을 별도 그룹과 오류·후속 확인 목록에 보존합니다. 분할 행 전체 합계가 입력 행 수와 일치하도록 유지합니다. 원본 값·사용자 문자열·그룹 내 행 순서는 보존합니다. 파일명은 user_0001 같은 그룹 ID를 사용합니다.

각 파일에 Split_Source_Row를 추가하고 웹에서는 결과 ID를 원본 GL 행과 연결합니다. 행 번호는 헤더 1행을 기준으로 한 논리 레코드 번호입니다. CSV 출력에는 기존 수식 방지 정책을 적용하며 CSV는 Excel의 자동 숫자 변환을 강제 제어하지 못하므로 사용자·계정 코드는 텍스트로 가져오세요.

이 기능은 **사용자별 GL 행 분할**입니다. 한 전표의 행에 여러 입력 사용자가 있으면 전표가 파일들로 나뉩니다. 전표 차대변 검사는 전체 전표 범위에서 수행합니다. 원본 행 선택·복사로 그룹을 구성합니다.

학습 예제: notebooks/split_gl_by_user.ipynb. 실제 파일을 지정하기 전에는 입력 경로 안내와 함께 멈추도록 했으며 분석할 원본 경로를 직접 지정합니다.

Python 사용:

```python
from audit_data_lab import split_gl_by_user
result = split_gl_by_user(gl)
result.tables['group_index']
result.save(new_output_directory)
```

웹 업로드·다운로드·자동 삭제·사용자 격리는 기존 작업 정책을 그대로 따릅니다. 노트북의 outputs 저장은 로컬 학습용이며 웹의 자동 삭제 대상과 다릅니다.

## 데이터베이스·감사 해석

`group_index.Group_ID → row_membership.Group_ID`는 1:N 관계이고 `Source_Row` 및 사용자 표의 `Split_Source_Row`로 원본을 추적합니다. 관리표와 원장은 Group_ID·원본 행으로 연결합니다. 여러 입력 파일을 합칠 때는 파일/버전 식별자를 함께 사용합니다.

이 함수는 원본 값과 그룹 내 순서를 보존하는 선택·복사 작업입니다. 원본·출력 버전 비교로 금액·사업단위 보존을 점검합니다. [구현](../src/audit_data_lab/gl_split.py)
