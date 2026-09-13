"""Domain errors raised by the store, mapped to HTTP responses in main.py.

Codes mirror frontend/js/mockApi.js's ApiError codes and openapi.yaml's
Error schema, so the frontend can eventually switch from the mock to real
HTTP calls without touching its error-handling branches.
"""


class ApiError(Exception):
    code: str
    status_code: int

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(ApiError):
    code = "NOT_FOUND"
    status_code = 404


class TableUnavailableError(ApiError):
    code = "TABLE_UNAVAILABLE"
    status_code = 409


class DuplicatePhoneError(ApiError):
    code = "DUPLICATE_PHONE"
    status_code = 409


class PartyTooLargeError(ApiError):
    code = "PARTY_TOO_LARGE"
    status_code = 422


class InvalidQueryError(ApiError):
    code = "VALIDATION_ERROR"
    status_code = 400
