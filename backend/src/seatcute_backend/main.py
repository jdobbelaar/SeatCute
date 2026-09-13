from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from .errors import ApiError
from .routers import config, queue, tables

app = FastAPI(
    title="SeatCute API",
    version="0.1.0",
    description="See openapi.yaml at the repository root for the hand-authored contract this implements.",
)

# Dev-only, permissive CORS: the frontend (frontend/index.html, kiosk.html)
# is served from a different origin (a plain static file server) than this
# API, and browsers enforce CORS for fetch() even though tools like curl
# don't. Tighten allow_origins to the real frontend origin(s) once this
# stops being a local mock backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)
app.include_router(tables.router)
app.include_router(queue.router)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Body validation errors (e.g. a malformed PUT /config or POST /queue)
    # are 422s; query/path validation errors (e.g. an invalid `size` on
    # GET /queue) are 400s -- matching the distinction openapi.yaml documents
    # per endpoint.
    errors = exc.errors()
    locations = {err["loc"][0] for err in errors if err.get("loc")}
    status_code = 422 if "body" in locations else 400

    message = "; ".join(
        f"{'.'.join(str(part) for part in err['loc'][1:])}: {err['msg']}" for err in errors
    )
    return JSONResponse(status_code=status_code, content={"code": "VALIDATION_ERROR", "message": message})
