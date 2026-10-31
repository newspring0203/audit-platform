"""소유자 확인과 작업별 검토 파일 읽기·쓰기."""
import json
import os
from pydantic import ValidationError
from .storage import ServiceError


class ReviewFiles:
    def __init__(self, store, small_json):
        self.store = store
        self.small_json = small_json

    def owned(self, job_id, request, complete=False):
        row = self.store.owned(job_id, request.state.principal)
        if complete and row['status'] != 'completed':
            raise ServiceError('RESULT_NOT_READY', '완료된 결과에서 사용할 수 있습니다.', 409)
        return (row, self.store.job_path(row))

    def load(self, path, default=None):
        if not path.exists():
            if default is not None:
                return default
            raise ServiceError('REVIEW_NOT_AVAILABLE', '이전 실행에는 검토 화면 데이터가 없습니다. 새 작업으로 실행하세요.', 404)
        return json.loads(path.read_text())

    def snapshot(self, folder):
        return self.load(folder / 'report' / 'review_snapshot.json')

    def save(self, path, data):
        tmp = path.with_suffix('.part')
        self.store.write_private(tmp, json.dumps(data, ensure_ascii=False, allow_nan=False).encode())
        os.replace(tmp, path)

    async def body(self, request, model):
        try:
            return model.model_validate(await self.small_json(request))
        except ValidationError:
            raise ServiceError('INVALID_REVIEW_INPUT', '필수 항목·기간·검토 완료 조건을 확인하세요.', 422) from None

    def clean_assets(self, inputs):
        return {slot: {k: v for k, v in item.items() if k != 'stored_name' and k != 'history'} | {'previous_versions': [{k: v for k, v in h.items() if k != 'stored_name'} for h in item.get('history', [])]} for slot, item in inputs.items()}
