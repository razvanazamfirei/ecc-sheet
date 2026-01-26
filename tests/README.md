# ECC Sheet Test Suite

Comprehensive test suite for the ECC Sheet application.

## Test Organization

The test suite is organized into several modules:

### test_models.py

Tests for database models and business logic:

- **Role model**: Creation, cutoff time formatting
- **Resident model**: Creation, activation/deactivation
- **TimeEntry model**: Relationships, nullable fields
- **DailySheet model**: Locking, submission, date uniqueness
- **Overtime calculations**: Same-day, overnight shifts, edge cases

### test_routes.py

Tests for Flask routes and API endpoints:

- **Index/Daily Sheet views**: Page loading, entry display
- **Adding entries**: Success cases, locked sheets
- **Deleting entries**: Permissions, locked sheets
- **Locking sheets**: Lock/unlock functionality
- **API endpoints**: Active residents, roles
- **Reports**: Generation, empty reports
- **Management pages**: Residents and roles CRUD operations
- **Workflow integration**: Complete end-to-end scenarios

### test_utils.py

Tests for utility functions:

- **Philadelphia timezone**: Time conversions, DST handling
- **Effective date**: 8 AM reset logic, edge cases
- **Time validation**: Format checking
- **String sanitization**: Input cleaning, max length
- **Quarter-hour rounding**: 15-minute increments
- **Database backup**: File creation, data integrity

### conftest.py

Pytest fixtures and test configuration:

- `app`: Test application with temporary database
- `client`: Test client for HTTP requests
- `db_session`: Database session management
- `sample_resident`, `sample_role`, `sample_time_entry`, `sample_daily_sheet`:
  Test data fixtures
- `clean_database`: Database cleanup between tests

## Running Tests

### Run all tests

```bash
pytest
```

### Run specific test file

```bash
pytest tests/test_models.py
pytest tests/test_routes.py
pytest tests/test_utils.py
```

### Run specific test class

```bash
pytest tests/test_models.py::TestOvertimeCalculation
pytest tests/test_routes.py::TestAPIEndpoints
pytest tests/test_utils.py::TestPhiladelphiaTime
```

### Run specific test method

```bash
pytest tests/test_models.py::TestOvertimeCalculation::test_overnight_overtime
```

### Run tests by marker

```bash
# Run only unit tests (fast, no database)
pytest -m unit

# Run only integration tests (with database)
pytest -m integration

# Run only overtime calculation tests
pytest -m overtime

# Run only timezone-related tests
pytest -m timezone
```

### Run with verbose output

```bash
pytest -v
```

### Run with coverage report

```bash
pytest --cov=. --cov-report=html
```

### Run tests and stop on first failure

```bash
pytest -x
```

### Run tests matching a keyword

```bash
pytest -k "overtime"
pytest -k "resident"
pytest -k "timezone"
```

## Test Markers

Tests are organized with pytest markers for selective execution:

- `@pytest.mark.unit`: Unit tests (fast, isolated)
- `@pytest.mark.integration`: Integration tests (database required)
- `@pytest.mark.overtime`: Overtime calculation tests
- `@pytest.mark.timezone`: Timezone-related tests
- `@pytest.mark.slow`: Slow-running tests

## Key Test Scenarios

### Overtime Calculation

The most critical feature. Tests cover:

- **Same-day overtime**: Exit after cutoff on same calendar day
- **Overnight shifts**: Exit before cutoff (treated as next day)
- **Edge cases**: Midnight, 8 AM, exactly at cutoff
- **Different cutoffs**: Various role cutoff times
- **15-minute increments**: Proper time rounding

Example:

- Cutoff: 17:30 (5:30 PM)
- Exit: 02:30 AM → 9.0 hours overtime (overnight)
- Exit: 20:00 (8:00 PM) → 2.5 hours overtime (same day)

### Timezone Handling

Philadelphia timezone (America/New_York) with 8 AM day reset:

- Times before 8 AM belong to previous calendar day
- Proper DST handling
- Timezone-aware datetime objects

### Locked Sheets

Tests verify that locked sheets:

- Cannot have entries added
- Cannot have entries deleted
- Can be unlocked

### Complete Workflows

End-to-end integration tests covering:

1. Add resident and role
2. Create time entry
3. View on daily sheet
4. Lock sheet
5. Generate report

## Writing New Tests

### Adding a new test

1. Choose the appropriate test file based on what you're testing
2. Add the test to an existing class or create a new class
3. Use appropriate pytest markers
4. Use fixtures for test data (`sample_resident`, `sample_role`, etc.)

Example:

```python
@pytest.mark.integration
class TestNewFeature:
    """Test description"""

    def test_feature_works(self, client, app, sample_resident):
        """Test that new feature works correctly"""
        with app.app_context():
            # Test code here
            response = client.get('/new-feature')
            assert response.status_code == 200
```

### Using fixtures

Fixtures are defined in `conftest.py` and automatically available:

```python
def test_with_fixtures(self, app, client, sample_resident, sample_role):
    """Fixtures are injected automatically"""
    with app.app_context():
        # sample_resident and sample_role are already created
        assert sample_resident.name == "Test Resident"
        assert sample_role.cutoff_hour == 17
```

### Test database

Each test uses a temporary SQLite database:

- Created in `conftest.py` with `tempfile.mkstemp()`
- Automatically cleaned up after test session
- Isolated from production database

## Coverage Goals

Target test coverage:

- **Models**: 100% (critical business logic)
- **Routes**: 95%+ (core functionality)
- **Utils**: 90%+ (helper functions)
- **Overall**: 90%+

## Continuous Integration

Tests should be run:

- Before every commit (pre-commit hook recommended)
- On every pull request
- Before deployment
- After any dependency updates

## Troubleshooting

### Tests fail with database errors

- Ensure you're in the UV virtual environment: `source .venv/bin/activate`
- Check that all dependencies are installed: `uv pip install -e .`
- Verify pytest is installed: `pytest --version`

### Timezone tests fail

- Check your system timezone settings
- Verify pytz is installed: `uv pip list | grep pytz`
- Tests use America/New_York timezone

### Import errors

- Ensure you're running from the project root directory
- Check PYTHONPATH includes current directory

### Fixtures not working

- Verify `conftest.py` is in the `tests/` directory
- Check fixture names match exactly (case-sensitive)
- Ensure fixtures have proper scope (`session`, `function`, etc.)
