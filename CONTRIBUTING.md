# Contributing to ECC Sheet

Thank you for your interest in contributing to the ECC Sheet project. This
document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Database Migrations](#database-migrations)
- [Pull Request Process](#pull-request-process)
- [Commit Message Guidelines](#commit-message-guidelines)

## Code of Conduct

This project adheres to professional standards of conduct:

- Be respectful and inclusive
- Focus on constructive feedback
- Prioritize patient data security and privacy
- Follow medical software best practices

## Getting Started

### Prerequisites

- Python 3.13
- Bun (JavaScript runtime)
- Git
- Basic understanding of Flask and SQLAlchemy
- Familiarity with medical shift tracking workflows

### Development Setup

1. Fork and clone the repository:

```bash
git clone https://github.com/your-username/ecc-sheet.git
cd ecc-sheet
```

2. Set up the backend:

```bash
uv venv
source .venv/bin/activate
uv sync
```

3. Set up the frontend:

```bash
bun install
bun run build
```

4. Create a `.env` file:

```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Apply database migrations:

```bash
uv run flask --app backend.app db upgrade
```

6. Run the application:

```bash
uv run python -m backend.app
```

## Development Workflow

### Branch Naming

Use descriptive branch names:

- `feature/add-resident-export` - New features
- `fix/overtime-calculation-bug` - Bug fixes
- `docs/update-api-documentation` - Documentation updates
- `refactor/simplify-audit-logging` - Code refactoring
- `test/add-role-model-tests` - Test additions

### Making Changes

1. Create a new branch from `main`:

2. Make your changes following the [Coding Standards](#coding-standards)

3. Test your changes thoroughly

4. Format your code:

```bash
# Backend (Python)
# Linting is done via Ruff (automatic in CI)

# Frontend (JavaScript/CSS/HTML)
bun run format
```

5. Commit your changes following
   [Commit Message Guidelines](#commit-message-guidelines)

6. Push to your fork and create a pull request

## Coding Standards

### Python (Backend)

- Follow PEP 8 style guide
- Use type hints where appropriate
- Maximum line length: 100 characters
- Use descriptive variable and function names
- Add docstrings for public functions and classes
- Use route blueprints for new endpoints

Example:

```python
def calculate_overtime(exit_time: str, cutoff_hour: int, cutoff_minute: int) -> float:
    """
    Calculate overtime hours based on exit time and cutoff.

    Args:
        exit_time: Exit time in HH:MM format
        cutoff_hour: Cutoff hour (0-23)
        cutoff_minute: Cutoff minute (0-59)

    Returns:
        Overtime hours as float
    """
    # Implementation
    pass
```

### Route Blueprint Organization

- New routes should be organized into blueprints in `backend/routes/`
- Each blueprint should have a clear purpose (e.g., `entries.py`, `reports.py`)
- Register blueprints in `backend/routes/_registry.py`
- Use `@admin_required` decorator for admin-only routes

Example:

```python
# backend/routes/my_feature.py
from flask import Blueprint, jsonify
from backend.auth import admin_required

bp = Blueprint('my_feature', __name__)

@bp.route('/my-endpoint')
@admin_required
def my_endpoint():
    return jsonify({'status': 'success'})
```

### JavaScript (Frontend)

- Use ES6+ syntax
- Follow Prettier configuration (4-space indentation)
- Use `const` and `let`, avoid `var`
- Use template literals for string interpolation
- Add comments for complex logic
- Write tests for new functionality

Example:

```javascript
const calculateOvertimeHours = (exitTime, cutoffHour, cutoffMinute) => {
  // Parse exit time and calculate overtime
  const exit = DateTime.fromFormat(exitTime, "HH:mm");
  const cutoff = DateTime.fromObject({
    hour: cutoffHour,
    minute: cutoffMinute,
  });

  return exit > cutoff ? exit.diff(cutoff, "hours").hours : 0;
};
```

### CSS

- Follow Prettier configuration
- Use Bootstrap utilities when possible
- Custom CSS only when Bootstrap doesn't suffice
- Use BEM naming for custom classes
- Run Stylelint: `bun run lint:css`

### HTML (Jinja2 Templates)

- Use 4-space indentation (Prettier)
- Keep templates modular and DRY
- Use semantic HTML5 elements
- Include CSRF tokens in all forms
- Set `lang="en-GB"` for 24-hour time format

## Testing

### Backend Testing (pytest)

**Coverage Requirement: 99%**

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=backend --cov-report=html

# Run specific test file
uv run pytest tests/test_models.py -v

# Run specific test
uv run pytest tests/test_models.py::test_overtime_calculation -v
```

### Frontend Testing (Vitest)

```bash
# Run all tests
bun run test

# Run with coverage
bun run test:coverage

# Run specific test file
bun run test frontend/static/js/__tests__/luxon-utils.test.js

# Watch mode
bun run test --watch
```

### Writing Tests

#### Backend Tests (pytest)

- Write tests for all new features
- Maintain or improve code coverage (target: 99%)
- Use descriptive test names
- Follow the AAA pattern (Arrange, Act, Assert)
- Use fixtures from `conftest.py`

Example:

```python
def test_overtime_calculation_after_cutoff(app):
    """Test that overtime is calculated correctly when exit time is after cutoff."""
    with app.app_context():
        # Arrange
        role = Role(name="ECC 1", cutoff_hour=17, cutoff_minute=30)
        db.session.add(role)
        db.session.commit()

        entry = TimeEntry(role_id=role.id, exit_time="19:00")

        # Act
        overtime = entry.calculate_overtime()

        # Assert
        assert overtime == 1.5  # 1.5 hours of overtime
```

#### Frontend Tests (Vitest)

- Write tests for new JavaScript functionality
- Maintain or improve coverage
- Mock DOM elements when needed
- Test user interactions

Example:

```javascript
describe("roundToFiveMinutes", () => {
  it("should round up to next 5-minute increment", () => {
    // Arrange
    const time = "14:23";

    // Act
    const rounded = roundToFiveMinutes(time);

    // Assert
    expect(rounded).toBe("14:30");
  });
});
```

### Test Coverage Requirements

- **Backend:** Minimum 99% coverage (enforced in CI)
- **Frontend:** Minimum 78% coverage (enforced in CI)
- New features: Add tests that maintain or improve coverage
- Bug fixes: Add a test that reproduces the bug
- Refactoring: Maintain existing coverage

### CI/CD Pipeline

All pull requests trigger the GitHub Actions workflow:

1. **Backend Tests** — Python 3.13, pytest with coverage
2. **Frontend Tests** — Bun, Vitest with coverage
3. **Frontend Build & Lint** - Prettier check, Stylelint, Vite build
4. **Security Scan** — Bandit security analysis
5. **Coverage Upload** — Codecov reporting

All checks must pass before merging.

## Database Migrations

### Creating Migrations

When you modify database models:

1. Make changes to `backend/models.py`
2. Generate migration:

```bash
uv run flask --app backend.app db migrate -m "Descriptive message"
```

3. Review the generated migration in `migrations/versions/`
4. Edit if necessary (Alembic may not detect all changes)
5. Test the migration:

```bash
# Apply migration
uv run flask --app backend.app db upgrade

# Test rollback
uv run flask --app backend.app db downgrade -1

# Reapply
uv run flask --app backend.app db upgrade
```

## Pull Request Process

### Before Submitting

- [ ] Code follows project style guidelines
- [ ] All tests pass locally (backend and frontend)
- [ ] Code is formatted (run `bun run format` for a frontend)
- [ ] New tests added for new features
- [ ] Test coverage meets requirements (99% backend, 78% frontend)
- [ ] Documentation updated if needed
- [ ] Database migrations included if applicable
- [ ] No merge conflicts with the main branch
- [ ] All CI/CD checks pass

### PR Description Template

```markdown
## Description

Brief description of changes

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactoring
- [ ] Performance improvement

## Testing

Describe testing performed

Backend:

- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Coverage maintained at 99%

Frontend:

- [ ] Vitest tests added/updated?
- [ ] All tests pass
- [ ] Coverage maintained

## Database Changes

- [ ] No database changes
- [ ] Migration included
- [ ] Migration tested (upgrade and downgrade)

## Screenshots (if applicable)

Add screenshots for UI changes

## Checklist

- [ ] Tests pass
- [ ] Code formatted
- [ ] Documentation updated
- [ ] CI/CD checks pass
- [ ] Coverage requirements met
```

### Review Process

1. Automated CI checks must pass
2. At least one maintainer review is required
3. Address review feedback
4. Squash commits if requested
5. Maintainer will merge when approved

## Commit Message Guidelines

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements

### Examples

```
feat(reports): add CSV export functionality

Add ability to export overtime reports as CSV files.
Includes proper column headers and date formatting.

Closes #123
```

```
fix(overtime): correct calculation for overnight shifts

Exit times before cutoff were incorrectly treated as same day.
Now properly handles overnight shifts by comparing to next day cutoff.

Fixes #456
```

```
docs(readme): update installation instructions

Add Bun installation step and clarify UV usage.
Update Python version requirement to 3.13.
```

```
test(holidays): add tests for holiday management

Add comprehensive tests for holiday CRUD operations.
Increases backend coverage from 98% to 99%.
```

### Best Practices

- Use an imperative mood ("add" not "added")
- First line max 72 characters
- Separate the subject from the body with a blank line
- Explain what and why, not how
- Reference issues and PRs when applicable

## Code Review Guidelines

### For Reviewers

- Be constructive and respectful
- Review both code and tests
- Check for security issues
- Verify migrations are safe
- Test locally when possible
- Respond within 48 hours
- Verify CI/CD checks pass
- Check test coverage requirements

### For Contributors

- Respond to feedback promptly
- Ask questions if feedback is unclear
- Make requested changes
- Update PR description if scope changes
- Be patient during the review process
- Address all CI/CD failures

## Security

### Reporting Security Issues

**Do not open public issues for security vulnerabilities.**

Instead, email security concerns to the project maintainers.

Include:

- Description of vulnerability
- Steps to reproduce
- Potential impact
- The suggested fix (if any)

### Security Best Practices

- Never commit secrets or credentials
- Use environment variables for sensitive data
- Validate all user inputs
- Use parameterized queries (SQLAlchemy handles this)
- Follow OWASP guidelines
- Review audit logging for security events
- Use `@admin_required` decorator for sensitive routes

## Questions?

- Check existing issues and discussions
- Read `CLAUDE.md` for detailed documentation
- Review `docs/ARCHITECTURE.md` for system design
- Ask questions in pull request comments
- Contact maintainers if needed

## Recognition

Contributors will be recognized in:

- GitHub contributors list
- Release notes for significant contributions
- Project documentation

Thank you for contributing to ECC Sheet.
