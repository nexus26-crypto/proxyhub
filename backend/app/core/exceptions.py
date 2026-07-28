class ProxyHubException(Exception):
    """Base exception for ProxyHub domain errors."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(ProxyHubException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ConflictError(ProxyHubException):
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message, status_code=409)


class UnauthorizedError(ProxyHubException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=401)


class ForbiddenError(ProxyHubException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=403)


class ValidationError(ProxyHubException):
    def __init__(self, message: str = "Validation error"):
        super().__init__(message, status_code=422)
