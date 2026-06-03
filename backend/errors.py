"""Error handling for the ECC Sheet application"""

from flask import jsonify

from backend.utils import setup_logging

logger = setup_logging()


class APIError(Exception):
    """Base API error with user-friendly message"""

    def __init__(self, message, status_code=400, payload=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        """Convert error to dictionary for JSON response"""
        response = {
            "success": False,
            "error": self.message,
            "type": self.__class__.__name__,
        }
        if self.payload:
            response["details"] = self.payload
        return response


class _FixedStatusAPIError(APIError):
    """API error with a subclass-defined status code."""

    status_code = 400

    def __init__(self, message, payload=None) -> None:
        super().__init__(message, status_code=self.status_code, payload=payload)


class ValidationError(_FixedStatusAPIError):
    """Validation error for invalid input"""


class NotFoundError(_FixedStatusAPIError):
    """Resource not found error"""

    status_code = 404


class NotAllowedError(_FixedStatusAPIError):
    """Permission denied error"""

    status_code = 403


class ConflictError(_FixedStatusAPIError):
    """Resource conflict error"""

    status_code = 409


class DatabaseError(_FixedStatusAPIError):
    """Database operation error"""

    status_code = 503


class SAMLConfigError(RuntimeError):
    """Base exception for SAML configuration problems."""


class SAMLMissingDependencyError(SAMLConfigError):
    """Raised when the python3-saml library is not installed."""


class SAMLSettingsNotFoundError(SAMLConfigError):
    """Raised when no SAML settings source is provided or the file is missing."""


class SAMLInvalidJSONError(SAMLConfigError):
    """Raised when a SAML settings source contains malformed JSON."""


class SAMLInvalidSettingsError(SAMLConfigError):
    """Raised when SAML settings parse successfully but are not a JSON object."""


class SAMLRequestTypeError(SAMLConfigError):
    """Raised when SAML request bookkeeping receives an unsupported type."""


def register_error_handlers(app):
    """Register error handlers with Flask app"""

    @app.errorhandler(APIError)
    def handle_api_error(error):
        """Handle API errors"""
        logger.error(
            "API Error: %s (status: %d)",
            error.message,
            error.status_code,
            extra={"payload": error.payload},
        )
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 errors"""
        logger.warning("404 Not Found: %s", error)
        return (
            jsonify(
                {
                    "success": False,
                    "error": "The requested resource was not found",
                    "type": "NotFoundError",
                }
            ),
            404,
        )

    @app.errorhandler(500)
    def handle_internal_error(error):
        """Handle unexpected server errors"""
        logger.error("Internal Server Error: %s", error)
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An unexpected error occurred. The issue has been logged.",
                    "type": "InternalServerError",
                }
            ),
            500,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Catch-all for unexpected exceptions"""
        logger.error("Unexpected Error: %s", error)
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An unexpected error occurred. Please try again.",
                    "type": type(error).__name__,
                }
            ),
            500,
        )
