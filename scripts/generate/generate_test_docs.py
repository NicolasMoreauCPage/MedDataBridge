#!/usr/bin/env python3
# scripts/generate_test_docs.py
"""
Generate comprehensive test documentation from pytest markers and test structure
Creates markdown documentation for test organization and maintenance
"""

import os
import subprocess
import json
from pathlib import Path
from collections import defaultdict


def run_pytest_collect():
    """Collect test information using pytest --collect-only"""
    try:
        result = subprocess.run([
            'python', '-m', 'pytest', '--collect-only', '-q', '--tb=no', 'tests/'
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        return result.stdout, result.stderr
    except Exception as e:
        print(f"Error running pytest: {e}")
        return "", str(e)


def parse_test_collection(output):
    """Parse pytest collection output to extract test information"""
    tests_by_marker = defaultdict(list)
    tests_by_file = defaultdict(list)

    lines = output.split('\n')
    current_file = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect test file
        if line.startswith('tests/') and '.py::' not in line:
            current_file = line
            continue

        # Detect test function/class
        if '::' in line and ('test_' in line or 'Test' in line) and current_file:
            test_path = line
            if current_file:
                tests_by_file[current_file].append(test_path)

            # Try to infer markers from file path
            if current_file and '/unit/' in current_file:
                tests_by_marker['unit'].append(test_path)
            elif current_file and '/integration/' in current_file:
                tests_by_marker['integration'].append(test_path)
            elif current_file and '/api/' in current_file:
                tests_by_marker['api'].append(test_path)
            elif current_file and '/security/' in current_file:
                tests_by_marker['security'].append(test_path)
            elif current_file and '/performance/' in current_file:
                tests_by_marker['performance'].append(test_path)
            elif current_file and '/ui/' in current_file:
                tests_by_marker['ui'].append(test_path)
            elif current_file and '/property/' in current_file:
                tests_by_marker['property'].append(test_path)
            elif current_file and '/mutation/' in current_file:
                tests_by_marker['mutation'].append(test_path)

    return dict(tests_by_marker), dict(tests_by_file)


def generate_markdown_docs(tests_by_marker, tests_by_file):
    """Generate comprehensive markdown documentation"""

    doc_content = f"""# Test Documentation - MedBridge Application

*Generated on: {subprocess.run(['date'], capture_output=True, text=True).stdout.strip()}*

## Overview

This document provides comprehensive information about the test suite structure, organization, and execution guidelines for the MedBridge application.

### Test Statistics

- **Total Test Files**: {len(tests_by_file)}
- **Total Test Categories**: {len(tests_by_marker)}
- **Total Tests**: {sum(len(tests) for tests in tests_by_marker.values())}

## Test Categories

### Unit Tests (`pytest -m unit`)
Fast, isolated tests focusing on individual functions and classes with mocked dependencies.

**Files**: {len(tests_by_marker.get('unit', []))}
**Tests**: {len(tests_by_marker.get('unit', []))}

### Integration Tests (`pytest -m integration`)
Tests that verify interactions between multiple components.

**Files**: {len(tests_by_marker.get('integration', []))}
**Tests**: {len(tests_by_marker.get('integration', []))}

### API Tests (`pytest -m api`)
Tests for REST API endpoints and HTTP interactions.

**Files**: {len(tests_by_marker.get('api', []))}
**Tests**: {len(tests_by_marker.get('api', []))}

### Security Tests (`pytest -m security`)
Tests for authentication, authorization, input validation, and security vulnerabilities.

**Files**: {len(tests_by_marker.get('security', []))}
**Tests**: {len(tests_by_marker.get('security', []))}

### Performance Tests (`pytest -m performance`)
Load testing and performance validation tests.

**Files**: {len(tests_by_marker.get('performance', []))}
**Tests**: {len(tests_by_marker.get('performance', []))}

### UI Tests (`pytest -m ui`)
User interface tests using Playwright/browser automation.

**Files**: {len(tests_by_marker.get('ui', []))}
**Tests**: {len(tests_by_marker.get('ui', []))}

### Property-Based Tests (`pytest -m property`)
Advanced tests using Hypothesis to test properties and edge cases.

**Files**: {len(tests_by_marker.get('property', []))}
**Tests**: {len(tests_by_marker.get('property', []))}

### Mutation Tests (`pytest -m mutation`)
Tests that verify test quality by introducing code mutations.

**Files**: {len(tests_by_marker.get('mutation', []))}
**Tests**: {len(tests_by_marker.get('mutation', []))}

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

## Test File Structure

### Directory Organization

```
tests/
├── unit/              # Unit tests (fast, isolated)
├── integration/       # Integration tests
├── api/              # API endpoint tests
├── security/         # Security tests
├── performance/      # Performance tests
├── ui/               # UI tests
├── property/         # Property-based tests
├── mutation/         # Mutation tests
├── conftest.py       # Shared fixtures and configuration
└── pytest.ini       # Pytest configuration
```

### Test Naming Conventions

- **Files**: `test_*.py`
- **Functions**: `test_*`
- **Classes**: `Test*`
- **Fixtures**: Use descriptive names in `conftest.py`

## Maintenance Guidelines

### Adding New Tests

1. Choose appropriate category directory
2. Use descriptive test names
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
- Use parallel execution for CI/CD
- Profile tests with `--durations=10`

## Troubleshooting

### Common Issues

1. **Database isolation**: Use `isolated_session` fixture
2. **Async tests**: Mark with `@pytest.mark.asyncio`
3. **Slow tests**: Add `@pytest.mark.slow` marker
4. **Flaky tests**: Investigate and fix root cause

### Debugging

```bash
# Verbose output
pytest -v -s

# Stop on first failure
pytest -x

# Show durations
pytest --durations=10

# Debug specific test
pytest tests/specific_test.py::TestClass::test_method -v -s
```

---

*This documentation is automatically generated. Last updated: {subprocess.run(['date'], capture_output=True, text=True).stdout.strip()}*
"""

    return doc_content


def main():
    """Main function to generate test documentation"""
    print("Generating test documentation...")

    # Collect test information
    stdout, stderr = run_pytest_collect()

    if stderr:
        print(f"Warning: {stderr}")

    # Parse test structure
    tests_by_marker, tests_by_file = parse_test_collection(stdout)

    # Generate documentation
    docs = generate_markdown_docs(tests_by_marker, tests_by_file)

    # Write to file
    docs_path = Path(__file__).parent.parent / "TEST_DOCUMENTATION.md"
    docs_path.write_text(docs, encoding='utf-8')

    print(f"Test documentation generated: {docs_path}")
    print(f"Found {len(tests_by_file)} test files with {sum(len(tests) for tests in tests_by_marker.values())} total tests")


if __name__ == "__main__":
    main()