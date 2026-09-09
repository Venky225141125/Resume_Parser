from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import pipeline_dep, settings_dep
from app.core.config import Settings
from app.core.exceptions import FileTooLargeError, NotImplementedStageError
from app.core.security import require_api_key
from app.pipeline.orchestrator import ParsePipeline
from app.schemas.candidate import ParseResponse

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/parse", response_model=ParseResponse)
async def parse_resume(
    file: UploadFile = File(...),
    settings: Settings = Depends(settings_dep),
    pipeline: ParsePipeline = Depends(pipeline_dep),
    _: None = Depends(require_api_key),
) -> ParseResponse:
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise FileTooLargeError()
    del pipeline
    raise NotImplementedStageError(
        "Resume parsing API is intentionally disabled until the next phase is implemented."
    )


@router.get("/{document_id}")
def get_resume(
    document_id: str,
    _: None = Depends(require_api_key),
) -> ParseResponse:
    del document_id
    raise NotImplementedStageError(
        "Document lookup is not implemented in Phase 1 (scaffold only)."
    )
