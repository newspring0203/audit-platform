import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const [inputFile, outputFile] = process.argv.slice(2);
const p=JSON.parse(await fs.readFile(inputFile,'utf8'));
const wb=Workbook.create();
const summary=wb.worksheets.add('검토요약');
const issues=wb.worksheets.add('확인필요사항');
const detail=wb.worksheets.add('검토대상');
const conditions=wb.worksheets.add('입력및조건');
const sheets=[summary,issues,detail,conditions];
const dark='#22364B',amber='#FFF1CB',ink='#22364B';
const literal=v=>typeof v==='string'&&v.startsWith('=')?"'"+v:v;
function base(sheet,title,description,lastCol='L',lastRow=30){
  sheet.showGridLines=false;
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.font={name:'Arial',size:11,color:ink};
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.verticalAlignment='center';
  sheet.getRange('A2').values=[[title]];sheet.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:ink};
  sheet.getRange(`A2:${lastCol}2`).format.rowHeight=30;
  sheet.getRange('A3').values=[[description]];
  sheet.getRange(`A3:${lastCol}3`).format.rowHeight=28;
}
function table(sheet,headers,records,tableName,widths){
  const n=records.length;
  const data=[headers,...records].map(row=>row.map(literal));
  sheet.getRangeByIndexes(4,0,data.length,headers.length).values=data;
  const range=sheet.getRangeByIndexes(4,0,data.length,headers.length);
  range.format.font={name:'Arial',size:11,color:ink};range.format.verticalAlignment='center';
  range.format.rowHeight=24;
  const head=sheet.getRangeByIndexes(4,0,1,headers.length);
  head.format={fill:dark,font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:42,wrapText:true};
  if(n){
    const tab=sheet.tables.add(range,true,tableName);tab.showFilterButton=true;
    sheet.freezePanes.freezeRows(5);
  }
  headers.forEach((h,i)=>{sheet.getRangeByIndexes(4,i,n+1,1).format.columnWidth=widths[i]??22;});
  return n;
}
const primary=p.tables['검토대상'];
const labels={Review_ID:'검토 식별자',Journal_ID:'전표번호',Journal_ID_Line_Number:'상세행',Source_Row:'원본 행',
 GL_Account_Number:'계정번호',Amount:'금액',Amount_Currency:'통화',Effective_Date:'전기일',Entered_Date:'입력일',
 Rule_ID:'검사 코드',Selection_Reason:'선정 이유',Suggested_Review:'후속 검토'};
const head=primary.columns.map(c=>labels[c]??c);
const rows=primary.records.map(record=>primary.columns.map(c=>{
 const value=record[c];
 if((c==='Effective_Date'||c==='Entered_Date')&&typeof value==='string'&&/^\d{8}$/.test(value))
   return new Date(`${value.slice(0,4)}-${value.slice(4,6)}-${value.slice(6,8)}T00:00:00Z`);
 return value;
}));
base(detail,'검토대상','동일 전표가 여러 검사에 나타날 수 있습니다. 검토 의견은 각 행에 입력하세요.','Q',Math.max(20,rows.length+5));
const widths=primary.columns.map(c=>({Review_ID:48,Journal_ID:32,Journal_ID_Line_Number:10,Source_Row:10,
 GL_Account_Number:14,Amount:18,Amount_Currency:10,Effective_Date:15,Entered_Date:15,Rule_ID:28,
 Selection_Reason:56,Suggested_Review:54,'검토 상태':16,'검토 의견':48,'근거':36,'검토자':20,'검토일':16}[c]??24));
table(detail,head,rows,'ReviewTargets',widths);
if(rows.length){
 primary.columns.forEach((c,i)=>{
  const r=detail.getRangeByIndexes(5,i,rows.length,1);
  if(c==='Amount')r.setNumberFormat('#,##0.00;[Red](#,##0.00);0.00');
  if(['Effective_Date','Entered_Date','검토일'].includes(c))r.setNumberFormat('yyyy-mm-dd');
  if(['Selection_Reason','Suggested_Review'].includes(c)){r.format.wrapText=true;r.format.rowHeight=58;}
  if(['검토 상태','검토 의견','근거','검토자','검토일'].includes(c))r.format.fill=amber;
  if(c==='검토 상태')r.dataValidation={rule:{type:'list',values:['미검토','검토중','추가자료요청','검토완료']}};
 });
}else detail.getRange('A7').values=[['검토대상 없음 또는 해당 계산 미실행. 검토요약의 상태를 확인하세요.']];
const issueHeaders=['오류 코드','필드','원본 파일','원본 행','입력값','원인','후속 검토','검토 상태','검토 의견','근거','검토자','검토일'];
const issueRows=p.issues.map(r=>issueHeaders.map(h=>r[h]??null));
base(issues,'확인필요사항','계산 미실행 사유와 필요한 추가 자료를 확인하세요. 검토 기록 입력은 기준 확인을 대신하지 않습니다.');
table(issues,issueHeaders,issueRows,'ReviewIssues',[36,23,28,11,22,68,68,17,48,38,20,16]);
if(issueRows.length){
 issues.getRange(`F6:G${issueRows.length+5}`).format.wrapText=true;
 issues.getRange(`A6:L${issueRows.length+5}`).format.rowHeight=76;
 issues.getRange(`H6:L${issueRows.length+5}`).format.fill=amber;
 issues.getRange(`H6:H${issueRows.length+5}`).dataValidation={rule:{type:'list',values:['미검토','검토중','추가자료요청','검토완료']}};
 issues.getRange(`L6:L${issueRows.length+5}`).setNumberFormat('yyyy-mm-dd');
}else issues.getRange('A7').values=[['보고된 입력·기준 이슈 없음. 개별 검사 수행 여부는 검토요약에서 확인하세요.']];
base(summary,'감사 지원 검토조서','결과 상태와 수행 범위를 확인한 뒤 상세 검토를 진행하세요.','I',Math.max(35,p.checks.length+16));
summary.tabColor=dark;
summary.getRange('A4:E5').values=[['회사',p.entity,null,'기간',p.period],['처리 상태',p.execution_status,null,'검토 상태','미검토']];
summary.getRange('B5').format.wrapText=true;summary.getRange('A5:E5').format.rowHeight=38;
summary.getRange('A7:B7').values=[['항목','결과']];
summary.getRange('A7:B7').format={fill:dark,font:{color:'#FFFFFF',bold:true}};
summary.getRange('A8:B12').values=p.summary.map(([k,v])=>[k,v===null?'미실행':v]);
summary.getRange('B8:B12').format.wrapText=true;summary.getRange('A8:B12').format.rowHeight=36;
summary.getRange('B8:B12').conditionalFormats.add('containsText',{text:'미실행',format:{fill:amber,font:{bold:true,color:'#795200'}}});
summary.getRange('A14:E14').values=[['검사','수행 여부','탐지 행','탐지 전표','미실행 사유']];
summary.getRange('A14:E14').format={fill:dark,font:{color:'#FFFFFF',bold:true},rowHeight:30};
if(p.checks.length){
 summary.getRangeByIndexes(14,0,p.checks.length,5).values=p.checks.map(row=>row.map(v=>v===null?'미실행':v));
 summary.getRangeByIndexes(14,0,p.checks.length,5).format.rowHeight=44;
 summary.getRangeByIndexes(14,1,p.checks.length,1).format.wrapText=true;
 summary.getRangeByIndexes(14,4,p.checks.length,1).format.wrapText=true;
}
summary.getRange('A4:A40').format.columnWidth=27;
summary.getRange('B4:B40').format.columnWidth=44;
summary.getRange('C4:D40').format.columnWidth=16;
summary.getRange('E4:E40').format.columnWidth=62;
summary.getRange('F1:F40').format.columnWidth=3;
summary.getRange('G1:G40').format.columnWidth=43;
summary.getRange('H1:H40').format.columnWidth=18;
summary.getRange('I1:I40').format.columnWidth=3;
summary.getRange('G7:H10').values=[['검토 진행','값'],['행별 검토완료',null],['전체 검토대상 행',rows.length],['입력·기준 이슈',issueRows.length]];
summary.getRange('G7:H7').format={fill:dark,font:{color:'#FFFFFF',bold:true}};
function col(n){let s='';for(n++;n>0;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;}
if(rows.length){
 const reviewCol=col(primary.columns.indexOf('검토 상태'));
 summary.getRange('H8').formulas=[[`=COUNTIF('검토대상'!${reviewCol}6:${reviewCol}${rows.length+5},"검토완료")`]];
 summary.getRange('H9').formulas=[[`=ROWS('검토대상'!${reviewCol}6:${reviewCol}${rows.length+5})`]];
}else summary.getRange('H8:H9').values=[[p.execution_status.includes('계산 미실행')?'미실행':0]];
summary.getRange('G12').values=[['노란색 셀은 검토 기록 입력란입니다.']];
summary.getRange('G13').values=[['검토 상태를 입력해도 대사 기준이 확인되거나 재분석되지는 않습니다.']];
summary.getRange('G13').format.wrapText=true;summary.getRange('G13:H13').format.rowHeight=46;
const conditionRows=[];
for(const [key,value] of Object.entries(p.conditions)){
 if(key==='config')for(const [k,v] of Object.entries(value))conditionRows.push([`검사 조건 ${k}`,typeof v==='object'?JSON.stringify(v):v]);
 else conditionRows.push([key,typeof value==='object'?JSON.stringify(value):value]);
}
base(conditions,'입력 및 분석 조건','원본을 변경하지 않고 선택한 조건과 수행 범위를 기록합니다.','D',conditionRows.length+10);
table(conditions,['항목','값'],conditionRows,'ReviewConditions',[38,115]);
conditions.getRange(`B6:B${conditionRows.length+5}`).format.wrapText=true;
conditions.getRange(`A6:B${conditionRows.length+5}`).format.rowHeight=48;
// 상태는 계산 결과에서 유지한다. 미실행을 0 또는 정상으로 바꾸지 않는다.
wb.recalculate();
const inspection=await wb.inspect({kind:'table',range:'검토요약!A4:H12',include:'values,formulas',tableMaxRows:12,tableMaxCols:8,maxChars:2200});
console.log(inspection.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:1500});
console.log(errors.ndjson);
await fs.mkdir(path.dirname(outputFile),{recursive:true});
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(outputFile);
for(const sheet of sheets){
 const preview=await wb.render({sheetName:sheet.name,range:sheet.name==='검토요약'?'A1:I18':sheet.name==='검토대상'?'A1:I9':sheet.name==='확인필요사항'?'A1:G8':'A1:B12',scale:1,format:'png'});
 await fs.writeFile(path.join(path.dirname(outputFile),`_preview_${sheet.name}.png`),new Uint8Array(await preview.arrayBuffer()));
}
console.log(JSON.stringify({exported:true,reviewRows:rows.length,issueRows:issueRows.length}));
