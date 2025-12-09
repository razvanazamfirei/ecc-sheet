#!/usr/bin/env python3
"""
Main entry point for the ECC Sheet application
Starts the Flask app with the scheduler
"""

import atexit

from backend.app import app, init_db
from backend.scheduler.enhanced_scheduler import start_scheduler

if __name__ == "__main__":
    # Initialize database
    init_db()

    # Start the scheduler for automated emails
    scheduler = start_scheduler(app)

    # Shut down the scheduler when exiting the app
    atexit.register(scheduler.shutdown)

    # Run the Flask app
    app.run(debug=False, host="0.0.0.0", port=6060)
