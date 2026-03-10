"""Tests for error handling module."""

import json

import pytest
from flask import Flask

from backend.errors import (
    APIError,
    ConflictError,
    DatabaseError,
    NotAllowedError,
    NotFoundError,
    ValidationError,
    register_error_handlers,
)


class TestAPIError:
    """Tests for APIError base class."""

    def test_api_error_initialization(self):
        """Test APIError can be initialized."""
        error = APIError("Test error message")
        assert error.message == "Test error message"
        assert error.status_code == 400
        assert error.payload is None

    def test_api_error_with_status_code(self):
        """Test APIError with custom status code."""
        error = APIError("Test error", status_code=500)
        assert error.status_code == 500

    def test_api_error_with_payload(self):
        """Test APIError with payload."""
        error = APIError("Test error", payload={"field": "value"})
        assert error.payload == {"field": "value"}

    def test_api_error_to_dict(self):
        """Test APIError to_dict method."""
        error = APIError("Test error message")
        result = error.to_dict()

        assert result["success"] is False
        assert result["error"] == "Test error message"
        assert result["type"] == "APIError"
        assert "details" not in result

    def test_api_error_to_dict_with_payload(self):
        """Test APIError to_dict with payload."""
        error = APIError("Test error", payload={"field": "value"})
        result = error.to_dict()

        assert result["details"] == {"field": "value"}


class TestValidationError:
    """Tests for ValidationError."""

    def test_validation_error_initialization(self):
        """Test ValidationError initialization."""
        error = ValidationError("Invalid input")
        assert error.message == "Invalid input"
        assert error.status_code == 400

    def test_validation_error_with_payload(self):
        """Test ValidationError with payload."""
        error = ValidationError("Invalid input", payload={"field": "name"})
        assert error.payload == {"field": "name"}

    def test_validation_error_to_dict(self):
        """Test ValidationError to_dict."""
        error = ValidationError("Invalid input")
        result = error.to_dict()
        assert result["type"] == "ValidationError"


class TestNotFoundError:
    """Tests for NotFoundError."""

    def test_not_found_error_initialization(self):
        """Test NotFoundError initialization."""
        error = NotFoundError("Resource not found")
        assert error.message == "Resource not found"
        assert error.status_code == 404

    def test_not_found_error_to_dict(self):
        """Test NotFoundError to_dict."""
        error = NotFoundError("Resource not found")
        result = error.to_dict()
        assert result["type"] == "NotFoundError"


class TestNotAllowedError:
    """Tests for NotAllowedError."""

    def test_not_allowed_error_initialization(self):
        """Test NotAllowedError initialization."""
        error = NotAllowedError("Access denied")
        assert error.message == "Access denied"
        assert error.status_code == 403

    def test_not_allowed_error_to_dict(self):
        """Test NotAllowedError to_dict."""
        error = NotAllowedError("Access denied")
        result = error.to_dict()
        assert result["type"] == "NotAllowedError"


class TestConflictError:
    """Tests for ConflictError."""

    def test_conflict_error_initialization(self):
        """Test ConflictError initialization."""
        error = ConflictError("Resource already exists")
        assert error.message == "Resource already exists"
        assert error.status_code == 409

    def test_conflict_error_to_dict(self):
        """Test ConflictError to_dict."""
        error = ConflictError("Resource already exists")
        result = error.to_dict()
        assert result["type"] == "ConflictError"


class TestDatabaseError:
    """Tests for DatabaseError."""

    def test_database_error_initialization(self):
        """Test DatabaseError initialization."""
        error = DatabaseError("Database unavailable")
        assert error.message == "Database unavailable"
        assert error.status_code == 503

    def test_database_error_to_dict(self):
        """Test DatabaseError to_dict."""
        error = DatabaseError("Database unavailable")
        result = error.to_dict()
        assert result["type"] == "DatabaseError"


@pytest.fixture
def error_test_app():
    """Create a fresh Flask app with error handlers and test routes."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    session_value = "test-session-value"
    app.config["SECRET_KEY"] = session_value

    # Register error handlers
    register_error_handlers(app)

    # Add test routes before any requests
    @app.route("/test-api-error")
    def raise_api_error():
        raise APIError("Test API error", status_code=400)

    @app.route("/test-validation-error")
    def raise_validation_error():
        raise ValidationError("Invalid data", payload={"field": "email"})

    @app.route("/test-not-found-error")
    def raise_not_found_error():
        raise NotFoundError("Item not found")

    @app.route("/test-permission-error")
    def raise_permission_error():
        raise NotAllowedError("Access denied")

    @app.route("/test-error-payload")
    def raise_error_with_payload():
        raise APIError(
            "Error with details",
            status_code=400,
            payload={"field": "name", "reason": "required"},
        )

    @app.route("/test-conflict-error")
    def raise_conflict_error():
        raise ConflictError("Resource conflict")

    @app.route("/test-database-error")
    def raise_database_error():
        raise DatabaseError("Database unavailable")

    @app.route("/test-500-error")
    def raise_500_error():
        raise RuntimeError("Unexpected server error")

    return app


@pytest.fixture
def error_test_client(error_test_app):
    """Create a test client for the error test app."""
    return error_test_app.test_client()


class TestErrorHandlers:
    """Tests for registered error handlers."""

    def test_register_error_handlers(self):
        """Test that error handlers can be registered."""
        app = Flask(__name__)
        # Should not raise an error
        register_error_handlers(app)

    def test_api_error_handler(self, error_test_client):
        """Test APIError handler returns JSON."""
        response = error_test_client.get("/test-api-error")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["error"] == "Test API error"

    def test_validation_error_handler(self, error_test_client):
        """Test ValidationError handler."""
        response = error_test_client.get("/test-validation-error")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["type"] == "ValidationError"

    def test_not_found_error_handler(self, error_test_client):
        """Test NotFoundError handler."""
        response = error_test_client.get("/test-not-found-error")
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["type"] == "NotFoundError"

    def test_permission_error_handler(self, error_test_client):
        """Test NotAllowedError handler."""
        response = error_test_client.get("/test-permission-error")
        assert response.status_code == 403
        data = json.loads(response.data)
        assert data["type"] == "NotAllowedError"

    def test_conflict_error_handler(self, error_test_client):
        """Test ConflictError handler."""
        response = error_test_client.get("/test-conflict-error")
        assert response.status_code == 409
        data = json.loads(response.data)
        assert data["type"] == "ConflictError"

    def test_database_error_handler(self, error_test_client):
        """Test DatabaseError handler."""
        response = error_test_client.get("/test-database-error")
        assert response.status_code == 503
        data = json.loads(response.data)
        assert data["type"] == "DatabaseError"

    def test_404_handler(self, error_test_client):
        """Test 404 error handler."""
        response = error_test_client.get("/nonexistent-route-that-does-not-exist")
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
        assert "not found" in data["error"].lower()

    def test_500_error_handler(self, error_test_client):
        """Test 500 error handler via unexpected exception."""
        response = error_test_client.get("/test-500-error")
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["success"] is False
        assert "type" in data

    def test_500_error_handler_via_abort(self, error_test_app):
        """Test 500 error handler via abort(500)."""
        from flask import abort

        @error_test_app.route("/test-abort-500")
        def raise_abort_500():
            abort(500)

        client = error_test_app.test_client()
        response = client.get("/test-abort-500")
        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["success"] is False
        assert "unexpected error" in data["error"].lower()

    def test_api_error_with_payload_in_handler(self, error_test_client):
        """Test API error handler includes payload."""
        response = error_test_client.get("/test-error-payload")
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["details"]["field"] == "name"
        assert data["details"]["reason"] == "required"
