"""자료 메모·기준서 참조·검토 기록의 입력 검증."""
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MaterialContext(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    label: str = Field(default='', max_length=160)
    pbc_reference: str = Field(default='', max_length=100)
    period_start: str = Field(default='', max_length=10)
    period_end: str = Field(default='', max_length=10)

    @model_validator(mode='after')
    def dates(self):
        if bool(self.period_start) != bool(self.period_end):
            raise ValueError('기간 시작·종료를 함께 입력하세요.')
        if self.period_start:
            if date.fromisoformat(self.period_start) > date.fromisoformat(self.period_end):
                raise ValueError('기간 순서를 확인하세요.')
        return self

class Reference(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    title: str = Field(min_length=1, max_length=200)
    issuer: str = Field(min_length=1, max_length=100)
    edition: str = Field(min_length=1, max_length=100)
    paragraph: str = Field(min_length=1, max_length=100)
    effective_date: str = Field(default='', max_length=10)
    url: str = Field(default='', max_length=1000)
    applicability_note: str = Field(min_length=1, max_length=2000)

    @field_validator('url')
    @classmethod
    def safe_url(cls, v):
        if v and (not v.startswith('https://') or any((c in v for c in '\r\n\x00'))):
            raise ValueError('https URL만 허용합니다.')
        return v

    @field_validator('effective_date')
    @classmethod
    def date_value(cls, v):
        if v:
            date.fromisoformat(v)
        return v

class ReviewNote(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    revision: int = Field(ge=0)
    status: str = Field(default='미검토', max_length=30)
    explanation: str = Field(default='', max_length=4000)
    evidence_reference: str = Field(default='', max_length=1000)
    conclusion: str = Field(default='', max_length=4000)
    reference_ids: list[str] = Field(default_factory=list, max_length=20)

    @field_validator('status')
    @classmethod
    def valid_status(cls, v):
        if v not in {'미검토', '검토중', '검토완료'}:
            raise ValueError('검토 상태 확인 필요')
        return v

    @model_validator(mode='after')
    def completion(self):
        if self.status == '검토완료' and (not self.conclusion.strip() or not self.evidence_reference.strip()):
            raise ValueError('검토완료에는 결론과 근거 참조가 필요합니다.')
        return self
