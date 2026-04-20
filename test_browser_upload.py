#!/usr/bin/env python3
"""Direct test of the upload from browser-like request"""
import requests
import time

BASE_URL = "http://localhost:5000"

# First, signup and login
print("[SETUP] Creating test user...")
resp = requests.post(f"{BASE_URL}/auth/signup", json={
    "username": f"uitest{int(time.time())}",
    "password": "test123456"
})
username = resp.json()["username"]
print(f"✓ Signed up: {username}")

print("[SETUP] Logging in...")
resp = requests.post(f"{BASE_URL}/auth/login", json={
    "username": username,
    "password": "test123456"})
token = resp.json()["access_token"]
print(f"✓ Logged in, token: {token[:30]}...")

# Now test upload like the browser does
print("\n[TEST] Simulating browser file upload...")
pdf_content = b"%PDF-1.4\n%Test PDF from browser simulation"

# This is how FormData sends files in a browser
files = {
    'file': ('test_document.pdf', pdf_content, 'application/pdf')
}
headers = {
    'Authorization': f'Bearer {token}'
}

print(f"Headers: {headers}")
print(f"Files: {files.keys()}")

resp = requests.post(f"{BASE_URL}/documents", files=files, headers=headers)
print(f"Upload response status: {resp.status_code}")
print(f"Upload response: {resp.json()}")

if resp.status_code == 202:
    print("\n✅ Upload successful (202)!")
    doc = resp.json()
    print(f"Document ID: {doc['id']}")
    print(f"Status: {doc['status']}")
    
    print("\n[TEST] Fetching documents list...")
    resp = requests.get(f"{BASE_URL}/documents", headers=headers)
    docs = resp.json()
    print(f"Documents: {len(docs)}")
    for doc in docs:
        print(f"  - {doc['filename']} [{doc['status']}]")
    
    if len(docs) > 0:
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ ERROR: Upload succeeded but document not in list!")
else:
    print(f"\n❌ ERROR: Upload failed with status {resp.status_code}")
    print(f"Response: {resp.json()}")
