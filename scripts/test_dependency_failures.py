from __future__ import annotations

import time

from test_helpers import (
    assert_eq,
    assert_true,
    docker,
    main_guard,
    request_json,
    request_status,
    unique_username,
    wait_for_ready,
)


EMBEDDING_CONTAINER = "semantic-retrieval-embedding-service"


def main() -> None:
    wait_for_ready()

    username = unique_username("itest_dep")
    password = "strongpass123"

    request_json(
        "POST",
        "/auth/signup",
        body={"username": username, "password": password},
        expected_status=201,
    )
    login = request_json(
        "POST",
        "/auth/login",
        body={"username": username, "password": password},
    )
    token = login["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    try:
        docker(["stop", EMBEDDING_CONTAINER])
        time.sleep(3)

        health = request_json("GET", "/health")
        assert_eq(health["status"], "ok", "public health remains up when embedding service is down")

        deadline = time.time() + 30
        ready_status = 200
        while time.time() < deadline:
            ready_status = request_status("GET", "/ready")
            if ready_status != 200:
                break
            time.sleep(2)
        assert_true(ready_status in {502, 503}, "public readiness fails when embedding service is down")

        search = request_json(
            "GET",
            "/search?q=playful%20household%20pets&limit=5",
            headers=headers,
            expected_status=503,
        )
        assert_eq(search["detail"], "Embedding service request failed", "search surfaces embedding dependency failure")
    finally:
        restart = docker(["compose", "up", "-d", "embedding-service"], check=False)
        if restart.returncode != 0:
            raise RuntimeError(
                f"Failed to restart embedding service: {restart.stderr.strip() or restart.stdout.strip()}"
            )

    wait_for_ready()
    ready = request_json("GET", "/ready")
    assert_eq(ready["status"], "ready", "system returns to ready after embedding service recovery")

    print("ALL DEPENDENCY FAILURE TESTS PASSED", flush=True)


if __name__ == "__main__":
    main_guard(main)
