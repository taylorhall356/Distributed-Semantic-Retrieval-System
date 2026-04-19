from __future__ import annotations

import json

from test_helpers import (
    assert_eq,
    assert_true,
    auth_headers,
    cleanup_files,
    create_test_files,
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

    pdf_path, txt_path = create_test_files("test_e2e_current_state")
    try:
        username = unique_username("itest_user")
        other_username = unique_username("itest_other")
        password = "strongpass123"

        signup = request_json(
            "POST",
            "/auth/signup",
            body={"username": username, "password": password},
            expected_status=201,
        )
        assert_eq(signup["username"], username, "signup primary user")

        duplicate = request_json(
            "POST",
            "/auth/signup",
            body={"username": username, "password": password},
            expected_status=409,
        )
        assert_eq(duplicate["detail"], "Username already exists", "duplicate signup rejected")

        login = request_json(
            "POST",
            "/auth/login",
            body={"username": username, "password": password},
        )
        assert_eq(login["token_type"], "bearer", "login returns bearer token")
        token = login["access_token"]
        headers = auth_headers(token)

        me = request_json("GET", "/me", headers=headers)
        assert_eq(me["username"], username, "me endpoint returns current user")

        unauthenticated_me = request_json("GET", "/me", expected_status=401)
        assert_eq(unauthenticated_me["detail"], "Not authenticated", "unauthenticated me rejected")

        queue = request_json("POST", "/queue-test", headers=headers, expected_status=202)
        assert_eq(queue["status"], "queued", "queue test returns queued status")

        bad_upload_status, _ = run_curl_upload(txt_path, token, "text/plain")
        assert_eq(bad_upload_status, 400, "non-pdf upload rejected")

        upload_status, upload_body = run_curl_upload(pdf_path, token, "application/pdf")
        assert_eq(upload_status, 202, "pdf upload accepted")
        upload = json.loads(upload_body)
        assert_eq(upload["status"], "processing", "pdf upload starts processing")
        document_id = int(upload["id"])

        document = wait_for_document_status(token, document_id, "ready")
        assert_eq(document["status"], "ready", "document processes to ready")

        documents = request_json("GET", "/documents", headers=headers)
        matching = [doc for doc in documents if int(doc["id"]) == document_id]
        assert_eq(len(matching), 1, "document list returns uploaded document")

        search = request_json(
            "GET",
            "/search?q=playful%20household%20pets&limit=5",
            headers=headers,
        )
        assert_true(len(search) >= 1, "search returns at least one result for owner")
        assert_eq(search[0]["filename"], pdf_path.name, "search returns uploaded filename first")

        request_json(
            "POST",
            "/auth/signup",
            body={"username": other_username, "password": password},
            expected_status=201,
        )
        other_login = request_json(
            "POST",
            "/auth/login",
            body={"username": other_username, "password": password},
        )
        other_headers = auth_headers(other_login["access_token"])
        other_search = request_json(
            "GET",
            "/search?q=playful%20household%20pets&limit=5",
            headers=other_headers,
        )
        assert_eq(len(other_search), 0, "search results are user-scoped")

        retry_ready = request_json(
            "POST",
            f"/documents/{document_id}/retry",
            headers=headers,
            expected_status=409,
        )
        assert_eq(
            retry_ready["detail"],
            "Only failed or stale processing documents can be retried",
            "retry on ready document rejected",
        )

        delete_status = run_curl_delete(document_id, token)
        assert_eq(delete_status, 204, "delete document succeeds")

        documents_after_delete = request_json("GET", "/documents", headers=headers)
        still_present = [doc for doc in documents_after_delete if int(doc["id"]) == document_id]
        assert_eq(len(still_present), 0, "deleted document absent from list")

        search_after_delete = request_json(
            "GET",
            "/search?q=playful%20household%20pets&limit=5",
            headers=headers,
        )
        matching_deleted = [result for result in search_after_delete if int(result["document_id"]) == document_id]
        assert_eq(len(matching_deleted), 0, "deleted document absent from search results")

        second_delete_status = run_curl_delete(document_id, token)
        assert_eq(second_delete_status, 404, "second delete returns not found")

        print("ALL E2E TESTS PASSED", flush=True)
    finally:
        cleanup_files(pdf_path, txt_path)


if __name__ == "__main__":
    main_guard(main)
