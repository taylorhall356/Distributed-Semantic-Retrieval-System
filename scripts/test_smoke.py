from test_helpers import (
    assert_eq,
    dump_compose_ps,
    main_guard,
    request_json,
    wait_for_ready,
)


def main() -> None:
    health = request_json("GET", "/health")
    assert_eq(health["status"], "ok", "public health endpoint")

    wait_for_ready()

    ready = request_json("GET", "/ready")
    assert_eq(ready["status"], "ready", "public readiness endpoint")

    dump_compose_ps()
    print("ALL SMOKE TESTS PASSED", flush=True)


if __name__ == "__main__":
    main_guard(main)
