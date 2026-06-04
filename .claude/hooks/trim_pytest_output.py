import json
import sys

d = json.load(sys.stdin)
out = d.get("output", "")
if "pytest" in d.get("command", "") and len(out) > 3000:
    lines = out.splitlines()
    keywords = ["FAILED", "ERROR", "AssertionError", "short test summary"]
    failures = [line for line in lines if any(x in line for x in keywords)]
    passed = next((line for line in lines if "passed" in line or "failed" in line), "")
    summary = "\n".join(failures[-40:] + ([passed] if passed else []))
    print(f"[trimmed pytest output]\n{summary}")
sys.exit(0)
