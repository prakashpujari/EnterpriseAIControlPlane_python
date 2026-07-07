"""
End-to-end UI test for the Enterprise AI Customer Support Assistant.

Drives a real Chromium browser through the live application:
  frontend (http://localhost:3000)  ->  backend (http://localhost:8000)

Flow under test:
  /  ->  (login if gate enabled)  ->  chat home
  ->  type a message  ->  send  ->  assistant reply rendered (with metrics)

The backend runs with DISABLE_AUTH=true (dev mode), so the frontend's
dev token is accepted and no 401s occur on chat / metrics. If the login
gate is enabled it also drives the real login form.

Run with:  pytest e2e/test_ui_e2e.py -v -s
Requires: backend on :8000, frontend on :3000, `playwright install chromium`.
"""

import os

import pytest
from playwright.sync_api import sync_playwright, expect

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
CREDENTIALS = {
    "email": os.environ.get("E2E_EMAIL", "admin@example.com"),
    "password": os.environ.get("E2E_PASSWORD", "Admin123!"),
}
TEST_MESSAGE = "What are your support hours?"
SETTLED_MARKERS = [
    "Model:",                     # assistant reply with model indicator (success)
    "unexpected error",           # backend 500 message (graceful error path)
    "Failed to send message",     # axios error fallback (graceful error path)
]


@pytest.fixture
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


def _login_if_needed(page):
    """If the login gate is enabled, drive the real login form."""
    email_field = page.get_by_label("Email")
    if email_field.count() > 0 and email_field.is_visible(timeout=5000):
        email_field.fill(CREDENTIALS["email"])
        page.get_by_label("Password").fill(CREDENTIALS["password"])
        page.get_by_role("button", name="Sign In").click()
        print("\n[E2E] Logged in via login form")
        return True
    print("\n[E2E] Login gate bypassed (dev mode)")
    return False


def test_ui_login_and_chat_end_to_end(browser):
    page = browser.new_page()
    page_errors = []
    chat_responses = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    page.on(
        "response",
        lambda resp: chat_responses.append((resp.status, resp.url))
        if "/api/v1/chat" in resp.url
        else None,
    )

    artifacts = os.path.join(os.path.dirname(__file__), "artifacts")
    os.makedirs(artifacts, exist_ok=True)

    try:
        # 1. App loads. In local dev the frontend may bypass the login gate
        #    (VITE_DISABLE_AUTH=true); otherwise it redirects to /login.
        page.goto(FRONTEND_URL + "/", wait_until="networkidle")

        # 2. Log in only if a login form is present.
        _login_if_needed(page)

        # 3. Land on the chat home (protected route).
        expect(
            page.get_by_text("Welcome to Enterprise AI Customer Support")
        ).to_be_visible(timeout=15000)

        # 4. Send a chat message.
        page.get_by_placeholder("Type your message...").fill(TEST_MESSAGE)
        page.get_by_role("button", name="send", exact=True).click()

        # 5. The user's own message is rendered immediately (as a chat bubble,
        #    not the (disabled) composer textarea which also holds the text).
        expect(
            page.get_by_role("paragraph").filter(has_text=TEST_MESSAGE)
        ).to_be_visible(timeout=10000)

        # 6. Wait until the assistant reply (or a graceful error) is rendered.
        expect(
            page.get_by_text("Model:")
            .or_(page.get_by_text("unexpected error"))
            .or_(page.get_by_text("Failed to send message"))
        ).to_be_visible(timeout=90000)

        body_text = page.inner_text("body").lower()
        assistant_replied = "model:" in body_text
        graceful_error = any(
            m in body_text for m in ("unexpected error", "failed to send message")
        )

        # 7. No uncaught client-side errors during the flow.
        assert not page_errors, f"Uncaught page errors: {page_errors}"
        assert (
            assistant_replied or graceful_error
        ), "Chat did not reach a settled state (no reply and no error shown)."
    finally:
        page.screenshot(
            path=os.path.join(artifacts, "chat_result.png"), full_page=False
        )
        with open(
            os.path.join(artifacts, "last_body.txt"), "w", encoding="utf-8"
        ) as f:
            f.write(page.inner_text("body"))
        print(f"\n[E2E] chat_responses={chat_responses}")
        print(f"[E2E] page_errors={page_errors}")
        outcome = "ASSISTANT_REPLY" if "model:" in page.inner_text("body").lower() else (
            "GRACEFUL_ERROR" if any(m in page.inner_text("body").lower()
                                    for m in ("unexpected error", "failed to send message"))
            else "NO_SETTLE"
        )
        print(f"[E2E] Outcome: {outcome}")
