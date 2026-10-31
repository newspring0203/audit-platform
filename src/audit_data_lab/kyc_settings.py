"""로컬 환경변수 설정. 키는 repr·보고서·출력에 포함하지 않는다."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
from .kyc_transport import provider_error

ALLOWED={'DART_API_KEY','OPENAI_API_KEY','OPENAI_MODEL'}

def load_project_env(root):
    """간단한 KEY=value 및 따옴표만 지원. 셸 실행·변수 치환·기존 환경 덮어쓰기 없음."""
    path=Path(root)/'.env'
    if not path.is_file():return
    for line in path.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        if '=' not in line:provider_error('INVALID_ENV_FILE','.env에는 KEY=value 형식만 사용하세요.','Config')
        key,value=line.split('=',1);key=key.strip();value=value.strip()
        if key not in ALLOWED:continue
        if value[:1] in ('"',"'"):
            if len(value)<2 or value[-1]!=value[0]:provider_error('INVALID_ENV_FILE','.env 따옴표를 확인하세요.','Config')
            value=value[1:-1]
        os.environ.setdefault(key,value)

@dataclass(frozen=True)
class KycSettings:
    dart_api_key: str=field(repr=False)
    openai_api_key: str=field(default='',repr=False)
    model: str=''

    @classmethod
    def from_env(cls):
        return cls(os.environ.get('DART_API_KEY','').strip(),os.environ.get('OPENAI_API_KEY','').strip(),os.environ.get('OPENAI_MODEL','').strip())

    def require(self,with_ai=False):
        if not re.fullmatch(r'[A-Za-z0-9]{40}',self.dart_api_key):
            provider_error('DART_KEY_REQUIRED','로컬 .env의 DART_API_KEY에 발급받은 40자리 키를 설정하세요.','Config')
        if with_ai and not self.openai_api_key:
            provider_error('OPENAI_KEY_REQUIRED','AI 요약에는 OPENAI_API_KEY 설정이 필요합니다. 공시 수집만 먼저 실행할 수 있습니다.','Config')
        if with_ai and not self.model:
            provider_error('OPENAI_MODEL_REQUIRED','AI 요약에 사용할 OPENAI_MODEL을 명시적으로 설정하세요.','Config')
