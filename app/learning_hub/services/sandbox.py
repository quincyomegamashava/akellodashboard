"""Code execution sandbox: Judge0 API or restricted local Python subprocess."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from flask import current_app


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int


def _normalize_out(s: str) -> str:
    return "\n".join(line.rstrip() for line in (s or "").replace("\r\n", "\n").strip().split("\n")).strip()


def run_python_locally(code: str, stdin: str, timeout_sec: float = 5.0) -> RunResult:
    """
    Runs submitted Python in a subprocess with wall-clock timeout.

    WARNING: Not a strong isolation boundary — configure Judge0 / Docker for production.
    """
    fd, path = tempfile.mkstemp(suffix=".py", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        proc = subprocess.run(
            [sys.executable, path],
            input=stdin.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_sec,
            cwd=tempfile.gettempdir(),
        )
        return RunResult(
            stdout=proc.stdout.decode("utf-8", errors="replace"),
            stderr=proc.stderr.decode("utf-8", errors="replace"),
            exit_code=int(proc.returncode),
        )
    except subprocess.TimeoutExpired:
        return RunResult(stdout="", stderr="Timeout: code took too long.", exit_code=-1)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def judge0_submit_and_poll(source_code: str, stdin: str, language_id: int) -> RunResult:
    base = current_app.config.get("JUDGE0_API_URL") or ""
    token = current_app.config.get("JUDGE0_API_TOKEN") or ""
    if not base:
        raise RuntimeError("Judge0 URL not configured")

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload: Dict[str, Any] = {
        "source_code": source_code,
        "language_id": language_id,
        "stdin": stdin,
        "cpu_time_limit": "2",
        "memory_limit": 128000,
    }

    sub_url = f"{base}/submissions?base64_encoded=false&wait=false"
    r = requests.post(sub_url, json=payload, headers=headers, timeout=15)
    r.raise_for_status()
    token_resp = r.json().get("token")
    if not token_resp:
        raise RuntimeError(f"Judge0 bad response: {r.text[:300]}")

    import time

    result_url = f"{base}/submissions/{token_resp}?base64_encoded=false"
    for _ in range(40):
        rr = requests.get(result_url, headers=headers, timeout=10)
        rr.raise_for_status()
        data = rr.json()
        if data.get("status", {}).get("id") not in (1, 2):  # not In Queue / Processing
            stdout = data.get("stdout") or ""
            stderr = (data.get("stderr") or "") + (data.get("message") or "")
            exit_code = int(data.get("exit_code") or data.get("exit_signal") or 0)
            return RunResult(stdout=stdout, stderr=stderr, exit_code=exit_code)
        time.sleep(0.25)

    return RunResult(stdout="", stderr="Judge0 polling timeout", exit_code=-1)


def run_python_challenge(code: str, stdin: str) -> RunResult:
    """Prefer Judge0 when configured; otherwise local subprocess."""
    try:
        if current_app.config.get("JUDGE0_API_URL"):
            lid = int(current_app.config.get("JUDGE0_LANGUAGE_PYTHON_ID", 71))
            return judge0_submit_and_poll(code, stdin, lid)
    except Exception as exc:
        return RunResult(stdout="", stderr=f"Judge0 error, falling back: {exc}", exit_code=-1)

    return run_python_locally(code, stdin)


def sample_tests_for_challenge(content_json: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Tests used for the learner-facing "Run sample" action (no DB write, no XP).

    Uses ``public_tests`` when present; otherwise the first entry of ``tests``.
    """
    c = content_json or {}
    pub = c.get("public_tests")
    if isinstance(pub, list) and pub:
        return [t for t in pub if isinstance(t, dict)]
    all_t = c.get("tests") or []
    if isinstance(all_t, list) and all_t and isinstance(all_t[0], dict):
        return [all_t[0]]
    return []


def grade_python_tests(code: str, tests: List[Dict[str, Any]]) -> tuple[float, float, Dict[str, Any]]:
    """Each test: {stdin, expected_stdout}. Score is count passed."""
    passed = 0
    total = len(tests)
    details: List[Dict[str, Any]] = []

    if total == 0:
        return 0.0, 0.0, {"tests": []}

    for i, t in enumerate(tests):
        stdin = str(t.get("stdin", ""))
        expected = _normalize_out(str(t.get("expected_stdout", "")))
        res = run_python_challenge(code, stdin)
        got = _normalize_out(res.stdout)
        ok = res.exit_code == 0 and got == expected
        if ok:
            passed += 1
        details.append(
            {
                "index": i,
                "passed": ok,
                "exit_code": res.exit_code,
                "stdout": got[:500],
                "expected": expected[:500],
                "stderr_tail": (res.stderr or "")[-400:],
            }
        )

    score = float(passed)
    max_score = float(total)
    return score, max_score, {"tests": details}
