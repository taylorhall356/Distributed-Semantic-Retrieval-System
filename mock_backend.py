"""
Mock API Backend for UI Testing
Provides mock endpoints that simulate the real API
"""
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from datetime import datetime, timedelta
import jwt
import json
import os
import threading
import time

app = Flask(__name__)
CORS(app)

# Mock data storage
mock_users = {
    "testuser": {
        "id": 1,
        "username": "testuser",
        "password": "test123"  # In real app, this would be hashed
    }
}

mock_documents = {
    1: [
        {
            "id": 1,
            "user_id": 1,
            "filename": "machine_learning_basics.pdf",
            "status": "ready",
            "created_at": (datetime.now() - timedelta(days=2)).isoformat()
        },
        {
            "id": 2,
            "user_id": 1,
            "filename": "deep_learning_guide.pdf",
            "status": "ready",
            "created_at": (datetime.now() - timedelta(days=1)).isoformat()
        },
        {
            "id": 3,
            "user_id": 1,
            "filename": "neural_networks.pdf",
            "status": "processing",
            "created_at": datetime.now().isoformat()
        }
    ]
}

mock_search_results = [
    {
        "document_id": 1,
        "document_filename": "machine_learning_basics.pdf",
        "score": 0.92,
        "text": "Machine learning is a subset of artificial intelligence that focuses on the ability of computers to learn from data without being explicitly programmed."
    },
    {
        "document_id": 2,
        "document_filename": "deep_learning_guide.pdf",
        "score": 0.87,
        "text": "Deep learning uses artificial neural networks with multiple layers (hence 'deep') to progressively extract higher-level features from raw input."
    },
    {
        "document_id": 1,
        "document_filename": "machine_learning_basics.pdf",
        "score": 0.81,
        "text": "Supervised learning is a method where the model learns from labeled data, where each example has an associated target output."
    },
    {
        "document_id": 3,
        "document_filename": "neural_networks.pdf",
        "score": 0.76,
        "text": "A neural network is composed of interconnected nodes (neurons) organized in layers that process information using connectionist approaches."
    },
    {
        "document_id": 2,
        "document_filename": "deep_learning_guide.pdf",
        "score": 0.71,
        "text": "Convolutional neural networks (CNNs) are particularly effective for image processing and computer vision tasks."
    }
]

JWT_SECRET = "development-secret-key-at-least-32-bytes"

def generate_token(user_id, username):
    """Generate a mock JWT token"""
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token):
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except:
        return None

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok"}), 200

@app.route("/auth/signup", methods=["POST"])
def signup():
    """Sign up a new user"""
    data = request.json
    username = data.get("username", "").lower()
    password = data.get("password", "")
    
    if not username or not password:
        return jsonify({"detail": "Username and password required"}), 400
    
    if username in mock_users:
        return jsonify({"detail": "User already exists"}), 409
    
    if len(password) < 6:
        return jsonify({"detail": "Password must be at least 6 characters"}), 400
    
    # Create new user
    new_user = {
        "id": len(mock_users) + 1,
        "username": username,
        "password": password
    }
    mock_users[username] = new_user
    mock_documents[new_user["id"]] = []
    
    return jsonify({
        "id": new_user["id"],
        "username": new_user["username"]
    }), 201

@app.route("/auth/login", methods=["POST"])
def login():
    """Log in a user"""
    data = request.json
    username = data.get("username", "").lower()
    password = data.get("password", "")
    
    user = mock_users.get(username)
    if not user or user["password"] != password:
        return jsonify({"detail": "Invalid credentials"}), 401
    
    token = generate_token(user["id"], user["username"])
    return jsonify({"access_token": token, "token_type": "bearer"}), 200

@app.route("/me", methods=["GET"])
def get_me():
    """Get current user info"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"detail": "Not authenticated"}), 401
    
    token = auth_header[7:]
    payload = verify_token(token)
    if not payload:
        return jsonify({"detail": "Invalid token"}), 401
    
    return jsonify({
        "id": payload["user_id"],
        "username": payload["username"]
    }), 200

@app.route("/documents", methods=["GET"])
def list_documents():
    """List user's documents"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"detail": "Not authenticated"}), 401
    
    token = auth_header[7:]
    payload = verify_token(token)
    if not payload:
        return jsonify({"detail": "Invalid token"}), 401
    
    user_id = payload["user_id"]
    documents = mock_documents.get(user_id, [])
    return jsonify(documents), 200

@app.route("/documents", methods=["OPTIONS"])
def documents_options():
    """Handle CORS preflight for documents endpoint"""
    return "", 204

@app.route("/documents", methods=["POST"])
def upload_document():
    """Upload a new document"""
    print(f"DEBUG: Upload request received")
    print(f"DEBUG: Headers: {dict(request.headers)}")
    print(f"DEBUG: Files: {request.files.keys()}")
    
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        print("DEBUG: No auth header")
        return jsonify({"detail": "Not authenticated"}), 401
    
    token = auth_header[7:]
    payload = verify_token(token)
    if not payload:
        print("DEBUG: Invalid token")
        return jsonify({"detail": "Invalid token"}), 401
    
    if "file" not in request.files:
        print("DEBUG: No file in request.files")
        print(f"DEBUG: Available keys: {list(request.files.keys())}")
        return jsonify({"detail": "No file provided"}), 400
    
    file = request.files["file"]
    print(f"DEBUG: File received: {file.filename}")
    
    if not file.filename.endswith(".pdf"):
        return jsonify({"detail": "Only PDF files allowed"}), 400
    
    # Create mock document
    user_id = payload["user_id"]
    doc_id = max([doc["id"] for docs in mock_documents.values() for doc in docs] or [0]) + 1
    
    new_doc = {
        "id": doc_id,
        "user_id": user_id,
        "filename": file.filename,
        "status": "processing",
        "created_at": datetime.now().isoformat()
    }
    
    if user_id not in mock_documents:
        mock_documents[user_id] = []
    
    mock_documents[user_id].append(new_doc)
    print(f"DEBUG: Document added. ID={doc_id}, User={user_id}")
    
    # Start a background thread to transition to "ready" after 5 seconds
    def transition_to_ready(user_id, doc_id):
        time.sleep(5)
        for doc in mock_documents.get(user_id, []):
            if doc["id"] == doc_id:
                doc["status"] = "ready"
                print(f"DEBUG: Transitioned doc {doc_id} to ready")
                break
    
    thread = threading.Thread(target=transition_to_ready, args=(user_id, doc_id), daemon=True)
    thread.start()
    
    print(f"DEBUG: Returning {new_doc}")
    return jsonify(new_doc), 202

@app.route("/documents/<int:doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    """Delete a document"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"detail": "Not authenticated"}), 401
    
    token = auth_header[7:]
    payload = verify_token(token)
    if not payload:
        return jsonify({"detail": "Invalid token"}), 401
    
    user_id = payload["user_id"]
    if user_id not in mock_documents:
        return jsonify({"detail": "Document not found"}), 404
    
    # Find and delete document
    docs = mock_documents[user_id]
    original_len = len(docs)
    mock_documents[user_id] = [d for d in docs if d["id"] != doc_id]
    
    if len(mock_documents[user_id]) == original_len:
        return jsonify({"detail": "Document not found"}), 404
    
    return "", 204

@app.route("/search", methods=["GET"])
def search():
    """Search documents"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"detail": "Not authenticated"}), 401
    
    token = auth_header[7:]
    payload = verify_token(token)
    if not payload:
        return jsonify({"detail": "Invalid token"}), 401
    
    query = request.args.get("q", "")
    if not query:
        return jsonify({"detail": "Query required"}), 400
    
    # Return mock search results
    return jsonify(mock_search_results), 200

@app.route("/queue-test", methods=["POST"])
def queue_test():
    """Queue test endpoint"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"detail": "Not authenticated"}), 401
    
    token = auth_header[7:]
    payload = verify_token(token)
    if not payload:
        return jsonify({"detail": "Invalid token"}), 401
    
    return jsonify({
        "task_id": "mock-task-123",
        "queue": "document_processing",
        "status": "queued"
    }), 202

if __name__ == "__main__":
    print("=" * 60)
    print("Mock API Backend Running")
    print("=" * 60)
    print("URL: http://localhost:5000")
    print("\nTest Credentials:")
    print("  Username: testuser")
    print("  Password: test123")
    print("\nNote: This is a mock backend with simulated data.")
    print("For production, use the real FastAPI backend with Docker.")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=False)
