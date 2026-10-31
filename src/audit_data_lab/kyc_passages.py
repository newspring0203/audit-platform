"""키워드 기반 원문 탐색. 위험 판단이나 요약을 생성하지 않는다."""
import re
import pandas as pd

TOPICS = [
    ('사업 내용', ('사업의 내용', '주요 제품', '주요제품', '사업부문'), '주요 제품·사업부문과 매출 구조는 무엇인가?', '분석적 검토'),
    ('매출·매출채권', ('매출채권', '수익인식', '수익 인식', '고객과의 계약'), '매출 인식 기준과 채권 회수·손상 관련 설명을 확인하세요.', '분석적 검토 / 총계정원장 테스트'),
    ('재고', ('재고자산', '재고 자산', '재고평가'), '재고 구성과 평가·평가손실 관련 설명을 확인하세요.', '재고 분석'),
    ('자금·차입', ('현금및현금성자산', '현금 및 현금성', '차입금', '유동성위험', '유동성 위험'), '현금·차입 구조와 유동성 관련 설명을 확인하세요.', '자금 대사 / 분석적 검토'),
    ('우발부채·약정', ('우발부채', '우발 부채', '소송', '약정사항', '약정 사항'), '소송·보증·약정의 내용과 공시 범위를 원문에서 확인하세요.', '원문·증빙 추가 검토'),
    ('특수관계자', ('특수관계자', '특수 관계자'), '관계자 범위와 거래·잔액 및 거래조건을 확인하세요.', '총계정원장 테스트 / 원문 추가 검토'),
]
COLUMNS=['Source_ID','주제','탐색상태','섹션명','일치키워드','원문발췌','시작문자','끝문자','확인할질문','연결기능','원문링크','검토상태']


def extract_review_passages(docs):
    rows=[]
    for doc in docs:
        text=doc['text']
        lines=[(m.start(),m.end(),m.group()) for m in re.finditer(r'[^\n]+',text)]
        # 목차처럼 짧은 제목이 연속된 구간보다 실제 본문·표가 이어지는 위치를 우선한다.
        headings=[]
        for start,end,line in lines:
            if len(line)<=90 and len(re.findall(r'[가-힣A-Za-z]',line))>=3 and (re.match(r'^(?:[IVXⅠⅡⅢⅣⅤ]+[.． ]|\d+[.．)](?!\d)|[가-힣][.．)])',line) or any(k in line for k in ('사업의 내용','재무제표 주석','연결재무제표 주석'))):
                headings.append((start,line))
        for topic,keywords,question,feature in TOPICS:
            candidates=[]
            for start,end,line in lines:
                hits=[k for k in keywords if k in line]
                if not hits:continue
                following=text[start:min(len(text),start+1000)]
                substantive=[s for s in following.splitlines() if len(s)>=65]
                if not substantive:continue
                # 같은 제목만 나열한 목차 및 표지만으로는 본문을 찾았다고 표시하지 않는다.
                score=min(len(line),500)+sum(min(len(s),150) for s in substantive[:4])
                if any(pos==start for pos,label in headings):score+=1000
                candidates.append((score,start,hits))
            base={'Source_ID':doc['source_id'],'주제':topic,'확인할질문':question,'연결기능':feature,'원문링크':doc['url'],'검토상태':'미검토'}
            if not candidates:
                rows.append({**base,'탐색상태':'본문 후보 미확보 · 원문 확인 필요','섹션명':'','일치키워드':'','원문발췌':'키워드 기반 탐색으로 본문을 확보하지 못했습니다. 해당 사항이 없다는 뜻은 아닙니다.','시작문자':None,'끝문자':None})
                continue
            _,anchor,hits=max(candidates,key=lambda item:(item[0],-item[1]))
            previous=[(pos,label) for pos,label in headings if pos<=anchor]
            section=previous[-1][1] if previous else '섹션 미식별 · 키워드 주변 본문'
            start=max(0,text.rfind('\n',0,max(0,anchor-180))+1)
            end=min(len(text),anchor+1000)
            rows.append({**base,'탐색상태':'키워드 기반 본문 후보','섹션명':section,'일치키워드':', '.join(hits),'원문발췌':text[start:end],'시작문자':start,'끝문자':end})
    return pd.DataFrame(rows,columns=COLUMNS)
