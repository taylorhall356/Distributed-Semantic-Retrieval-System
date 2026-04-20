from __future__ import annotations

import io
import time
import uuid

from locust import HttpUser, between, tag, task


PASSWORD = "strongpass123"
SEARCH_QUERY = "software architecture scalability reliability"
STARTUP_POLL_TIMEOUT_SECONDS = 120
STARTUP_POLL_INTERVAL_SECONDS = 3
WARM_USER_WAIT_INTERVAL_SECONDS = 1

_WARM_USER_HEADERS: dict[str, str] | None = None
_WARM_USER_PREPARING = False
_WARM_USER_ERROR: str | None = None


def build_pdf_bytes() -> bytes:
    return b"""%PDF-1.4
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
<< /Length 257 >>
stream
BT
/F1 16 Tf
72 720 Td
(Software architecture affects scalability reliability observability deployment behavior and query performance across distributed retrieval systems under sustained production traffic.) Tj
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
0000000557 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
627
%%EOF
"""


def login_and_get_headers(client, username: str, password: str) -> dict[str, str]:
    payload = {"username": username, "password": password}
    with client.post(
        "/auth/login",
        json=payload,
        name="/auth/login",
        catch_response=True,
    ) as response:
        if response.status_code != 200:
            response.failure(f"login failed: {response.status_code} {response.text}")
            raise RuntimeError(f"login failed with status {response.status_code}")

        token = response.json().get("access_token")
        if not token:
            response.failure("login did not return access_token")
            raise RuntimeError("login did not return access_token")

        return {"Authorization": f"Bearer {token}"}


def wait_for_document_ready(client, headers: dict[str, str], document_id: int) -> None:
    deadline = time.time() + STARTUP_POLL_TIMEOUT_SECONDS
    while time.time() < deadline:
        docs = client.get(
            "/documents",
            headers=headers,
            name="/documents [startup poll]",
        )
        if docs.status_code != 200:
            time.sleep(STARTUP_POLL_INTERVAL_SECONDS)
            continue

        document = next(
            (doc for doc in docs.json() if int(doc["id"]) == int(document_id)),
            None,
        )
        if document and document.get("status") == "ready":
            return
        if document and document.get("status") == "failed":
            raise RuntimeError(
                f"seed document failed to process: {document.get('error_message')}"
            )

        time.sleep(STARTUP_POLL_INTERVAL_SECONDS)

    raise RuntimeError("timed out waiting for seed document to become ready")


def prepare_warm_user(client) -> dict[str, str]:
    global _WARM_USER_HEADERS, _WARM_USER_PREPARING, _WARM_USER_ERROR

    if _WARM_USER_HEADERS is not None:
        return _WARM_USER_HEADERS

    if _WARM_USER_ERROR is not None:
        raise RuntimeError(_WARM_USER_ERROR)

    if not _WARM_USER_PREPARING:
        _WARM_USER_PREPARING = True
        try:
            username = f"locust_warm_{uuid.uuid4().hex[:10]}"
            payload = {"username": username, "password": PASSWORD}

            with client.post(
                "/auth/signup",
                json=payload,
                name="/auth/signup",
                catch_response=True,
            ) as response:
                if response.status_code != 201:
                    response.failure(
                        f"warm signup failed: {response.status_code} {response.text}"
                    )
                    raise RuntimeError(
                        f"warm signup failed with status {response.status_code}"
                    )

            headers = login_and_get_headers(client, username=username, password=PASSWORD)

            file_obj = io.BytesIO(build_pdf_bytes())
            files = {"file": ("warm_seed.pdf", file_obj, "application/pdf")}
            with client.post(
                "/documents",
                headers=headers,
                files=files,
                name="/documents [warm seed upload]",
                catch_response=True,
            ) as response:
                if response.status_code != 202:
                    response.failure(
                        f"warm seed upload failed: {response.status_code} {response.text}"
                    )
                    raise RuntimeError(
                        f"warm seed upload failed with status {response.status_code}"
                    )

                document_id = response.json().get("id")
                if not document_id:
                    response.failure("warm seed upload did not return document id")
                    raise RuntimeError("warm seed upload did not return document id")

            wait_for_document_ready(client, headers=headers, document_id=int(document_id))
            _WARM_USER_HEADERS = headers
            return _WARM_USER_HEADERS
        except Exception as exc:
            _WARM_USER_ERROR = str(exc)
            raise
        finally:
            _WARM_USER_PREPARING = False

    while _WARM_USER_PREPARING:
        time.sleep(WARM_USER_WAIT_INTERVAL_SECONDS)

    if _WARM_USER_HEADERS is not None:
        return _WARM_USER_HEADERS

    if _WARM_USER_ERROR is not None:
        raise RuntimeError(_WARM_USER_ERROR)

    raise RuntimeError("warm user preparation ended without usable state")


class AuthenticatedUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.username = f"locust_{uuid.uuid4().hex[:10]}"
        self.headers: dict[str, str] = {}
        self.signup()
        self.login()
        self.seed_document()

    def signup(self) -> None:
        payload = {"username": self.username, "password": PASSWORD}
        with self.client.post(
            "/auth/signup",
            json=payload,
            name="/auth/signup",
            catch_response=True,
        ) as response:
            if response.status_code != 201:
                response.failure(f"signup failed: {response.status_code} {response.text}")

    def login(self) -> None:
        self.headers = login_and_get_headers(
            self.client,
            username=self.username,
            password=PASSWORD,
        )

    def seed_document(self) -> None:
        file_obj = io.BytesIO(build_pdf_bytes())
        filename = f"{self.username}_seed.pdf"
        files = {"file": (filename, file_obj, "application/pdf")}

        with self.client.post(
            "/documents",
            headers=self.headers,
            files=files,
            name="/documents [seed upload]",
            catch_response=True,
        ) as response:
            if response.status_code != 202:
                response.failure(f"seed upload failed: {response.status_code} {response.text}")
                return

            body = response.json()
            document_id = body.get("id")
            if not document_id:
                response.failure("seed upload did not return document id")
                return

        wait_for_document_ready(self.client, headers=self.headers, document_id=int(document_id))

    @tag("search")
    @task(5)
    def search_documents(self) -> None:
        self.client.get(
            f"/search?q={SEARCH_QUERY}&limit=5",
            headers=self.headers,
            name="/search",
        )

    @tag("documents")
    @task(1)
    def list_documents(self) -> None:
        self.client.get(
            "/documents",
            headers=self.headers,
            name="/documents",
        )

    @tag("uploads")
    @task(1)
    def upload_document(self) -> None:
        filename = f"{self.username}_{uuid.uuid4().hex[:8]}.pdf"
        file_obj = io.BytesIO(build_pdf_bytes())
        files = {"file": (filename, file_obj, "application/pdf")}
        self.client.post(
            "/documents",
            headers=self.headers,
            files=files,
            name="/documents [upload]",
        )

    @tag("auth")
    @task(1)
    def get_current_user(self) -> None:
        self.client.get(
            "/me",
            headers=self.headers,
            name="/me",
        )


class WarmSearchUser(HttpUser):
    wait_time = between(1, 2)
    weight = 2

    def on_start(self) -> None:
        self.headers = prepare_warm_user(self.client)

    @tag("search")
    @task(10)
    def search_documents(self) -> None:
        self.client.get(
            f"/search?q={SEARCH_QUERY}&limit=5",
            headers=self.headers,
            name="/search [warm]",
        )

    @tag("documents")
    @task(1)
    def list_documents(self) -> None:
        self.client.get(
            "/documents",
            headers=self.headers,
            name="/documents [warm]",
        )

    @tag("auth")
    @task(1)
    def get_current_user(self) -> None:
        self.client.get(
            "/me",
            headers=self.headers,
            name="/me [warm]",
        )


class AuthOnlyUser(HttpUser):
    wait_time = between(1, 2)
    weight = 1

    @tag("auth")
    @task(3)
    def signup_and_login(self) -> None:
        username = f"locust_auth_{uuid.uuid4().hex[:10]}"
        payload = {"username": username, "password": PASSWORD}

        with self.client.post(
            "/auth/signup",
            json=payload,
            name="/auth/signup",
            catch_response=True,
        ) as response:
            if response.status_code != 201:
                response.failure(f"signup failed: {response.status_code} {response.text}")
                return

        with self.client.post(
            "/auth/login",
            json=payload,
            name="/auth/login",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"login failed: {response.status_code} {response.text}")

    @tag("auth")
    @task(1)
    def invalid_login(self) -> None:
        username = f"locust_invalid_{uuid.uuid4().hex[:10]}"
        payload = {"username": username, "password": PASSWORD}

        with self.client.post(
            "/auth/login",
            json=payload,
            name="/auth/login [invalid]",
            catch_response=True,
        ) as response:
            if response.status_code == 401:
                response.success()
            else:
                response.failure(
                    f"invalid login returned {response.status_code} instead of 401"
                )


class SearchOnlyUser(AuthenticatedUser):
    weight = 3

    @tag("search")
    @task(10)
    def search_documents(self) -> None:
        super().search_documents()

    @tag("documents")
    @task(1)
    def list_documents(self) -> None:
        super().list_documents()


class DocumentListUser(AuthenticatedUser):
    weight = 2

    @tag("documents")
    @task(8)
    def list_documents(self) -> None:
        super().list_documents()

    @tag("auth")
    @task(2)
    def get_current_user(self) -> None:
        super().get_current_user()


class UploadOnlyUser(AuthenticatedUser):
    weight = 1

    @tag("uploads")
    @task(8)
    def upload_document(self) -> None:
        super().upload_document()

    @tag("documents")
    @task(1)
    def list_documents(self) -> None:
        super().list_documents()

    @tag("search")
    @task(1)
    def search_documents(self) -> None:
        super().search_documents()


class SearchHeavyUser(AuthenticatedUser):
    weight = 3


class MixedTrafficUser(AuthenticatedUser):
    weight = 2


class UploadHeavyUser(AuthenticatedUser):
    weight = 1

    @task(4)
    def upload_document(self) -> None:
        super().upload_document()

    @task(1)
    def search_documents(self) -> None:
        super().search_documents()
