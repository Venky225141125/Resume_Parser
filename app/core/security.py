from fastapi import Depends, Header

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError


def require_api_key(
    settings: Settings = Depends(get_settings),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Enforce API key when configured. Health routes skip this."""
    if not settings.api_auth_enabled:
        return
    if not x_api_key or x_api_key != settings.api_key:
        raise UnauthorizedError()
