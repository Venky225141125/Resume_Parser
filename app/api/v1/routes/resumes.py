from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import pipeline_dep, settings_dep, store_dep
from app.core.config import Settings
from app.core.exceptions import FileTooLargeError, NotFoundError
from app.core.security import require_api_key
from app.pipeline.orchestrator import ParsePipeline
from app.schemas.candidate import ParseResponse
from app.services.store import ResultStore

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/parse", response_model=ParseResponse)
async def parse_resume(
    file: UploadFile = File(...),
    settings: Settings = Depends(settings_dep),
    pipeline: ParsePipeline = Depends(pipeline_dep),
    store: ResultStore = Depends(store_dep),
    _: None = Depends(require_api_key),
) -> ParseResponse:
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise FileTooLargeError()
    result = pipeline.parse_bytes(data, file.filename or "resume", file.content_type)
    store.save(result)
    return result


@router.get("/{document_id}", response_model=ParseResponse)
def get_resume(
    document_id: str,
    store: ResultStore = Depends(store_dep),
    _: None = Depends(require_api_key),
) -> ParseResponse:
    result = store.get(document_id)
    if result is None:
        raise NotFoundError(f"No parse result found for document_id '{document_id}'.")
    return result
