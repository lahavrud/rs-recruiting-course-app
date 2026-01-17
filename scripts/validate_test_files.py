#!/usr/bin/env python3
"""Validate that source files have corresponding test files.

This script ensures test coverage by checking:
- src/services/X.py → tests/services/test_X.py must exist
- src/api/X.py → tests/api/test_X.py must exist
- src/core/infrastructure/X.py → tests/core/infrastructure/test_X.py must exist
"""

import sys
from pathlib import Path

# Mapping of source directories to test directories
SOURCE_TO_TEST_MAPPING = {
    "src/services": "tests/services",
    "src/api": "tests/api",
    "src/core/infrastructure": "tests/core/infrastructure",
}

# Files that don't require tests (exceptions, simple factories, etc.)
# TODO: Add tests for database.py, security.py, and config.py
EXCLUDED_FILES = {
    "src/services/exceptions.py",  # Exception classes tested indirectly
    "src/core/infrastructure/limiter.py",  # Simple factory function
    "src/core/infrastructure/database.py",  # TODO: Add tests for init_db
    "src/core/infrastructure/security.py",  # TODO: Add tests for password/JWT
    "src/core/infrastructure/config.py",  # TODO: Add tests for config validators
}


def get_expected_test_file(source_file: Path) -> Path | None:
    """Get the expected test file path for a source file.

    Args:
        source_file: Path to source file

    Returns:
        Expected test file path, or None if not in a mapped directory
    """
    source_str = str(source_file)

    for source_dir, test_dir in SOURCE_TO_TEST_MAPPING.items():
        if source_str.startswith(source_dir):
            # Get relative path from source directory
            relative_path = source_file.relative_to(source_dir)

            # Convert to test file path
            # e.g., src/services/auth.py -> tests/services/test_auth.py
            test_file_name = f"test_{relative_path.name}"
            test_file_path = Path(test_dir) / test_file_name

            return test_file_path

    return None


def check_test_files() -> list[str]:
    """Check that source files have corresponding test files.

    Returns:
        List of violation messages (empty if no violations)
    """
    violations = []
    src_path = Path("src")

    if not src_path.exists():
        return [f"❌ Source directory '{src_path}' not found"]

    for source_dir in SOURCE_TO_TEST_MAPPING.keys():
        dir_path = Path(source_dir)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            # Skip __init__.py files
            if py_file.name == "__init__.py":
                continue

            # Skip excluded files
            file_str = str(py_file).replace("\\", "/")
            if file_str in EXCLUDED_FILES:
                continue

            expected_test = get_expected_test_file(py_file)
            if expected_test is None:
                continue

            if not expected_test.exists():
                violations.append(f"{py_file}: Missing test file '{expected_test}'")

    return violations


def main() -> None:
    """Main validation function."""
    violations = check_test_files()

    if violations:
        print("❌ Missing test files detected:")
        print("Source files must have corresponding test files.\n")
        for violation in violations:
            print(f"  {violation}")
        sys.exit(1)
    else:
        print("✅ All source files have corresponding test files")
        sys.exit(0)


if __name__ == "__main__":
    main()
