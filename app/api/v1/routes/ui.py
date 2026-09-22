"""Serves the manual compare-original-vs-parsed page. Not part of the JSON API."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.paths import repo_root

router = APIRouter(tags=["ui"], include_in_schema=False)

_INDEX_PATH = repo_root() / "app" / "static" / "index.html"


@router.get("/ui", response_class=HTMLResponse)
def ui_index() -> str:
    return _INDEX_PATH.read_text(encoding="utf-8")
