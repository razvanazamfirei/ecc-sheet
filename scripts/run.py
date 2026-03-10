#!/usr/bin/env python3
"""
Main entry point for the ECC Sheet application
Starts the Flask app with proper configuration
"""

from backend.app import app

if __name__ == "__main__":
    # Run the Flask app
    # Debug mode is disabled for production safety
    # Use host="0.0.0.0" to allow external connections if needed
    # Port can be configured via PORT environment variable in .env
    app.run(debug=False, host="0.0.0.0", port=app.config.get("PORT", 5000))
