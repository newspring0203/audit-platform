# SAP–ADS 전처리 테스트

프로젝트의 pandas·openpyxl·IPython 설치 환경에서 실행합니다.

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

작은 가상 데이터의 정답 잔액, 오류 입력 거절, 차대변 불균형과 GL–TB 차이 보고, 실제 SAP 예제의 전체 변환을 확인합니다. 노트북의 실제 코드 셀을 실행해 분석 결과를 검증합니다. 모든 테스트 결과 파일은 임시 폴더에 생성되며 기존 CSV 및 SAP 원본을 보존합니다.

통화는 영문 대문자 3자리 형식을 검사하고 특별기간은 달력연도 기준으로 검증합니다.
