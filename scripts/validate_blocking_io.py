#!/usr/bin/env python3
"""Validate that async functions don't use blocking I/O operations.

This script detects blocking operations in async functions:
- open() instead of aiofiles.open()
- requests.get() instead of httpx.AsyncClient()
- time.sleep() instead of asyncio.sleep()
- session.query() instead of await session.execute()
- Path.write_bytes(), Path.read_bytes(), Path.write_text(), Path.read_text()
- Path.exists(), Path.unlink(), Path.mkdir() (without run_in_executor)
"""

import ast
import sys
from pathlib import Path

# Blocking operations to detect
BLOCKING_IO_PATTERNS = {
    "open": "Use aiofiles.open() instead of open()",
    "requests.get": "Use httpx.AsyncClient() instead of requests.get()",
    "requests.post": "Use httpx.AsyncClient() instead of requests.post()",
    "requests.put": "Use httpx.AsyncClient() instead of requests.put()",
    "requests.delete": "Use httpx.AsyncClient() instead of requests.delete()",
    "time.sleep": "Use asyncio.sleep() instead of time.sleep()",
    "session.query": "Use await session.execute() instead of session.query()",
}

# Blocking Path methods (when not in run_in_executor)
BLOCKING_PATH_METHODS = {
    "write_bytes": "Use aiofiles or run_in_executor() for file writes",
    "read_bytes": "Use aiofiles or run_in_executor() for file reads",
    "write_text": "Use aiofiles or run_in_executor() for file writes",
    "read_text": "Use aiofiles or run_in_executor() for file reads",
    "exists": "Use run_in_executor() for file system checks",
    "unlink": "Use run_in_executor() for file deletion",
    "mkdir": "Use run_in_executor() for directory creation",
}


def is_in_run_in_executor(node: ast.AST, tree: ast.AST) -> bool:
    """Check if a node is inside a run_in_executor call.

    Args:
        node: AST node to check
        tree: Full AST tree

    Returns:
        True if node is inside run_in_executor call
    """
    for parent in ast.walk(tree):
        if isinstance(parent, ast.Call):
            # Check if it's a run_in_executor call
            if isinstance(parent.func, ast.Attribute):
                if parent.func.attr == "run_in_executor":
                    # Check if our node is within this call's arguments
                    for arg in parent.args:
                        if hasattr(arg, "lineno") and hasattr(node, "lineno"):
                            if arg.lineno == node.lineno:
                                return True
    return False


def check_blocking_io(file_path: Path) -> list[str]:
    """Check for blocking I/O operations in async functions.

    Args:
        file_path: Path to Python file to check

    Returns:
        List of violation messages (empty if no violations)
    """
    violations = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content, filename=str(file_path))

        # Track which functions are async
        async_functions = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                async_functions.add(node)

        # Check for blocking operations in async functions
        for node in ast.walk(tree):
            # Check if we're inside an async function
            current_async_func = None
            for async_func in async_functions:
                if hasattr(node, "lineno") and hasattr(async_func, "lineno"):
                    if async_func.lineno <= node.lineno <= async_func.end_lineno:
                        current_async_func = async_func
                        break

            if current_async_func is None:
                continue

            # Check for blocking function calls
            if isinstance(node, ast.Call):
                # Check direct function calls (e.g., open(), time.sleep())
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name in BLOCKING_IO_PATTERNS:
                        violations.append(
                            f"{file_path}:{node.lineno}: Blocking I/O '{func_name}' "
                            f"in async function '{current_async_func.name}'. "
                            f"{BLOCKING_IO_PATTERNS[func_name]}"
                        )

                # Check attribute calls (e.g., requests.get(), session.query())
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        full_name = f"{node.func.value.id}.{node.func.attr}"
                        if full_name in BLOCKING_IO_PATTERNS:
                            violations.append(
                                f"{file_path}:{node.lineno}: "
                                f"Blocking I/O '{full_name}' in async function "
                                f"'{current_async_func.name}'. "
                                f"{BLOCKING_IO_PATTERNS[full_name]}"
                            )

                    # Check Path methods (e.g., path.write_bytes())
                    if node.func.attr in BLOCKING_PATH_METHODS:
                        # Check if it's inside run_in_executor
                        # Simple heuristic: check if parent is a Call with
                        # run_in_executor
                        # This is a simplified check - may have false
                        # positives/negatives but catches most common cases
                        parent_call = None
                        for parent in ast.walk(tree):
                            if isinstance(parent, ast.Call):
                                if isinstance(parent.func, ast.Attribute):
                                    if parent.func.attr == "run_in_executor":
                                        # Check if node is in parent's args
                                        for arg in parent.args:
                                            if (
                                                isinstance(arg, ast.Call)
                                                and arg.lineno == node.lineno
                                            ):
                                                parent_call = parent
                                                break

                        if parent_call is None:
                            violations.append(
                                f"{file_path}:{node.lineno}: Blocking I/O "
                                f"'Path.{node.func.attr}()' in async function "
                                f"'{current_async_func.name}'. "
                                f"{BLOCKING_PATH_METHODS[node.func.attr]}"
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

        file_violations = check_blocking_io(py_file)
        violations.extend(file_violations)

    if violations:
        print("❌ Blocking I/O violations detected in async functions:")
        print("Async functions must use async I/O operations or run_in_executor().\n")
        for violation in violations:
            print(f"  {violation}")
        sys.exit(1)
    else:
        print("✅ No blocking I/O operations found in async functions")
        sys.exit(0)


if __name__ == "__main__":
    main()
