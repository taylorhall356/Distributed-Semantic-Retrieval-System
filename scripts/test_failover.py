from __future__ import annotations

import time

from test_helpers import (
    assert_eq,
    assert_true,
    docker,
    docker_compose,
    main_guard,
    request_json,
    run_curl_headers,
    wait_for_ready,
)


API3_CONTAINER = "semantic-retrieval-api-3"


def collect_upstreams(samples: int = 60) -> set[str]:
    upstreams: set[str] = set()
    successful_samples = 0
    for _ in range(samples):
        try:
            status, headers = run_curl_headers("/health", timeout_seconds=8)
        except Exception:
            time.sleep(0.5)
            continue
        assert_eq(status, 200, "health request through nginx")
        successful_samples += 1
        upstream = headers.get("x-upstream", "")
        if upstream:
            for part in upstream.split(","):
                cleaned = part.strip()
                if cleaned:
                    upstreams.add(cleaned)
        time.sleep(0.2)
    assert_true(successful_samples >= max(3, samples // 2), "sufficient successful nginx samples collected")
    return upstreams


def main() -> None:
    wait_for_ready()

    initial_upstreams = collect_upstreams()
    assert_true(len(initial_upstreams) >= 3, "nginx routes across three API upstreams")

    try:
        docker(["stop", API3_CONTAINER])
        time.sleep(3)

        surviving_upstreams = collect_upstreams(samples=10)
        assert_true(len(surviving_upstreams) >= 1, "requests still succeed with one API replica down")
        assert_true(
            all("172.21." in upstream for upstream in surviving_upstreams),
            "responses still come from live upstream addresses",
        )
    finally:
        docker_compose_result = docker_compose(["up", "-d", "api3"], check=False)
        if docker_compose_result.returncode != 0:
            raise RuntimeError(
                f"Failed to restart api3: {docker_compose_result.stderr.strip() or docker_compose_result.stdout.strip()}"
            )

    wait_for_ready()
    recovered = request_json("GET", "/ready")
    assert_eq(recovered["status"], "ready", "system recovers to ready after api3 restart")

    restored_upstreams = collect_upstreams()
    assert_true(len(restored_upstreams) >= 3, "three upstreams return after api3 restart")

    print("ALL FAILOVER TESTS PASSED", flush=True)


if __name__ == "__main__":
    main_guard(main)
