#!/usr/bin/env python3
"""
Database migration management script.
This script provides commands for managing database migrations.
"""

from flask_migrate import Migrate, current, downgrade, history, init, migrate, upgrade

from backend.app import app, db

# Initialize Flask-Migrate
migrate_instance = Migrate(app, db)

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python manage.py [command]")
        print("\nAvailable commands:")
        print("  init       - Initialize migrations directory")
        print("  migrate    - Generate a new migration")
        print("  upgrade    - Apply migrations to database")
        print("  downgrade  - Revert last migration")
        print("  current    - Show current migration version")
        print("  history    - Show migration history")
        print("\nExamples:")
        print("  python manage.py init")
        print('  python manage.py migrate -m "Add epic_id to residents"')
        print("  python manage.py upgrade")
        sys.exit(1)

    command = sys.argv[1]

    with app.app_context():
        if command == "init":
            print("Initializing migrations directory...")
            init()
        elif command == "migrate":
            message = None
            if "-m" in sys.argv:
                idx = sys.argv.index("-m")
                if idx + 1 < len(sys.argv):
                    message = sys.argv[idx + 1]
            print("Generating new migration...")
            migrate(message=message)
        elif command == "upgrade":
            print("Applying migrations to database...")
            upgrade()
        elif command == "downgrade":
            print("Reverting last migration...")
            downgrade()
        elif command == "current":
            print("Current migration version:")
            current()
        elif command == "history":
            print("Migration history:")
            history()
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)

    print("\nDone!")
