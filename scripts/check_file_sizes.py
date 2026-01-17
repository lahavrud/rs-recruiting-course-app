#!/usr/bin/env python3
"""Check file sizes against guidelines.

This script enforces file size limits to prevent "fat" files:
- API routers: < 200 lines
- Services: < 300 lines
- Core: < 300 lines
"""

import sys
from pathlib import Path

MAX_LINES = {
    "src/api": 200,
    "src/services": 300,
    "src/core": 300,
}


def count_lines(file_path: Path) -> int:
    """Count non-empty lines in a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def check_file_sizes():
    """Check file sizes against limits."""
    violations = []
    warnings = []

    for directory, max_lines in MAX_LINES.items():
        dir_path = Path(directory)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue

            line_count = count_lines(py_file)

            # Violation if exceeds limit
            if line_count > max_lines:
                violations.append(f"{py_file}: {line_count} lines (limit: {max_lines})")
            # Warning if within 10% of limit
            elif line_count > max_lines * 0.9:
                warnings.append(
                    f"{py_file}: {line_count} lines (approaching limit: {max_lines})"
                )

    if violations:
        print("❌ File size violations detected:")
        for violation in violations:
            print(f"  {violation}")
        print("\nConsider splitting large files into smaller modules.")
        sys.exit(1)

    if warnings:
        print("⚠️  Files approaching size limits:")
        for warning in warnings:
            print(f"  {warning}")
        print("\nConsider refactoring before these files grow further.")
        sys.exit(0)

    print("✅ All files within size limits")
    sys.exit(0)


if __name__ == "__main__":
    check_file_sizes()
