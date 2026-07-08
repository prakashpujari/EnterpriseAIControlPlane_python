import requests
import os

BASE_URL = "http://localhost:8000"

def main():
    # 1. Upload a file
    content = (
        "Enterprise AI Control Plane is a powerful system that uses "
        "Retrieval-Augmented Generation (RAG) and memory to provide accurate answers. "
        "It supports multiple roles such as support engineer and mortgage analyst."
    )
    # Create a temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(content)
        fname = f.name

    try:
        with open(fname, "rb") as f:
            files = {"file": (os.path.basename(fname), f, "text/plain")}
            resp = requests.post(f"{BASE_URL}/api/v1/documents/upload", files=files)
        print(f"Upload status: {resp.status_code}")
        print(f"Upload response: {resp.text}")
        resp.raise_for_status()
        upload_data = resp.json()
        doc_id = upload_data.get("document_id")
        print(f"Uploaded document ID: {doc_id}")
        assert doc_id, "No document ID returned"

        # 2. List documents (optional)
        list_resp = requests.get(f"{BASE_URL}/api/v1/documents")
        print(f"List status: {list_resp.status_code}")
        print(f"List response: {list_resp.text}")
        list_resp.raise_for_status()
        documents = list_resp.json()
        print(f"Documents list: {documents}")
        found = any(doc.get("id") == doc_id for doc in documents)
        assert found, f"Uploaded document {doc_id} not found in list"

        # 3. Create a chat session
        session_resp = requests.post(
            f"{BASE_URL}/api/v1/chat/session",
            params={"role": "support_engineer", "title": "Test session"},
        )
        print(f"Create session status: {session_resp.status_code}")
        print(f"Create session response: {session_resp.text}")
        session_resp.raise_for_status()
        session_data = session_resp.json()
        session_id = session_data.get("session_id")
        print(f"Created session ID: {session_id}")
        assert session_id, "No session ID returned"

        # 4. Send a chat message
        chat_payload = {
            "query": "What is Enterprise AI Control Plane?",
            "session_id": session_id,
            "role": "support_engineer"
        }
        chat_resp = requests.post(f"{BASE_URL}/api/v1/chat", json=chat_payload)
        print(f"Chat status: {chat_resp.status_code}")
        print(f"Chat response: {chat_resp.text}")
        chat_resp.raise_for_status()
        chat_data = chat_resp.json()
        response_text = chat_data.get("response", "")
        print(f"Chat response text: {response_text}")

        # 5. Check for expected keywords
        assert (
            "powerful system" in response_text.lower()
            or "rag" in response_text.lower()
            or "memory" in response_text.lower()
        ), f"Response does not contain expected keywords: {response_text}"
        assert len(response_text.strip()) > 0, "Response is empty"

        print("\n✅ All tests passed!")
    finally:
        os.remove(fname)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise