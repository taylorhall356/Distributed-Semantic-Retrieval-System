from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


BASE_URL = "http://127.0.0.1:8080"
ROOT_DIR = Path(__file__).resolve().parents[1]


class TestFailure(RuntimeError):
    pass


def log(message: str) -> None:
    print(message, flush=True)


def assert_eq(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise TestFailure(f"FAIL: {label} (expected={expected!r} actual={actual!r})")
    log(f"PASS: {label}")


def assert_true(condition: bool, label: str) -> None:
    if not condition:
        raise TestFailure(f"FAIL: {label}")
    log(f"PASS: {label}")


def request_json(
    method: str,
    path: str,
    *,
    body: dict | list | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 15,
    expected_status: int = 200,
) -> dict | list:
    payload = None
    req_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url=f"{BASE_URL}{path}",
        data=payload,
        headers=req_headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
        if status != expected_status:
            raise TestFailure(
                f"Unexpected HTTP status for {method} {path}: expected {expected_status}, got {status}, body={raw}"
            ) from exc
        return json.loads(raw) if raw else {}
    except urllib.error.URLError as exc:
        raise TestFailure(f"Request failed for {method} {path}: {exc}") from exc

    if status != expected_status:
        raise TestFailure(
            f"Unexpected HTTP status for {method} {path}: expected {expected_status}, got {status}, body={raw}"
        )

    return json.loads(raw) if raw else {}


def request_status(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 15,
) -> int:
    req = urllib.request.Request(
        url=f"{BASE_URL}{path}",
        headers=headers or {},
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except urllib.error.URLError as exc:
        raise TestFailure(f"Request failed for {method} {path}: {exc}") from exc


def run_curl_upload(file_path: Path, token: str, content_type: str) -> tuple[int, str]:
    result = subprocess.run(
        [
            "curl.exe",
            "-s",
            "-o",
            "-",
            "-w",
            "\n%{http_code}",
            "-X",
            "POST",
            f"{BASE_URL}/documents",
            "-H",
            f"Authorization: Bearer {token}",
            "-F",
            f"file=@{file_path};type={content_type}",
        ],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise TestFailure(f"curl upload failed: {result.stderr.strip()}")

    output = result.stdout.strip()
    body, status = output.rsplit("\n", 1)
    return int(status), body


def run_curl_delete(document_id: int, token: str) -> int:
    result = subprocess.run(
        [
            "curl.exe",
            "-s",
            "-o",
            "NUL",
            "-w",
            "%{http_code}",
            "-X",
            "DELETE",
            f"{BASE_URL}/documents/{document_id}",
            "-H",
            f"Authorization: Bearer {token}",
        ],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise TestFailure(f"curl delete failed: {result.stderr.strip()}")
    return int(result.stdout.strip())


def run_curl_headers(path: str, *, timeout_seconds: int = 5) -> tuple[int, dict[str, str]]:
    result = subprocess.run(
        [
            "curl.exe",
            "--max-time",
            str(timeout_seconds),
            "-s",
            "-D",
            "-",
            f"{BASE_URL}{path}",
            "-o",
            "NUL",
        ],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise TestFailure(f"curl header request failed: {result.stderr.strip()}")

    status_code = 0
    headers: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if line.startswith("HTTP/"):
            parts = line.split()
            if len(parts) >= 2:
                status_code = int(parts[1])
        elif ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return status_code, headers


def wait_for_ready(timeout_seconds: int = 120) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = request_status("GET", "/ready")
        if status == 200:
            log("PASS: public readiness endpoint reached ready state")
            return
        time.sleep(2)
    raise TestFailure("Timed out waiting for /ready to return 200")


def wait_for_document_status(token: str, document_id: int, expected_status: str, timeout_seconds: int = 120) -> dict:
    deadline = time.time() + timeout_seconds
    headers = {"Authorization": f"Bearer {token}"}
    while time.time() < deadline:
        documents = request_json("GET", "/documents", headers=headers)
        assert isinstance(documents, list)
        document = next((doc for doc in documents if int(doc["id"]) == document_id), None)
        if document is None:
            raise TestFailure(f"Document {document_id} not found while polling")
        log(f"INFO: document {document_id} status={document['status']}")
        if document["status"] == expected_status:
            return document
        time.sleep(5)
    raise TestFailure(f"Timed out waiting for document {document_id} to reach {expected_status}")


def create_test_files(prefix: str) -> tuple[Path, Path]:
    pdf_path = ROOT_DIR / f"{prefix}.pdf"
    txt_path = ROOT_DIR / f"{prefix}.txt"
    pdf_path.write_text(
        """%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 245 >>
stream
BT
/F1 16 Tf
72 720 Td
(Cats are playful household pets and love chasing toys.) Tj
0 -28 Td
(Dogs enjoy long walks, fetch, and outdoor exercise.) Tj
0 -28 Td
(Software architecture concerns services, APIs, scalability, and reliability.) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000063 00000 n 
0000000122 00000 n 
0000000248 00000 n 
0000000545 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
615
%%EOF
""",
        encoding="ascii",
    )
    txt_path.write_text("not a pdf", encoding="ascii")
    return pdf_path, txt_path


def create_failure_pdf(prefix: str) -> Path:
    pdf_path = ROOT_DIR / f"{prefix}.pdf"
    pdf_path.write_text(
        """%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [] /Count 0 >>
endobj
xref
0 3
0000000000 65535 f 
0000000010 00000 n 
0000000063 00000 n 
trailer
<< /Root 1 0 R /Size 3 >>
startxref
114
%%EOF
""",
        encoding="ascii",
    )
    return pdf_path


def cleanup_files(*paths: Path) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def unique_username(prefix: str) -> str:
    return f"{prefix}_{int(time.time())}"


def dump_compose_ps() -> None:
    result = subprocess.run(
        ["docker", "compose", "ps"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        log("INFO: docker compose ps")
        log(result.stdout.strip())
    else:
        log(f"INFO: unable to run docker compose ps: {result.stderr.strip()}")


def docker_compose(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["docker", "compose", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise TestFailure(
            f"docker compose {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def docker(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["docker", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise TestFailure(
            f"docker {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def main_guard(fn) -> None:
    try:
        fn()
    except TestFailure as exc:
        print(str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
