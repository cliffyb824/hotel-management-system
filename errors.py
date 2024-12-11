from flask import jsonify

class APIError(Exception):
    """Base class for API errors"""
    def __init__(self, message, status_code=400, payload=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        rv['status'] = 'error'
        return rv

class ValidationError(APIError):
    """Raised when validation fails"""
    pass

class ResourceNotFoundError(APIError):
    """Raised when a resource is not found"""
    def __init__(self, message="Resource not found", payload=None):
        super().__init__(message, status_code=404, payload=payload)

class AuthenticationError(APIError):
    """Raised when authentication fails"""
    def __init__(self, message="Authentication failed", payload=None):
        super().__init__(message, status_code=401, payload=payload)

def handle_api_error(error):
    """Handler for API errors"""
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

def register_error_handlers(app):
    """Register error handlers with the Flask app"""
    app.register_error_handler(APIError, handle_api_error)
    app.register_error_handler(404, lambda e: handle_api_error(
        ResourceNotFoundError("The requested resource was not found")))
