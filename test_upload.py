#!/usr/bin/env python3
"""Test upload endpoint"""
import requests
import json

BASE_URL = "http://localhost:5000"

try:
    # 1. Signup
    print("[1] Signing up...")
    resp = requests.post(f"{BASE_URL}/auth/signup", json={"username": "uitest123", "password": "password123"})
    print(f"    Status: {resp.status_code}")
    if resp.status_code != 201:
        print(f"    Error: {resp.text}")
        # Try with different username
        resp = requests.post(f"{BASE_URL}/auth/signup", json={"username": f"uitest{hash('test')}", "password": "password123"})
        print(f"    Retry Status: {resp.status_code}")

    # 2. Login
    print("[2] Logging in...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "uitest123", "password": "password123"})
    if resp.status_code != 200:
        print(f"    Error: {resp.text}")
        print("    Cannot proceed")
        exit(1)
    
    token = resp.json()["access_token"]
    print(f"    Status: {resp.status_code}, Token: {token[:20]}...")

    # 3. Create test PDF
    pdf_path = "test_doc.pdf"
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4\nTest PDF content")
    print(f"[3] Test PDF created: {pdf_path}")

    # 4. Upload
    print("[4] Uploading document...")
    with open(pdf_path, "rb") as f:
        files = {"file": ("test_doc.pdf", f, "application/pdf")}
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(f"{BASE_URL}/documents", files=files, headers=headers)
    
    print(f"    Status: {resp.status_code}")
    print(f"    Response: {json.dumps(resp.json(), indent=2)}")

    # 5. Get documents
    print("[5] Fetching documents...")
    resp = requests.get(f"{BASE_URL}/documents", headers=headers)
    print(f"    Status: {resp.status_code}")
    docs = resp.json()
    print(f"    Documents: {len(docs)}")
    for doc in docs:
        print(f"      - {doc['filename']} [{doc['status']}]")

    # Cleanup
    import os
    os.remove(pdf_path)
    print("\n✅ UPLOAD TEST PASSED")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
