"""업로드를 실행 가능한 파일로 취급하지 않는다. 확장자·내용·압축 용량을 함께 확인."""
from pathlib import Path
import zipfile
from .storage import ServiceError


def filename_suffix(name):
    if not name or len(name)>180 or '\x00' in name or '/' in name or '\\' in name:
        raise ServiceError('INVALID_FILENAME','파일명에 경로를 포함할 수 없습니다.',422)
    suffix=Path(name).suffix.lower()
    if suffix not in ('.csv','.txt','.xlsx'):raise ServiceError('FILE_TYPE_NOT_ALLOWED','CSV·TXT·XLSX 파일만 지원합니다.',422)
    return suffix


def validate_upload(path,suffix,*,max_uncompressed=128*1024*1024):
    if path.stat().st_size==0:raise ServiceError('EMPTY_FILE','빈 파일은 사용할 수 없습니다.',422)
    if suffix=='.xlsx':
        try:
            with zipfile.ZipFile(path) as z:
                entries=z.infolist();names={i.filename for i in entries}
                if '[Content_Types].xml' not in names or 'xl/workbook.xml' not in names:
                    raise ServiceError('INVALID_XLSX','실제 XLSX 구조가 아닙니다.',422)
                if len(entries)>5000 or sum(i.file_size for i in entries)>max_uncompressed:
                    raise ServiceError('ARCHIVE_LIMIT','압축 해제 후 용량 또는 항목 한도를 초과합니다.',413)
                if any(i.flag_bits&1 or 'vbaproject' in i.filename.lower() or i.filename.lower().startswith('xl/externallinks/') for i in entries):
                    raise ServiceError('ACTIVE_CONTENT_NOT_ALLOWED','매크로·암호화·외부 연결이 있는 파일은 지원하지 않습니다.',422)
                if any(i.file_size>max(1,i.compress_size)*1000 for i in entries):
                    raise ServiceError('ARCHIVE_LIMIT','압축 비율 한도를 초과합니다.',413)
                for item in entries:
                    if item.filename.lower().endswith(('.xml','.rels')):
                        with z.open(item) as stream:
                            tail=b''
                            while True:
                                chunk=stream.read(65536)
                                if not chunk:break
                                scanned=(tail+chunk).replace(b'\x00',b'').upper()
                                if b'<!DOCTYPE' in scanned or b'<!ENTITY' in scanned:
                                    raise ServiceError('UNSAFE_XML','DTD·엔티티 선언이 있는 문서는 지원하지 않습니다.',422)
                                tail=chunk[-64:]
        except (zipfile.BadZipFile,RuntimeError):raise ServiceError('INVALID_XLSX','XLSX 파일을 읽을 수 없습니다.',422) from None
    else:
        raw=path.read_bytes()
        if b'\x00' in raw:raise ServiceError('INVALID_TEXT_FILE','텍스트 파일에 바이너리 내용이 있습니다.',422)
        for encoding in ('utf-8-sig','cp949'):
            try:raw.decode(encoding);break
            except UnicodeDecodeError:continue
        else:raise ServiceError('INVALID_TEXT_ENCODING','UTF-8 또는 CP949 텍스트를 사용하세요.',422)
