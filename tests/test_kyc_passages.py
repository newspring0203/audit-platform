"""원문 후보 탐색의 범위·누락 안내·근거 위치를 검증한다."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from audit_data_lab.kyc import kyc_review

class PassageTests(unittest.TestCase):
    def run_doc(self,text):
        return kyc_review('회사',fetch_documents=lambda _: [{'title':'사업보고서','url':'https://dart.fss.or.kr/','published_at':'20260301','text':text}])

    def test_cover_and_contents_are_not_used_as_inventory_evidence(self):
        text='사업보고서 표지\n목차\n1. 재고자산\n2. 특수관계자\n'+'표지 정보\n'*200+'3. 재고자산\n'+('당사는 재고자산을 원가와 순실현가능가치 중 낮은 금액으로 평가하며 평가손실과 재고의 구성 및 변동을 주석으로 공시하고 있습니다. '*8)
        result=self.run_doc(text)
        rows=result.tables['review_passages']
        row=rows[rows['주제']=='재고'].iloc[0]
        self.assertIn('평가손실',row['원문발췌'])
        self.assertEqual(text[int(row['시작문자']):int(row['끝문자'])],row['원문발췌'])
        self.assertNotIn('Excerpt',result.tables['sources'].columns)
        self.assertEqual(result.summary['insight_count'],0)

    def test_missing_topic_is_not_claimed_absent(self):
        result=self.run_doc('사업보고서 표지만 있는 문서')
        rows=result.tables['review_passages']
        self.assertEqual(len(rows),6)
        self.assertEqual(result.summary['passage_count'],0)
        self.assertTrue(rows['탐색상태'].str.contains('미확보').all())
        self.assertTrue(rows['원문발췌'].str.contains('없다는 뜻은 아닙니다').all())

    def test_decimal_is_not_a_section_heading(self):
        text='3. 재고자산\n66.7\n'+('재고자산 평가와 관련한 회계정책 및 평가손실의 변동 원인을 확인하기 위한 설명을 포함하며 원문을 추가로 검토해야 합니다. '*8)
        row=self.run_doc(text).tables['review_passages'].query("주제 == '재고'").iloc[0]
        self.assertEqual(row['섹션명'],'3. 재고자산')
