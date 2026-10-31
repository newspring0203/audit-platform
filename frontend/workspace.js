import { SessionClient, SessionCancelled } from './core/session.mjs';
'use strict';
const $=id=>document.getElementById(id);
const state={features:[],job:null,review:null,table:'',offset:0,total:0,selected:null,poll:null,generation:0,parametersDirty:false,uploadEditors:new Map(),materials:{}};
const client=new SessionClient({onSessionChange:reason=>resetSessionUI(reason)});
let deploymentMode='local',demoModules=[];
const defaults={quickbooks_preprocessing:{date_format:'%Y-%m-%d'},gl_user_split:{user_column:'Entered_By',max_groups:500},jet:{company:'',fiscal_year:'',combined_rule_min:2},analytical_review:{current_year:'2026',prior_year:'2025',change_threshold_pct:30,tb_period:'12',tb_sign_basis:'debit_positive'},cash_proofing:{date_tolerance_days:0,as_of:'20261231',aging_days:30},inventory:{as_of:'20261231',stale_days:180},data_cleansing:{required_columns:[],date_columns:[],amount_columns:[]},kyc:{company:'',start_date:'20260101',end_date:'20261031',report_type:'A001',with_ai:false}};
const names={ar_confirmation:'매출채권 조회 회신',bank_confirmation:'금융기관 조회 회신',sap_preprocessing:'SAP 전처리',quickbooks_preprocessing:'QuickBooks 전처리',gl_user_split:'입력 사용자별 GL 분할',jet:'총계정원장 테스트',analytical_review:'분석적 검토',cash_proofing:'자금 대사',inventory:'재고 분석',data_cleansing:'데이터 클렌징',kyc:'KYC 공시'};
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function message(text,error=false){$('message').textContent=text;$('message').className=error?'error':'';}
async function api(path,options={}){const generation=state.generation;const data=await client.request(path,options);if(generation!==state.generation)throw new SessionCancelled();return data;}
const json=(method,body)=>({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
function guarded(fn){return async e=>{if(e?.preventDefault)e.preventDefault();try{await fn(e);}catch(error){if(error instanceof SessionCancelled||error?.name==='AbortError')return;if(error.sessionEpoch!==undefined&&!client.isCurrent(error.sessionEpoch))return;message(error.message,true);}};}
function jobPath(suffix=''){if(!state.job)throw Error('작업을 먼저 선택하세요.');return 'jobs/'+encodeURIComponent(state.job.job_id)+suffix;}
function clearResult(){state.generation++;$('summaryCards').replaceChildren();$('chart').replaceChildren();state.review=null;state.uploadEditors.clear();state.materials={};state.selected=null;state.offset=0;state.table='';state.total=0;$('expiry').textContent='';$('pageInfo').textContent='';$('prev').disabled=true;$('next').disabled=true;$('results').replaceChildren(el('p','분석 완료 후 결과가 표시됩니다.'));$('table').replaceChildren();$('trace').replaceChildren();$('source').replaceChildren();$('noteHistory').replaceChildren();$('references').replaceChildren();$('referenceIds').replaceChildren();renderReferences();$('summary').textContent='';$('noteForm').reset();}
async function connect(){
    const candidate=$('token').value.trim();if(!candidate)throw Error('접근 토큰을 입력하세요. 이미 연결되어 있으면 바로 기능을 사용하세요.');
    const data=await client.connect(candidate);$('token').value='';state.features=data.features;
    await applyFeatures(data);
}
async function applyFeatures(data){
    state.features=data.features;
    $('module').replaceChildren(...state.features.map(f=>{const o=el('option',names[f.module]||f.module);o.value=f.module;return o;}));
    renderParameters();renderFeatureNav();$('module').dispatchEvent(new Event('change'));await refreshJobs();$('token').value='';
    $('connectionStatus').textContent=deploymentMode==='demo'?'방문자 전용 데모 연결됨':'연결됨 · 토큰은 새로고침 시 사라집니다.';message('');
}
function showJob(){const j=state.job;$('jobId').value=j.job_id;$('jobStatus').textContent=`${names[j.module]||j.module} · ${statusLabel(j.status)}`;$('expiry').textContent='만료 '+new Date(j.expires_at*1000).toLocaleString();const required=state.features.find(f=>f.module===j.module)?.required_inputs||[];$('run').disabled=j.status!=='created'||(deploymentMode!=='demo'&&required.some(slot=>!j.uploaded_slots.includes(slot)))||automaticPending(j.job_id)||automaticProblems(j.job_id);$('download').disabled=!j.artifact;$('export').disabled=j.status!=='completed';}
async function refreshMaterials(){const materialJob=state.job?.job_id;const d=await api(jobPath('/materials'));if(state.job?.job_id!==materialJob)return;if(state.job){state.materials=d.datasets;state.job.uploaded_slots=Object.keys(d.datasets);hydrateUploadContexts(d.datasets);showJob();}const box=$('materials');box.replaceChildren();for(const [slot,m] of Object.entries(d.datasets)){const div=el('div',undefined,'material');div.append(el('strong',`${slot} · ${m.display_name||m.context?.label||'사용자 제출 자료'}`),el('p',`${materialAnalysisLabel(slot)}\n자료 메모 기간: ${m.context?.period_start&&m.context?.period_end?m.context.period_start+' ~ '+m.context.period_end:'미입력 (분석 조건과 별도)'} / 자료 요청 참조(PBC): ${m.context?.pbc_reference||'미입력 (선택)'}`,'muted'),el('p',`버전 ${m.version_id||m.sha256}`,'hash'),el('p',`SHA-256 ${m.sha256}`,'hash'));if(m.history?.length||m.previous_versions?.length)div.append(el('p',`보관된 이전 버전 ${(m.previous_versions||m.history).length}개 · 작업 만료 시 삭제`,'muted'));const versions=m.previous_versions||[];if(versions.length){const select=el('select');for(const v of versions){const o=el('option',`${v.display_name||slot} · ${v.version_id||v.sha256}`);o.value=v.version_id||v.sha256;select.append(o);}const keys=el('input');keys.placeholder='비교 유일 키: 예 Row_ID 또는 회사,연도,전표,행';keys.setAttribute('aria-label',slot+' 버전 비교 키');const compare=el('button','이전 버전과 비교','secondary');compare.addEventListener('click',guarded(async()=>{const d=await api(jobPath(`/materials/${encodeURIComponent(slot)}/compare?prior_version=${encodeURIComponent(select.value)}&keys=${encodeURIComponent(keys.value)}`));state.selected=null;$('trace').replaceChildren();$('source').replaceChildren();$('noteHistory').replaceChildren();$('noteForm').reset();$('results').replaceChildren(el('p',JSON.stringify(d.summary)),el('p',d.policy,'muted'),renderGrid(['kind','key','prior_row','current_row','changed_fields','prior','current'],d.changes.map(r=>({values:Object.fromEntries(Object.entries(r).map(([k,v])=>[k,typeof v==='object'?JSON.stringify(v):v]))}))));$('pageInfo').textContent=`변경 ${d.total}개 중 첫 ${d.changes.length}개 표시`;$('prev').disabled=true;$('next').disabled=true;}));div.append(select,keys,compare);}box.append(div);}if(!box.children.length)box.append(el('p','업로드된 자료가 없습니다.','muted'));}
let automaticQueue=Promise.resolve();
const pendingSaves=new Map(),saveProblems=new Map();
function automaticPending(job){return (pendingSaves.get(job)||0)>0;}
function automaticProblems(job){return Array.from(saveProblems.keys()).some(key=>key.startsWith(job+':'));}
function updateReady(job){if(state.job?.job_id===job)showJob();}
function queueSave(job,editor,kind,operation){
    if(!client.isCurrent(editor.sessionEpoch))return Promise.resolve();
    pendingSaves.set(job,(pendingSaves.get(job)||0)+1);updateReady(job);
    const task=automaticQueue.then(async()=>{
        if(!client.isCurrent(editor.sessionEpoch))return;
        try{await operation();if(kind==='file')saveProblems.delete(job+':'+editor.slot+':'+kind);}
        catch(error){if(error instanceof SessionCancelled||!client.isCurrent(editor.sessionEpoch))return;saveProblems.set(job+':'+editor.slot+':'+kind,error.message);editor.status.textContent=error.message+' · 다시 선택하거나 입력을 수정하세요.';editor.status.className='uploadStatus error';if(kind==='file')editor.file.value='';}
        finally{editor.file.disabled=false;}
    }).finally(()=>{if(!client.isCurrent(editor.sessionEpoch))return;const count=(pendingSaves.get(job)||1)-1;if(count)pendingSaves.set(job,count);else pendingSaves.delete(job);updateReady(job);});
    automaticQueue=task.catch(()=>{});return task;
}
function contextValue(editor){return {label:(editor.filename||editor.label||'').slice(0,160),pbc_reference:editor.pbc.value,period_start:editor.start.value,period_end:editor.end.value};}
function validContext(editor){return editor.start.validity.valid&&editor.end.validity.valid&&Boolean(editor.start.value)===Boolean(editor.end.value)&&editor.start.value<=editor.end.value;}
function contextProblem(editor){const key=editor.job+':'+editor.slot+':metadata';if(!validContext(editor)){saveProblems.set(key,'자료 기간의 시작·종료를 함께, 올바른 순서로 입력하세요.');editor.status.textContent='기간의 시작·종료를 함께 입력하세요. 분석 전에 자동 저장됩니다.';editor.status.className='uploadStatus error';updateReady(editor.job);return true;}saveProblems.delete(key);return false;}
async function saveContext(editor){
    if(!client.isCurrent(editor.sessionEpoch))throw new SessionCancelled();
    if(contextProblem(editor))return;
    const revision=editor.revision;await client.request('jobs/'+editor.job+'/materials/'+editor.slot,json('PATCH',contextValue(editor)));
    if(revision===editor.revision){saveProblems.delete(editor.job+':'+editor.slot+':metadata');editor.status.textContent='파일·자료 정보 저장 완료';editor.status.className='uploadStatus saved';}
    if(state.job?.job_id===editor.job)await refreshMaterials();
}
function scheduleContext(editor){
    editor.revision++;client.clearTimer(editor.timer);
    if(contextProblem(editor))return;
    if(!editor.uploaded&&!editor.uploading){editor.status.textContent='파일을 선택하면 자료 정보도 함께 저장됩니다.';editor.status.className='uploadStatus';return;}
    // 디바운스 중에도 분석을 시작하지 못하게 잠근다.
    saveProblems.set(editor.job+':'+editor.slot+':metadata','자료 정보 저장 대기');editor.status.textContent='자료 정보 저장 대기…';editor.status.className='uploadStatus';updateReady(editor.job);
    editor.timer=client.setTimer(()=>{if(!client.isCurrent(editor.sessionEpoch))return;queueSave(editor.job,editor,'metadata',()=>saveContext(editor));},450);
}
function hydrateUploadContexts(datasets){for(const [slot,editor] of state.uploadEditors){const asset=datasets[slot];if(!asset)continue;editor.uploaded=true;if(editor.revision===0){const c=asset.context||{};editor.label=c.label||asset.display_name||'';editor.pbc.value=c.pbc_reference||'';editor.start.value=c.period_start||'';editor.end.value=c.period_end||'';editor.status.textContent='저장된 파일: '+(asset.display_name||slot);editor.status.className='uploadStatus saved';}}}
function uploadForms(){
    if(deploymentMode==='demo'){$('uploads').replaceChildren(el('p','서버의 합성 샘플이 분석 실행 시 자동 준비됩니다. 파일 업로드는 필요하지 않습니다.'));return;}
    const box=$('uploads');box.replaceChildren();state.uploadEditors.clear();const job=state.job;const feature=state.features.find(f=>f.module===job.module);if(!feature)return;
    if(job.status!=='created'){box.append(el('p','분석 시점 자료가 고정되었습니다.','muted'));return;}
    for(const slot of feature.inputs){
        const div=el('details',undefined,'upload');div.open=feature.required_inputs.includes(slot);div.append(el('summary',`${slot} · ${feature.required_inputs.includes(slot)?'필수':'선택'}`));
        const columns=feature.input_columns?.[slot]||[];
        if(columns.length){const hint=el('details');hint.append(el('summary','필요한 컬럼 보기'),el('p',columns.filter(Boolean).join(', '),'muted'));const template=el('button','빈 CSV 서식 받기','secondary');template.type='button';template.addEventListener('click',guarded(()=>saveBlob(`input-templates/${feature.module}/${slot}`,`${slot}_template.csv`)));div.append(hint,template);}
        const file=el('input');file.type='file';file.accept='.csv,.txt,.xlsx';file.setAttribute('aria-label',slot+' 파일');
        const pbc=el('input');pbc.placeholder='예: DEMO-GL-01';pbc.maxLength=100;pbc.setAttribute('aria-label',slot+' PBC 참조');
        const start=el('input');start.type='date';start.setAttribute('aria-label',slot+' 기간 시작');
        const end=el('input');end.type='date';end.setAttribute('aria-label',slot+' 기간 종료');
        const status=el('p','파일 선택 시 자동 업로드됩니다. 기간·PBC는 입력 후 자동 저장됩니다.','uploadStatus');status.setAttribute('role','status');
        const editor={job:job.job_id,slot,sessionEpoch:client.epoch,file,pbc,start,end,status,revision:0,uploaded:job.uploaded_slots.includes(slot),uploading:false,filename:'',timer:null};state.uploadEditors.set(slot,editor);
        file.addEventListener('change',()=>{
            const selected=file.files[0];if(!selected)return;editor.revision++;editor.filename=selected.name;
            if(selected.size>20*1024*1024){saveProblems.set(job.job_id+':'+slot+':file','파일 용량 초과');status.textContent='파일은 20MB 이하로 선택하세요.';status.className='uploadStatus error';file.value='';updateReady(job.job_id);return;}
            editor.uploading=true;file.disabled=true;status.textContent='자동 업로드 대기…';status.className='uploadStatus';
            queueSave(job.job_id,editor,'file',async()=>{
                try{status.textContent='업로드 중…';await client.request('jobs/'+job.job_id+'/inputs/'+slot,{method:'PUT',headers:{'X-Filename':encodeURIComponent(selected.name)},body:selected});editor.uploaded=true;
                    // 파일 저장 성공과 자료 정보 저장 실패는 구분한다.
                    try{await saveContext(editor);}catch(error){if(error instanceof SessionCancelled||!client.isCurrent(editor.sessionEpoch))throw new SessionCancelled();saveProblems.set(job.job_id+':'+slot+':metadata',error.message);status.textContent='파일 저장 완료 · 자료 정보 저장 실패: '+error.message;status.className='uploadStatus error';}
                    if(state.job?.job_id===job.job_id)await refreshMaterials();
                }finally{editor.uploading=false;}
            });
        });
        for(const input of [pbc,start,end]){input.addEventListener('input',()=>scheduleContext(editor));input.addEventListener('change',()=>scheduleContext(editor));}
        const pbcLabel=el('label','자료 요청 번호 / PBC (선택)');pbcLabel.append(pbc);const startLabel=el('label','자료 메모 시작일 (선택)');startLabel.append(start);const endLabel=el('label','자료 메모 종료일 (선택)');endLabel.append(end);div.append(file,pbcLabel,startLabel,endLabel,el('p','메모 기간은 자료 설명용이며 분석 범위를 바꾸지 않습니다.','muted'),status);box.append(div);
    }
    hydrateUploadContexts(state.materials);
}

async function loadJob(){client.clearTimer(state.poll);const generation=++state.generation;const loaded=await api('jobs/'+encodeURIComponent($('jobId').value.trim()));if(generation!==state.generation)return;state.job=loaded;const jobId=loaded.job_id;clearResult();$('module').value=state.job.module;renderParameters();renderFeatureNav();$('pageTitle').textContent=names[state.job.module]||state.job.module;for(const [key,value] of Object.entries(state.job.parameters||{})){const input=$('parameterForm').elements.namedItem(key);if(!input)continue;if(input.type==='checkbox')input.checked=value;else if(input.type==='date')input.value=String(value).replace(/^(\d{4})(\d{2})(\d{2})$/,'$1-$2-$3');else input.value=Array.isArray(value)?value.join(', '):value;}syncParameters();showJob();uploadForms();await refreshMaterials();if(state.job?.job_id!==jobId)return;if(state.job.status==='completed')await loadReview();else if(['running','queued'].includes(state.job.status))schedulePoll();}
function schedulePoll(){const id=state.job.job_id;state.poll=client.setTimer(guarded(async()=>{const j=await api('jobs/'+encodeURIComponent(id));if(state.job?.job_id!==id)return;state.job=j;showJob();if(j.status==='completed'){await refreshJobs();await loadReview();}else if(['running','queued'].includes(j.status))schedulePoll();else message('작업 상태: '+j.status);}),1500);}
async function loadReview(){const jobId=state.job?.job_id,generation=state.generation;const review=await api(jobPath('/review'));if(state.job?.job_id!==jobId||state.generation!==generation)return;state.review=review;$('table').replaceChildren(...Object.entries(state.review.tables).map(([key,value])=>{const o=el('option',`${({confirmation_comparison:'장부·조회 회신 비교',unlinked_replies:'요청에 연결되지 않은 회신',terms_review:'금융기관 조건 검토',review_passages:'주제별 원문 검토자료',sources:'수집 공시·출처',insights:'AI 검토 제안',evidence:'AI 원문 근거'})[key]||key} (${value.row_count})`);o.value=key;return o;}));renderSummary();state.table=$('table').value;state.offset=0;renderReferences();await loadTable();if(state.job?.job_id===jobId&&state.generation===generation)showPanel('results');}
function renderGrid(columns,rows,onSelect){const wrap=el('div',undefined,'tableWrap'),table=el('table'),head=el('thead'),hr=el('tr');if(onSelect)hr.append(el('th','출처 / 검토'));columns.forEach(c=>hr.append(el('th',c)));head.append(hr);const body=el('tbody');for(const row of rows){const tr=el('tr');if(onSelect){const td=el('td'),button=el('button','확인','secondary');button.addEventListener('click',guarded(()=>onSelect(row)));td.append(button);tr.append(td);}columns.forEach(c=>{const value=row.values?.[c],td=el('td');if(c==='원문발췌'&&value){const details=el('details');details.append(el('summary',String(value).slice(0,100)+'…'));const paragraph=el('p',String(value));paragraph.style.whiteSpace='pre-wrap';paragraph.style.minWidth='320px';paragraph.style.maxWidth='560px';details.append(paragraph);td.append(details);}else td.textContent=value===null||value===undefined?'—':String(value);tr.append(td);});body.append(tr);}table.append(head,body);wrap.append(table);return wrap;}
async function loadTable(){if(!state.table)return;const g=state.generation,table=state.table,offset=state.offset;const d=await api(jobPath('/review/tables/'+encodeURIComponent(table)+`?offset=${state.offset}&limit=25`));if(g!==state.generation||table!==state.table||offset!==state.offset)return;state.total=d.row_count;renderChart(d.rows);$('results').replaceChildren(renderGrid(d.columns,d.rows,selectRow));$('pageInfo').textContent=`${d.row_count?state.offset+1:0}–${Math.min(state.offset+25,d.row_count)} / ${d.row_count}`;$('prev').disabled=state.offset===0;$('next').disabled=state.offset+25>=d.row_count;}
async function selectRow(row){showPanel('review');$('tab-review').focus();state.selected=row.review_id;const trace=await api(jobPath('/review/trace/'+row.review_id));if(state.selected!==row.review_id)return;const box=$('trace');box.replaceChildren(el('p','결과 ID '+row.review_id,'hash'),el('p','출처 상태: '+trace.status),el('pre',JSON.stringify({산식:trace.calculation,실행조건:trace.conditions,안내:trace.note},null,2)));$('source').replaceChildren();for(const ref of trace.sources){const d=trace.datasets[ref.slot],b=el('button',`${ref.slot} · ${ref.role} · ${ref.rows.length}행`,'secondary');b.addEventListener('click',guarded(()=>showSource(ref.slot,row.review_id,0)));box.append(el('p',`${d.context?.label||d.display_name||ref.slot} / 버전 ${ref.dataset_version_id}`,'hash'),b);}const events=state.review.review_log.events.filter(e=>e.review_id===row.review_id);const last=events.at(-1);$('noteForm').reset();if(last){$('noteStatus').value=last.status;$('explanation').value=last.explanation;$('evidence').value=last.evidence_reference;$('conclusion').value=last.conclusion;for(const o of $('referenceIds').options)o.selected=last.reference_ids.includes(o.value);}syncReferenceChoices();$('noteHistory').replaceChildren(...events.map(e=>el('p',`${e.at} · ${e.reviewer} · ${e.status} · ${e.conclusion}`,'history')));}
async function showSource(slot,id,offset){const d=await api(jobPath(`/review/sources/${encodeURIComponent(slot)}?review_id=${id}&offset=${offset}&limit=25`));if(state.selected!==id)return;const box=$('source');box.replaceChildren(el('h3',`${slot} · 원본 논리 레코드 (${d.total}행)`),el('p',d.dataset.row_basis,'muted'),renderGrid(['source_row',...d.dataset.columns],d.rows.map(r=>({values:{source_row:r.source_row,...r.values}}))));const prev=el('button','이전 원본','secondary'),next=el('button','다음 원본','secondary');prev.disabled=offset===0;next.disabled=offset+25>=d.total;prev.addEventListener('click',guarded(()=>showSource(slot,id,offset-25)));next.addEventListener('click',guarded(()=>showSource(slot,id,offset+25)));box.append(prev,next);}
function renderReferences(){
    const refs=state.review?.review_log?.references||{};const selected=new Set(Array.from($('referenceIds').selectedOptions,o=>o.value));
    $('references').replaceChildren();$('referenceIds').replaceChildren();$('referenceChoices').replaceChildren();
    $('referenceIds').disabled=!Object.keys(refs).length;
    $('referenceHint').textContent=Object.keys(refs).length?'':'등록된 기준서가 없습니다. 아래에서 기준서를 등록하면 여기에서 선택할 수 있습니다.';
    if(Object.keys(refs).length)$('referenceHint').textContent='직접 입력하는 칸이 아닙니다. 연결할 기준서를 체크한 뒤 검토 기록을 저장하세요.';
    for(const [id,r] of Object.entries(refs)){
        const div=el('div',undefined,'reference');div.append(el('strong',`${r.title} / ${r.paragraph}`),el('p',`${r.issuer} · ${r.edition} · 적용일 ${r.effective_date||'미입력'} · 사용자 등록·미검증`,'muted'),el('p',r.applicability_note));
        if(r.url){const a=el('a','출처 열기');a.href=r.url;a.target='_blank';a.rel='noopener noreferrer';div.append(a);}$('references').append(div);
        const option=el('option',`${r.title} / ${r.paragraph}`);option.value=id;option.selected=selected.has(id);$('referenceIds').append(option);
        const label=el('label',undefined,'referenceChoice');const checkbox=el('input');checkbox.type='checkbox';checkbox.value=id;checkbox.checked=selected.has(id);checkbox.addEventListener('change',()=>{option.selected=checkbox.checked;});
        label.append(checkbox,el('span',`${r.title} / ${r.paragraph} (${r.edition})`));$('referenceChoices').append(label);
    }
}
function syncReferenceChoices(){const selected=new Set(Array.from($('referenceIds').selectedOptions,o=>o.value));for(const input of $('referenceChoices').querySelectorAll('input'))input.checked=selected.has(input.value);}

async function saveBlob(path,name){
    const blob=await client.request(path,{},'blob');const epoch=client.epoch;client.assertCurrent(epoch);
    const url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);
}
$('connect').addEventListener('click',guarded(connect));$('module').addEventListener('change',()=>{renderParameters();renderFeatureNav();$('pageTitle').textContent=names[$('module').value]||'감사 분석 워크스페이스';});
$('create').addEventListener('click',guarded(async()=>{client.clearTimer(state.poll);state.job=await api('jobs',json('POST',{module:$('module').value,parameters:deploymentMode==='demo'?{}:readParameters()}));clearResult();showJob();uploadForms();await refreshMaterials();await refreshJobs();showPanel('setup');message(deploymentMode==='demo'?'합성 샘플로 작업을 만들었습니다. 분석 실행을 누르세요.':'작업을 만들었습니다. 필요한 자료를 업로드하세요.');}));
$('load').addEventListener('click',guarded(loadJob));$('run').addEventListener('click',guarded(async()=>{if(automaticPending(state.job.job_id)||automaticProblems(state.job.job_id))throw Error('파일·자료 정보 저장이 끝난 뒤 분석을 실행하세요.');state.job=await api(jobPath('/run'),{method:'POST'});showJob();uploadForms();await refreshJobs();schedulePoll();message('분석 중입니다. 완료될 때까지 상태를 확인합니다.');}));
$('table').addEventListener('change',guarded(async()=>{state.table=$('table').value;state.offset=0;await loadTable();}));$('prev').addEventListener('click',guarded(async()=>{state.offset=Math.max(0,state.offset-25);await loadTable();}));$('next').addEventListener('click',guarded(async()=>{state.offset+=25;await loadTable();}));
$('noteForm').addEventListener('submit',guarded(async()=>{if(!state.selected)throw Error('검토할 결과 행을 선택하세요.');await api(jobPath('/review/notes/'+state.selected),json('PUT',{revision:state.review.review_log.revision,status:$('noteStatus').value,explanation:$('explanation').value,evidence_reference:$('evidence').value,conclusion:$('conclusion').value,reference_ids:Array.from($('referenceIds').selectedOptions,o=>o.value)}));state.review=await api(jobPath('/review'));const current=state.selected;if(current){const note=state.review.review_log.events.filter(e=>e.review_id===current).at(-1);$('noteHistory').append(el('p',`${note.at} · ${note.reviewer} · ${note.status} · ${note.conclusion}`,'history'));}message('검토 이력을 저장했습니다. 최신 검토 이력을 별도로 내려받을 수 있습니다.');}));
$('referenceForm').addEventListener('submit',guarded(async e=>{if(!state.review)throw Error('분석 완료 후 참조를 등록하세요.');await api(jobPath('/review/references'),json('POST',Object.fromEntries(new FormData(e.target))));state.review=await api(jobPath('/review'));renderReferences();e.target.reset();$('referenceChoices').scrollIntoView({behavior:'smooth',block:'center'});message('기준서를 등록했습니다. 위 체크박스에서 선택한 뒤 검토 기록을 저장하세요.');}));
$('download').addEventListener('click',guarded(()=>saveBlob(jobPath('/downloads/'+state.job.artifact.artifact_id),'audit_review.zip')));$('export').addEventListener('click',guarded(()=>saveBlob(jobPath('/review/export'),'review_history.json')));
$('delete').addEventListener('click',guarded(async()=>{if(!confirm('이 작업의 원본·모든 버전·결과·검토 기록을 삭제할까요?'))return;await api(jobPath(),{method:'DELETE'});client.clearTimer(state.poll);state.job=null;clearResult();$('materials').replaceChildren();$('uploads').replaceChildren();$('jobStatus').textContent='삭제됨';await refreshJobs();message('작업을 삭제했습니다.');}));
$('logout').addEventListener('click',guarded(async()=>{await client.logout();message('로그아웃했습니다.');}));

function statusLabel(status){return ({created:'자료 준비',uploading:'업로드 중',queued:'실행 대기',running:'분석 중',completed:'결과 확인'})[status]||status;}
function renderParameters(){
    state.parametersDirty=false;const feature=state.features.find(f=>f.module===$('module').value);const form=$('parameterForm');form.replaceChildren();$('moduleHelp').textContent=feature?.ui?.description||'';const info={ar_confirmation:'ledger: 거래처별 잔액. requests: 항목별 요청 ID와 조회 대상. replies: 받은 회신 정리표. 상태는 confirmed·disputed·partial·unable이며 미회신은 회신 행을 만들지 않는다. Request_ID별 회신은 1건만 제출한다. 빈 회신도 헤더가 있는 CSV로 제출한다.',bank_confirmation:'ledger·requests·replies 서식으로 입력한다. Item_Type은 deposit·loan 등 자료 간 동일한 코드를 사용한다. 한 금융기관 회신에 여러 항목이 있으면 내부 Request_ID를 항목별로 부여한다. 담보·보증·제한 등의 공란은 없음으로 판단하지 않는다.',sap_preprocessing:'BSEG·GLT0: XLSX 또는 CSV. BKPF: 파이프(|) 구분 TXT 또는 CSV/XLSX. 첫 시트·첫 행 헤더를 읽습니다. 필요한 컬럼은 각 업로드의 서식에서 확인하세요. 결과 ZIP의 gl.csv·tb.csv를 후속 분석에 업로드할 수 있습니다.',quickbooks_preprocessing:'앞 5개 계정 표시 열과 Type·Date·Num·Name·Memo·Split·Amount·Balance의 예제 형식을 지원합니다. 첫 시트만 읽습니다. 통화·전표 키·입력 사용자 등이 확인되지 않아 ADS GL로 자동 변환하지 않습니다.',data_cleansing:'컬럼명 변경과 값의 의미 변환은 다릅니다. 예를 들어 SAP S/H를 ADS D/C로 바꾸거나 통화를 정하는 것은 별도 변환이 필요합니다. 오류가 있는 행은 임의로 삭제하지 않습니다.',jet:'log 입력은 웹 접속 로그가 아니라 GL과 비교할 별도 회계 거래 기록입니다. 금액·통화·추출 범위가 같은지 확인해야 합니다. 현재 웹에서는 근거 승인 기능이 없어 로그 대사를 미실행으로 표시하며 GL 규칙 검사는 수행합니다.'};$('moduleDetails').hidden=!info[$('module').value];$('moduleDetailsText').textContent=info[$('module').value]||'';
    for(const f of feature?.ui?.fields||[]){const label=el('label',f.label);let input;
        if(f.kind==='select'){input=el('select');for(const [value,text] of f.options){const option=el('option',text);option.value=value;input.append(option);}}
        else{input=el('input');input.type=f.kind==='checkbox'?'checkbox':f.kind==='date'?'date':['number','decimal','year'].includes(f.kind)?'number':'text';if(['number','decimal'].includes(f.kind)){input.min=f.min;input.max=f.max;input.step=f.kind==='decimal'?'any':'1';}if(f.kind==='year'){input.min=1000;input.max=9999;input.step=1;}if(f.kind==='list')input.placeholder='예: Date, Amount';}
        input.name=f.key;input.required=Boolean(f.required);if(f.kind==='checkbox')input.checked=Boolean(f.default);else input.value=f.default??'';input.addEventListener('input',()=>{state.parametersDirty=false;syncParameters();});label.append(input);form.append(label);
    }syncParameters();
}
function collectParameters(){const result={};const feature=state.features.find(f=>f.module===$('module').value);for(const f of feature?.ui?.fields||[]){const input=$('parameterForm').elements.namedItem(f.key);if(f.kind==='checkbox'){result[f.key]=input.checked;continue;}const value=input.value.trim();if(value==='')continue;result[f.key]=f.kind==='date'?value.replaceAll('-',''):['number','decimal'].includes(f.kind)?Number(value):f.kind==='list'?value.split(',').map(x=>x.trim()).filter(Boolean):value;}return result;}
function syncParameters(){$('parameters').value=JSON.stringify(collectParameters(),null,2);}
function readParameters(){if(state.parametersDirty){try{return JSON.parse($('parameters').value);}catch{throw Error('고급 조건 JSON 형식을 확인하세요.');}}if(!$('parameterForm').reportValidity())throw Error('필수 분석 조건과 숫자 범위를 확인하세요.');return collectParameters();}
async function refreshJobs(){const d=await api('jobs');$('jobsList').replaceChildren();for(const j of d.jobs){const button=el('button',`${names[j.module]||j.module} · ${statusLabel(j.status)}`,'jobButton secondary');button.title=j.job_id;button.type='button';button.addEventListener('click',guarded(async()=>{$('jobId').value=j.job_id;await loadJob();}));$('jobsList').append(button);}if(!d.jobs.length)$('jobsList').append(el('p','진행 중인 작업이 없습니다.','muted'));}
const summaryNames={ledger_row_count:'장부 항목',request_count:'조회 요청 항목',reply_count:'회신 항목',no_reply_count:'미회신',not_requested_count:'미요청',difference_count:'잔액 차이',orphan_reply_count:'미연결 회신',terms_review_count:'조건 검토 항목',gl_output_rows:'생성 GL 행',tb_output_rows:'생성 TB 행',nonbalancing_journal_count:'차대 불일치 전표',reconciliation_difference_rows:'GL·TB 금액 차이 행',source_count:'수집 공시',passage_count:'주제별 본문 후보',insight_count:'AI 검토 제안',ai_issue_count:'AI 확인 사항',input_row_count:'입력 행',transaction_row_count:'변환 거래 행',review_row_count:'검토 필요 행',output_file_count:'분할 파일',missing_user_row_count:'사용자 누락 행',journal_count:'입력 전표',flagged_journal_count:'검토 후보 전표',complex_condition_journal_count:'복합 조건 전표',comparison_account_count:'비교 계정',review_account_count:'검토 후보 계정',matched_count:'대사 연결',unmatched_bank_count:'은행 미대사',unmatched_gl_count:'GL 미대사',item_count:'품목',negative_stock_count:'기말 음수 재고',negative_movement_event_count:'기간 중 음수 후보',stale_candidate_count:'장기 미출고 후보',issue_count:'확인 필요 사항'};
function renderSummary(){const box=$('summaryCards');box.replaceChildren();for(const [key,value] of Object.entries(state.review.summary)){if(!summaryNames[key]||typeof value!=='number')continue;const card=el('div',undefined,'summaryCard');card.append(el('span',summaryNames[key]),el('strong',value.toLocaleString()));box.append(card);if(box.children.length===6)break;}const status=state.review.metadata.execution_status;const labels={completed:'분석 수행 완료 · 검토 전',completed_with_limitations:'일부 기준 미확보 또는 확인 필요 사항 있음',not_executed_input_issue:'입력 문제로 분석 미실행',not_executed_system_issue:'처리 문제로 분석 미실행'};const isKyc=state.job?.module==='kyc';
const done=['completed','completed_with_limitations'].includes(status);
const hasIssues=['module_issues','validation_issues','log_basis_issues'].some(k=>(state.review.tables[k]?.row_count||0)>0);
$('summary').textContent=(isKyc&&done?'공시 수집·검토자료 추출 완료 · 원문 검토 전':(labels[status]||status))+(hasIssues?' · 확인 필요 사항은 이슈 표에서 확인하세요.':'')+(isKyc&&done?' · 주제별 발췌는 키워드로 찾은 본문 후보입니다. 위험 판단이 아니며, 미확보는 해당 사항이 없다는 뜻이 아닙니다.':'');}
function renderChart(rows){const box=$('chart');box.replaceChildren();const candidates=[['Current_Movement','Prior_Movement','당기','전기'],['Current_Balance','Prior_Balance','당기 잔액','전기 잔액'],['Quantity_In','Quantity_Out','입고','출고']];const pair=candidates.find(p=>rows.some(r=>r.values[p[0]]!==undefined));if(!pair)return;box.append(el('p','현재 페이지 중 최대 8개 항목 · 막대는 각 행 안에서 절댓값 비교이며 부호는 수치를 확인하세요.','muted'));for(const r of rows.slice(0,8)){const v=r.values;const div=el('div',undefined,'chartRow');div.append(el('strong',[v.GL_Account_Number||v.Item_ID,v.Business_Unit_Code,v.Amount_Currency,v.Period].filter(Boolean).join(' · ')));const max=Math.max(...pair.slice(0,2).map(k=>typeof v[k]==='number'?Math.abs(v[k]):0),1);for(let i=0;i<2;i++){const line=el('div',undefined,'chartLine');line.append(el('span',pair[i+2]));const meter=el('meter');meter.min=0;meter.max=max;meter.value=typeof v[pair[i]]==='number'?Math.abs(v[pair[i]]):0;meter.setAttribute('aria-label',pair[i+2]);line.append(meter,el('span',typeof v[pair[i]]==='number'?v[pair[i]].toLocaleString():'미확보'));div.append(line);}box.append(div);}}
function resetSessionUI(reason='disconnected'){
    showPanel('setup');state.job=null;clearResult();state.features=[];
    for(const id of ['materials','uploads','jobsList','module','parameterForm'])$(id).replaceChildren();
    $('jobId').value='';$('jobStatus').textContent='새 작업을 만들어 시작하세요.';$('pageTitle').textContent='감사 분석 워크스페이스';$('moduleHelp').textContent='';$('moduleDetails').hidden=true;
    $('run').disabled=true;$('download').disabled=true;$('export').disabled=true;
    automaticQueue=Promise.resolve();pendingSaves.clear();saveProblems.clear();
    const labels={connected:'연결 확인됨',logout:'로그아웃됨',unauthenticated:'서버에서 인증을 확인하지 못했습니다. 토큰을 확인하고 다시 연결하세요.',disconnected:'연결되지 않았습니다.'};
    $('connectionStatus').textContent=labels[reason]||labels.disconnected;renderFeatureNav();
}
$('parameters').addEventListener('input',()=>{state.parametersDirty=true;});
$('refreshJobs').addEventListener('click',guarded(refreshJobs));

function showPanel(name){for(const button of document.querySelectorAll('[role=tab][data-panel]')){const active=button.dataset.panel===name;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;document.getElementById('panel-'+button.dataset.panel).hidden=!active;}}
function renderFeatureNav(){const nav=$('featureNav');nav.replaceChildren();const groups=[['데이터 준비',['sap_preprocessing','quickbooks_preprocessing','gl_user_split','data_cleansing']],['감사 분석',['ar_confirmation','bank_confirmation','jet','analytical_review','cash_proofing','inventory']],['회사 이해',['kyc']]];const icons={ar_confirmation:'AR',bank_confirmation:'BC',sap_preprocessing:'SAP',quickbooks_preprocessing:'QB',gl_user_split:'↗',data_cleansing:'◇',jet:'JE',analytical_review:'↔',cash_proofing:'₩',inventory:'▦',kyc:'K'};for(const [title,ids] of groups){if(deploymentMode==='demo'&&!ids.some(id=>demoModules.includes(id)))continue;nav.append(el('p',title,'navGroup'));for(const id of ids){if(deploymentMode==='demo'&&!demoModules.includes(id))continue;if(state.features.length&&!state.features.some(f=>f.module===id))continue;const b=el('button',undefined,'featureButton');b.type='button';b.append(el('span',icons[id],'navIcon'),el('span',names[id]));if($('module').value===id)b.setAttribute('aria-current','page');b.addEventListener('click',guarded(async()=>{if(!state.features.length){message(deploymentMode==='demo'?'데모 시작을 먼저 누르세요.':'개발용 연결 설정을 열어 토큰으로 먼저 연결하세요.');if(deploymentMode!=='demo')document.querySelector('.accessPanel').open=true;return;}client.clearTimer(state.poll);state.job=null;clearResult();for(const key of ['materials','uploads'])$(key).replaceChildren();$('jobStatus').textContent='새 작업을 만들어 시작하세요.';$('run').disabled=true;$('download').disabled=true;$('export').disabled=true;$('module').value=id;$('module').dispatchEvent(new Event('change'));showPanel('setup');message('');}));nav.append(b);}}}
for(const button of document.querySelectorAll('[role=tab][data-panel]')){button.addEventListener('click',()=>showPanel(button.dataset.panel));button.addEventListener('keydown',event=>{const tabs=Array.from(document.querySelectorAll('[role=tab][data-panel]'));let index=tabs.indexOf(button);if(event.key==='ArrowRight')index=(index+1)%tabs.length;else if(event.key==='ArrowLeft')index=(index+tabs.length-1)%tabs.length;else if(event.key==='Home')index=0;else if(event.key==='End')index=tabs.length-1;else return;event.preventDefault();showPanel(tabs[index].dataset.panel);tabs[index].focus();});}
renderFeatureNav();

$('addReference').addEventListener('click',()=>{if(!state.review){message('분석을 완료한 작업을 먼저 여세요.',true);return;}$('referenceForm').scrollIntoView({behavior:'smooth',block:'center'});$('referenceForm').elements.namedItem('title').focus({preventScroll:true});});
renderReferences();

function materialAnalysisLabel(slot){const p=state.job?.parameters||{};if(state.job?.module==='analytical_review'){
 if(slot==='gl')return `GL 분석 조건: ${p.current_year||'미지정'}년 ↔ ${p.prior_year||'미지정'}년 · 업로드된 해당 연도 거래 전체`;
 if(slot==='tb')return `TB 분석 조건: ${p.current_year||'미지정'}년·${p.prior_year||'미지정'}년, 각각 ${p.tb_period||'미지정'}기 잔액`;
 if(slot==='account_mapping')return '계정 분류표 · 거래 기간 필터 적용 대상 아님';
}if(p.as_of)return '분석 기준일: '+String(p.as_of).replace(/^(\d{4})(\d{2})(\d{2})$/,'$1-$2-$3');return '자료 메모 기간은 분석 범위와 별도로 관리합니다.';}

async function startDemo(){
    $('demoStart').disabled=true;
    try{
        const data=await client.connectDemo();
        await applyFeatures(data);
        $('module').value='cash_proofing';$('module').dispatchEvent(new Event('change'));
        $('connectionStatus').textContent='방문자 전용 데모 연결됨';
        $('demoStatus').textContent='연결되었습니다. 기능을 선택하고 작업 만들기 → 분석 실행 → 조서 ZIP 순서로 체험하세요.';
        message('자금 대사 샘플이 준비되어 있습니다. 이 조건으로 작업 만들기를 누르세요.');
    }finally{$('demoStart').disabled=false;}
}
$('demoStart').addEventListener('click',guarded(startDemo));
$('demoLogout').addEventListener('click',guarded(async()=>{await client.logout();$('demoStatus').textContent='데모를 종료했습니다. 기존 세션 접근 권한은 폐기되었습니다.';}));
async function initializeDeployment(){
    try{
        const response=await fetch('/deployment-info',{cache:'no-store'});
        if(!response.ok)throw Error('서비스 설정을 확인하지 못했습니다.');
        const info=await response.json();deploymentMode=info.mode;demoModules=info.demo_modules||[];renderFeatureNav();Object.assign(defaults,info.demo_parameters||{});
        document.querySelector('.pill').textContent=(deploymentMode==='demo'?'PUBLIC DEMO':'LOCAL / PRIVATE')+' · 검토 지원';
        $('demoPanel').hidden=deploymentMode!=='demo';
        document.querySelector('.accessPanel').hidden=deploymentMode==='demo';
        if(deploymentMode==='demo'){
            document.querySelector('.uploadCard h2').textContent='합성 샘플';document.querySelector('.uploadCard > .muted').textContent='서버가 기능별 합성 자료를 준비합니다. 작업을 만든 뒤 분석 실행을 누르세요.';
            $('parameterForm').hidden=true;$('parameters').closest('details').hidden=true;
            $('create').textContent='합성 샘플로 작업 만들기';
        }
    }catch(error){message(error.message,true);}
}
initializeDeployment();
