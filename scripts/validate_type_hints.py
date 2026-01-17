#!/usr/bin/env python3
"""Validate that functions have return type hints.

This script enforces strict type hints by ensuring:
- All public functions (non-private) have return type hints
- All async functions have return type hints
"""

import ast
import sys
from pathlib import Path


def check_type_hints(file_path: Path) -> list[str]:
    """Check that functions have return type hints.

    Args:
        file_path: Path to Python file to check

    Returns:
        List of violation messages (empty if no violations)
    """
    violations = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip private functions (starting with _)
                if node.name.startswith("_"):
                    continue

                # Skip __init__ methods (they return None implicitly)
                if node.name == "__init__":
                    continue

                # Check if return type annotation exists
                if node.returns is None:
                    func_type = (
                        "async function"
                        if isinstance(node, ast.AsyncFunctionDef)
                        else "function"
                    )
                    violations.append(
                        f"{file_path}:{node.lineno}: "
                        f"{func_type.capitalize()} '{node.name}' "
                        f"missing return type hint"
                    )
    except SyntaxError as e:
        violations.append(f"{file_path}:{e.lineno}: Syntax error: {e.msg}")
    except Exception as e:
        violations.append(f"{file_path}: Error parsing: {e}")

    return violations


def main() -> None:
    """Main validation function."""
    violations = []
    src_path = Path("src")

    if not src_path.exists():
        print(f"❌ Source directory '{src_path}' not found")
        sys.exit(1)

    for py_file in src_path.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue

        file_violations = check_type_hints(py_file)
        violations.extend(file_violations)

    if violations:
        print("❌ Type hint violations detected:")
        print("All public functions must have return type hints.\n")
        for violation in violations:
            print(f"  {violation}")
        sys.exit(1)
    else:
        print("✅ All functions have return type hints")
        sys.exit(0)


if __name__ == "__main__":
    main()
