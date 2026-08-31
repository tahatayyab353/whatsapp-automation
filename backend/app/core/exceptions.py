from typing import Any, Dict, Optional


class AppException(Exception):
    """
    Base exception class for all application-specific domain errors.
    """
    def __init__(
        self,
        message: str,
        code: str = "APPLICATION_ERROR",
        status_code: int = 400,
        details: Optional[Any] = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None) -> None:
        super().__init__(message=message, code="NOT_FOUND", status_code=404, details=details)


class BadRequestException(AppException):
    def __init__(self, message: str = "Bad request", details: Optional[Any] = None) -> None:
        super().__init__(message=message, code="BAD_REQUEST", status_code=400, details=details)


class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict", details: Optional[Any] = None) -> None:
        super().__init__(message=message, code="CONFLICT", status_code=409, details=details)

