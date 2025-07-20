# SentinelZero Test Suite

## Overview

This test suite provides comprehensive testing for the SentinelZero network scanning dashboard, covering both backend Python functionality and frontend React components.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Pytest configuration and fixtures
├── README.md                   # This file
├── unit/                       # Unit tests
│   ├── __init__.py
│   ├── test_database.py        # Database model tests
│   └── test_settings.py        # Settings functionality tests
├── integration/                # Integration tests
│   ├── __init__.py
│   ├── test_api_endpoints.py   # API endpoint tests
│   ├── test_iot_scan.py        # IoT scanning tests
│   └── test_multi_schedule.py  # Multi-schedule tests
├── e2e/                        # End-to-end tests
│   └── __init__.py
└── *.spec.js                   # Playwright frontend tests
```

## Test Types

### Backend Tests (Python/pytest)

- **Unit Tests**: Test individual functions and classes in isolation
- **Integration Tests**: Test API endpoints and component interactions
- **E2E Tests**: Test complete workflows and user scenarios

### Frontend Tests (Playwright)

- **Component Tests**: Test individual React components
- **Page Tests**: Test complete page functionality
- **User Flow Tests**: Test complete user journeys

## Running Tests

### Backend Tests

```bash
# Run all backend tests
npm run test:backend

# Run specific test types
npm run test:unit
npm run test:integration
npm run test:e2e

# Run with coverage
npm run test:coverage
```

### Frontend Tests

```bash
# Run all frontend tests
npm run test:frontend

# Run Playwright tests
npm run test:playwright

# Run Playwright with UI
npm run test:playwright:ui
```

### All Tests

```bash
# Run both backend and frontend tests
npm run test
```

## Test Commands

| Command | Description |
|---------|-------------|
| `npm run test` | Run all tests (backend + frontend) |
| `npm run test:backend` | Run Python backend tests with coverage |
| `npm run test:frontend` | Run React frontend tests |
| `npm run test:unit` | Run unit tests only |
| `npm run test:integration` | Run integration tests only |
| `npm run test:e2e` | Run end-to-end tests only |
| `npm run test:coverage` | Run tests with detailed coverage report |
| `npm run test:playwright` | Run Playwright E2E tests |
| `npm run test:playwright:ui` | Run Playwright tests with UI |
| `npm run lint` | Run code linting |
| `npm run format` | Format code with Black |
| `npm run pre-commit` | Run linting and backend tests |

## Coverage

The test suite aims for:
- **70% minimum coverage** for backend code
- **Comprehensive API testing** for all endpoints
- **User flow coverage** for critical frontend paths

## Test Data

Test fixtures are defined in `conftest.py`:
- `sample_scan_data`: Sample scan information
- `sample_host_data`: Sample host information
- Database fixtures for isolated testing

## Adding New Tests

### Backend Tests

1. **Unit Tests**: Add to `tests/unit/` directory
2. **Integration Tests**: Add to `tests/integration/` directory
3. **E2E Tests**: Add to `tests/e2e/` directory

### Frontend Tests

1. Add `.spec.js` files to `tests/` directory
2. Use Playwright for browser automation
3. Follow existing naming conventions

## Best Practices

- Use descriptive test names
- Test both success and failure cases
- Mock external dependencies
- Keep tests isolated and independent
- Use fixtures for common test data
- Aim for fast test execution

## CI/CD Integration

Tests are configured to run in CI/CD pipelines:
- Backend tests run with pytest
- Frontend tests run with Playwright
- Coverage reports are generated
- Linting is enforced

## Troubleshooting

### Common Issues

1. **Database conflicts**: Tests use isolated databases via fixtures
2. **Port conflicts**: Tests use different ports than development
3. **File permissions**: Ensure test directories are writable

### Debug Mode

```bash
# Run tests with verbose output
pytest -v -s

# Run specific test file
pytest tests/unit/test_database.py -v

# Run with debugger
pytest --pdb
``` 