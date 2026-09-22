from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class APIError(Exception):
    def __init__(self, status: int, code: str):
        self.status = status
        self.code = code


def install_error_handlers(app: FastAPI):
    @app.exception_handler(APIError)
    async def api_error(_request: Request, error: APIError):
        return JSONResponse(
            status_code=error.status,
            content={
                "error": {
                    "code": error.code,
                    "message": error.code,
                    "details": {},
                    "request_id": str(uuid4()),
                }
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, error: RequestValidationError):
        # Never echo input values (passwords, invite codes, tokens).
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request",
                    "details": {
                        "fields": [
                            {"location": list(e["loc"]), "type": e["type"]} for e in error.errors()
                        ]
                    },
                    "request_id": str(uuid4()),
                }
            },
        )
