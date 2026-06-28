"""Guard: the worker-reachable domain must not import the web stack.

The API and the SQS worker are built as separate, independently deployable
images. The worker image must stay lean — it must never carry FastAPI / slowapi
/ uvicorn / starlette. The two seams that historically dragged the web stack
into the worker were the `core.__init__` re-export barrel and
`core.services.file_validation` (UploadFile); both are now severed.

This test imports the worker's entire reachable surface in a *fresh* subprocess
(the main pytest process already has FastAPI loaded by API tests, so we can't
inspect this process's `sys.modules`) and asserts none of the forbidden
packages got pulled in. It fails the moment someone re-couples them.
"""

import subprocess
import sys

# Modules the SQS worker imports, directly or transitively, at runtime.
_WORKER_SURFACE = [
    "rs_worker.worker",
    "rs_shared.core.tasks",
    "rs_shared.core.matching",
]

# Packages that must never be imported by the worker surface.
_FORBIDDEN = ["fastapi", "slowapi", "uvicorn", "starlette"]


def test_worker_surface_does_not_import_web_stack() -> None:
    forbidden = ", ".join(repr(p) for p in _FORBIDDEN)
    surface = ", ".join(repr(m) for m in _WORKER_SURFACE)
    program = (
        "import importlib, sys\n"
        f"for name in [{surface}]:\n"
        "    importlib.import_module(name)\n"
        f"leaked = sorted(p for p in [{forbidden}]\n"
        "    if any(m == p or m.startswith(p + '.') for m in sys.modules))\n"
        "print(','.join(leaked))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Importing the worker surface failed:\n{result.stderr}"
    )
    leaked = result.stdout.strip()
    assert not leaked, (
        "The worker-reachable domain imported the web stack: "
        f"{leaked}. Keep FastAPI/slowapi out of core/services/worker so the "
        "worker image stays lean (see core/__init__.py and api/uploads.py)."
    )
