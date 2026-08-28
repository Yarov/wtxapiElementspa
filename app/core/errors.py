from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.responses import JSONResponse


def _slug(code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "unprocessable_entity",
        500: "internal_error",
        502: "upstream_error",
        503: "service_unavailable",
    }.get(code, "error")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(FastAPIHTTPException)
    async def _handler(request: Request, exc: FastAPIHTTPException):  # noqa: ARG001
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": _slug(exc.status_code), "message": exc.detail}},
        )
