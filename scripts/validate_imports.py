#!/usr/bin/env python3
"""Validate that the shared domain doesn't import FastAPI or HTTPException.

This script enforces Separation of Concerns by ensuring the shared package
(installed into both the API and the worker images) stays framework-free:
- Service logic in libs/shared/rs_shared/services/ does NOT import fastapi or
  HTTPException
- Core infrastructure in libs/shared/rs_shared/core/ does NOT import fastapi

The FastAPI-coupled modules (dependencies, error_handling, limiter, middleware)
now live in the API service (services/api/rs_api/infrastructure/), so there are
no longer any allowed exceptions here.
"""

import ast
import sys
from pathlib import Path

FORBIDDEN_IMPORTS = {
    "libs/shared/rs_shared/services": ["fastapi", "HTTPException"],
    "libs/shared/rs_shared/core": ["fastapi"],
}

ALLOWED_FILES: set[str] = set()


def check_file(file_path: Path, forbidden: list[str]) -> list[str]:
    """Check a file for forbidden imports.

    Args:
        file_path: Path to Python file to check
        forbidden: List of forbidden import names

    Returns:
        List of violation messages (empty if no violations)
    """
    violations = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(
                        forbidden_name in alias.name for forbidden_name in forbidden
                    ):
                        violations.append(
                            f"{file_path}:{node.lineno}: Import '{alias.name}'"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and any(
                    forbidden_name in node.module for forbidden_name in forbidden
                ):
                    violations.append(
                        f"{file_path}:{node.lineno}: Import from '{node.module}'"
                    )
                # Check for specific imports like "from fastapi import HTTPException"
                if node.module and any(
                    forbidden_name in node.module for forbidden_name in forbidden
                ):
                    for name in node.names or []:
                        violations.append(
                            f"{file_path}:{node.lineno}: Import '{name.name}' "
                            f"from '{node.module}'"
                        )
    except Exception as e:
        violations.append(f"{file_path}: Error parsing: {e}")

    return violations


def main():
    """Main validation function."""
    violations = []

    for directory, forbidden in FORBIDDEN_IMPORTS.items():
        dir_path = Path(directory)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            # Skip __init__.py and allowed files
            if py_file.name == "__init__.py":
                continue

            # Convert to string for comparison (handle both relative and absolute paths)
            file_str = str(py_file).replace("\\", "/")
            if any(allowed in file_str for allowed in ALLOWED_FILES):
                continue

            file_violations = check_file(py_file, forbidden)
            violations.extend(file_violations)

    if violations:
        print("❌ Import violations detected:")
        print(
            "Services and core infrastructure should NOT import FastAPI or "
            "HTTPException."
        )
        print(
            "Use domain exceptions from "
            "libs/shared/rs_shared/services/exceptions.py instead.\n"
        )
        for violation in violations:
            print(f"  {violation}")
        sys.exit(1)
    else:
        print("✅ No import violations detected")
        sys.exit(0)


if __name__ == "__main__":
    main()
