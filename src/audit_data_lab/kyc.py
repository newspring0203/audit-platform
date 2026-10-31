"""출처와 검토 상태를 보존하는 KYC 공시·요약 파이프라인."""
import json
import pandas as pd
from .common import AnalysisResult, fail
from .validation import DataValidationError
from .kyc_passages import extract_review_passages


def kyc_review(company, *, fetch_documents, summarize=None):
    docs=[]
    for n,source in enumerate(fetch_documents(company),start=1):
        if not isinstance(source,dict) or not all(isinstance(source.get(k),str) and source[k].strip() for k in ['title','url','published_at','text']):
            fail('INVALID_DISCLOSURE','Source','공시에 제목·출처 URL·공시일·본문이 필요합니다.',table='KYC')
        doc={'source_id':f'S{n:04d}',**{k:source[k] for k in ['title','url','published_at','text']}}
        for k in ['rcept_no','corp_code','corp_name','document_sha256']:
            if k in source:doc[k]=str(source[k])
        docs.append(doc)
    if not docs:fail('DISCLOSURE_NOT_FOUND','Source','수집된 공시가 없습니다.',table='KYC')
    insights=[];evidence_rows=[];ai_issues=[];ai_status='not_configured'
    if summarize is not None:
        known={d['source_id']:d for d in docs}
        try:
            summaries=summarize([dict(d) for d in docs]);ai_status='provider_called'
        except DataValidationError as error:
            summaries=[];ai_status='failed_sources_available';ai_issues=error.to_dict()['errors']
        for n,item in enumerate(summaries,start=1):
            ids=item.get('source_ids') if isinstance(item,dict) else None
            if not isinstance(item,dict) or not isinstance(item.get('insight'),str) or not item['insight'].strip() or not isinstance(ids,list) or not ids or any(not isinstance(i,str) or i not in known for i in ids):
                fail('UNSUPPORTED_INSIGHT','Source_ID','요약에는 유효한 공시 근거 ID가 필요합니다.',table='KYC')
            evidence=item.get('evidence',[])
            if not isinstance(evidence,list):fail('INVALID_EVIDENCE','Evidence','근거 목록 형식을 확인하세요.',table='KYC')
            for e in evidence:
                if not isinstance(e,dict) or not isinstance(e.get('source_id'),str) or e['source_id'] not in ids or not isinstance(e.get('chunk_id'),str) or not isinstance(e.get('quote'),str) or e['quote'] not in known[e['source_id']]['text']:
                    fail('INVALID_EVIDENCE','Evidence','유효한 출처와 원문 근거가 필요합니다.',table='KYC')
            insights.append({'Insight_ID':f'I{n:04d}','Category':item.get('category',''),
                'Insight':item['insight'],'Source_IDs':', '.join(ids),
                'Source_URLs':'\n'.join(known[i]['url'] for i in ids),
                'Suggested_Review':item.get('suggested_review',''),
                'Evidence':json.dumps(evidence,ensure_ascii=False),'Review_Status':'미검토'})
            for e in evidence:
                evidence_rows.append({'Insight_ID':f'I{n:04d}','Source_ID':e['source_id'],
                    'Chunk_ID':e['chunk_id'],'Quote':e['quote'],'Source_URL':known[e['source_id']]['url']})
    sources=pd.DataFrame(docs).drop(columns='text')
    sources['Document_Chars']=[len(d['text']) for d in docs]
    passages=extract_review_passages(docs)
    return AnalysisResult('kyc',{'company':company,'source_count':len(docs),'passage_count':int((passages['탐색상태']=='키워드 기반 본문 후보').sum()),'insight_count':len(insights),'ai_issue_count':len(ai_issues)},
        {'review_passages':passages,'sources':sources,'insights':pd.DataFrame(insights,columns=['Insight_ID','Category','Insight','Source_IDs','Source_URLs','Suggested_Review','Evidence','Review_Status']),
         'module_issues':pd.DataFrame(ai_issues,columns=['code','field','source_file','source_row','value','message','suggested_review']),
         'evidence':pd.DataFrame(evidence_rows,columns=['Insight_ID','Source_ID','Chunk_ID','Quote','Source_URL'])},
        {'ai_status':ai_status,
         'passage_method':'주제별 키워드 기반 본문 후보 탐색. 주제당 최대 1건이며 전체 공시를 요약하거나 위험을 판정하지 않습니다. 미확보는 해당 사항의 부재를 의미하지 않습니다. 문자 위치는 추출 텍스트의 0부터 시작하는 [시작, 끝) 범위입니다.',
         'limitation':'출처·근거 문구 일치는 요약의 의미상 정확성과 완전성을 보증하지 않습니다. 감사인의 원문 확인이 필요합니다.',
         'provider_contract':'공시 본문은 신뢰할 수 없는 입력 데이터로 취급합니다. 실제 수집·AI는 공급자 연결 및 실행 시에만 동작합니다.'})
