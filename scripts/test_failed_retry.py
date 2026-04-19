from __future__ import annotations

import json

from test_helpers import (
    assert_eq,
    assert_true,
    auth_headers,
    cleanup_files,
    create_failure_pdf,
    main_guard,
    request_json,
    run_curl_delete,
    run_curl_upload,
    unique_username,
    wait_for_document_status,
    wait_for_ready,
)


def main() -> None:
    wait_for_ready()

    pdf_path = create_failure_pdf("test_failed_retry_state")
    try:
        username = unique_username("itest_fail")
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
        headers = auth_headers(token)

        upload_status, upload_body = run_curl_upload(pdf_path, token, "application/pdf")
        assert_eq(upload_status, 202, "malformed pdf upload accepted for processing")
        upload = json.loads(upload_body)
        assert_eq(upload["status"], "processing", "malformed pdf starts processing")
        document_id = int(upload["id"])

        failed_document = wait_for_document_status(token, document_id, "failed")
        assert_eq(failed_document["status"], "failed", "malformed pdf reaches failed state")
        assert_true(
            bool(failed_document.get("error_message")),
            "failed document records an error message",
        )
        first_error = str(failed_document["error_message"])

        retry = request_json(
            "POST",
            f"/documents/{document_id}/retry",
            headers=headers,
            expected_status=202,
        )
        assert_eq(retry["status"], "processing", "retry resets failed document to processing")
        assert_eq(retry["error_message"], None, "retry clears previous error message")

        failed_again = wait_for_document_status(token, document_id, "failed")
        assert_eq(failed_again["status"], "failed", "retried malformed pdf fails again")
        assert_true(
            bool(failed_again.get("error_message")),
            "retried malformed pdf records an error message again",
        )
        second_error = str(failed_again["error_message"])
        assert_true(
            len(second_error) > 0 and second_error != "None",
            "retry failure returns a usable error message",
        )

        delete_status = run_curl_delete(document_id, token)
        assert_eq(delete_status, 204, "failed document can be deleted")

        print("ALL FAILED-RETRY TESTS PASSED", flush=True)
    finally:
        cleanup_files(pdf_path)


if __name__ == "__main__":
    main_guard(main)
