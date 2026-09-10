from typing import Optional

from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str, field: Optional[str] = None) -> HTTPException:
    detail = {"code": code, "message": message}
    if field is not None:
        detail["field"] = field
    return HTTPException(status_code=status_code, detail=detail)

