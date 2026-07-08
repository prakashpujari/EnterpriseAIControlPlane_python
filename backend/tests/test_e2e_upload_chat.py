"""
End-to-end test for document upload and chat retrieval.
"""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

# Change working directory to repository root so that relative paths in .env work correctly
# (the .env file expects to be run from root, where test.db resides)
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now import the app (this will load .env from the current directory, which is repo root)
from app.main import app
from app.config import settings

print(f"DATABASE_URL from settings: {settings.DATABASE_URL}")

client = TestClient(app)


def test_document_upload_and_chat():
    # 1. Upload a text file with known content
    content = (
        "Enterprise AI Control Plane is a powerful system that uses "
        "Retrieval-Augmented Generation (RAG) and memory to provide accurate answers. "
        "It supports multiple roles such as support engineer and mortgage analyst."
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(content)
        fname = f.name

    try:
        with open(fname, "rb") as file:
            files = {"file": (os.path.basename(fname), file, "text/plain")}
            upload_resp = client.post("/api/v1/documents/upload", files=files)
        assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
        upload_data = upload_resp.json()
        doc_id = upload_data["document_id"]
        print(f"Uploaded document ID: {doc_id}")
        assert doc_id is not None

        # 2. Verify document appears in list
        list_resp = client.get("/api/v1/documents")
        assert list_resp.status_code == 200, f"List documents failed: {list_resp.text}"
        documents = list_resp.json()
        assert isinstance(documents, list) and len(documents) > 0
        # Find our document
        found = any(d.get("id") == doc_id for d in documents)
        assert found, f"Uploaded document {doc_id} not found in document list"

        # 3. Create a chat session
        session_resp = client.post(
            "/api/v1/chat/session",
            json={"role": "support_engineer", "title": "Test session"},
        )
        assert session_resp.status_code == 200, f"Create session failed: {session_resp.text}"
        session_data = session_resp.json()
        session_id = session_data["session_id"]
        print(f"Created session ID: {session_id}")

        # 4. Send a chat message via the chat endpoint
        chat_payload = {
            "query": "What is Enterprise AI Control Plane?",
            "session_id": session_id,
            "role": "support_engineer",
        }
        chat_resp = client.post("/api/v1/chat", json=chat_payload)
        assert chat_resp.status_code == 200, f"Chat failed: {chat_resp.text}"
        chat_data = chat_resp.json()
        response_text = chat_data.get("response", "")
        print(f"Chat response: {response_text}")

        # 5. Verify response contains expected keywords from the document
        assert (
            "powerful system" in response_text.lower()
            or "rag" in response_text.lower()
            or "memory" in response_text.lower()
        ), f"Response does not contain expected keywords: {response_text}"
        assert len(response_text.strip()) > 0, "Response is empty"

    finally:
        os.unlink(fname)


if __name__ == "__main__":
    test_document_upload_and_chat()
    print("Test passed!")