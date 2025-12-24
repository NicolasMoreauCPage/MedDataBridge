# TEST_DOCUMENTATION.md
# Test Documentation - MedBridge Application

*Generated on: $(date)*

## Overview

This document provides information about the test suite structure and execution guidelines for the MedBridge application.

## Test Categories

### Available Markers

- `unit`: Fast unit tests with mocked dependencies
- `integration`: Integration tests testing real component interactions
- `ui`: User interface tests requiring browser/playwright
- `api`: API endpoint tests
- `security`: Security-related tests (auth, validation, injection)
- `performance`: Performance and load tests
- `slow`: Tests taking longer than 30 seconds
- `critical`: Critical functionality that must always work
- `flaky`: Tests that may fail intermittently (needs investigation)
- `coverage`: Tests related to coverage measurement
- `mutation`: Mutation testing for test quality validation
- `property`: Property-based tests using hypothesis for edge case validation

### Test Directory Structure

```
tests/
├── unit/              # Unit tests (fast, isolated)
├── integration/       # Integration tests
├── api/              # API endpoint tests
├── security/         # Security tests
├── performance/      # Performance tests
├── ui/               # UI tests
├── property/         # Property-based tests (Hypothesis)
├── mutation/         # Mutation tests
├── conftest.py       # Shared fixtures and configuration
└── pytest.ini       # Pytest configuration
```

## Test Execution Guidelines

### Running Tests by Category

```bash
# Run all tests
pytest

# Run specific categories
pytest -m unit              # Fast unit tests only
pytest -m "integration or api"  # Multiple categories
pytest -m "not slow"        # Exclude slow tests

# Run with parallel execution
pytest -n auto             # Use all available CPU cores
pytest -n 4                # Use 4 parallel workers

# Run with coverage
pytest --cov=app --cov-report=html
```

### CI/CD Integration

```bash
# Quick validation (unit tests only)
pytest -m unit -x --tb=short

# Full test suite with coverage
pytest --cov=app --cov-report=xml --junitxml=results.xml

# Performance and integration tests
pytest -m "performance or integration" --durations=10
```

## Recent Improvements (Phase 6)

### Infrastructure Enhancements

- ✅ Enhanced pytest configuration with comprehensive markers
- ✅ Fixed namespaces router JSON parsing error
- ✅ Added test categorization markers to existing tests
- ✅ Improved test isolation with database cleanup fixtures
- ✅ Fixed TestMetrics class naming conflict
- ✅ Added property-based testing framework (Hypothesis)
- ✅ Parallel test execution support (pytest-xdist)

### Test Reliability Features

- **Automatic Database Cleanup**: `isolated_session` and `clean_db_tables` fixtures
- **Comprehensive Markers**: 12 different test categories for selective execution
- **Property-Based Testing**: Edge case validation using Hypothesis
- **Parallel Execution**: Multi-core test running for faster CI/CD
- **Error Handling**: Improved JSON parsing and validation error handling

## Maintenance Guidelines

### Adding New Tests

1. Choose appropriate category directory (`tests/unit/`, `tests/api/`, etc.)
2. Use descriptive test names following `test_*` convention
3. Add proper markers (`@pytest.mark.category`)
4. Include docstrings explaining test purpose
5. Use fixtures from `conftest.py` for consistency

### Test Isolation

- Each test should be independent
- Use `isolated_session` fixture for database tests
- Clean up resources in test teardown
- Avoid shared state between tests

### Performance Considerations

- Unit tests should run in <100ms each
- Mark slow tests with `@pytest.mark.slow`
- Use parallel execution for CI/CD: `pytest -n auto`
- Profile tests with `--durations=10`

## Troubleshooting

### Common Issues

1. **Database isolation**: Use `isolated_session` fixture
2. **Async tests**: Mark with `@pytest.mark.asyncio`
3. **Slow tests**: Add `@pytest.mark.slow` marker
4. **Flaky tests**: Investigate and fix root cause

### Debugging Commands

```bash
# Verbose output
pytest -v -s

# Stop on first failure
pytest -x

# Show test durations
pytest --durations=10

# Debug specific test
pytest tests/specific_test.py::TestClass::test_method -v -s
```

---

*This documentation is maintained manually. For automatic generation, run: `python scripts/generate_test_docs.py`*