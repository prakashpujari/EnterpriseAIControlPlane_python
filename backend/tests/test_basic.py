"""
Basic tests for Enterprise AI Customer Support Assistant.
"""

import pytest
from fastapi.testclient import TestClient


def test_settings():
    """Test settings configuration."""
    from app.config.settings import settings

    assert settings.APP_NAME == "Enterprise AI Customer Support Assistant"
    assert settings.APP_VERSION == "1.0.0"
    assert settings.ENVIRONMENT == "development"

    # Check Groq models
    assert "llama-3.1-8b-instruct" in settings.SMALL_MODEL
    assert "llama-3.1-70b-sonnet" in settings.MEDIUM_MODEL
    assert "mixtral-8x7b-32b" in settings.LARGE_MODEL


def test_role_types():
    """Test role type enum."""
    from app.config.settings import RoleType

    assert RoleType.SUPPORT_ENGINEER.value == "support_engineer"
    assert RoleType.MORTGAGE_ANALYST.value == "mortgage_analyst"
    assert RoleType.COMPLIANCE_OFFICER.value == "compliance_officer"
    assert RoleType.PRODUCT_OWNER.value == "product_owner"


def test_query_types():
    """Test query type enum."""
    from app.config.settings import QueryType

    assert QueryType.FAQ.value == "faq"
    assert QueryType.RAG.value == "rag"
    assert QueryType.SUMMARIZE.value == "summarize"
    assert QueryType.REASON.value == "reason"


def test_model_router():
    """Test model routing logic."""
    from app.config.llm_providers import model_router

    # FAQ should route to small model
    assert model_router.route_query("faq", "support_engineer") == "small"

    # RAG should route to medium model
    assert model_router.route_query("rag", "support_engineer") == "medium"

    # Reason should route to large model
    assert model_router.route_query("reason", "support_engineer") == "large"

    # Summarize should route to medium model
    assert model_router.route_query("summarize", "support_engineer") == "medium"


def test_planner_agent():
    """Test planner agent classification."""
    from app.agents.planner import PlannerAgent, QueryType

    agent = PlannerAgent()

    # FAQ query
    result = agent._rule_based_classify("What are your hours?", "support_engineer")
    assert result.query_type == QueryType.FAQ


def test_pii_scanner():
    """Test PII scanning."""
    from app.gateway.guardrails import PIIScanner

    scanner = PIIScanner()

    # Test email detection
    result = scanner.scan("Contact us at test@example.com")
    assert result.detected
    assert "email" in result.pii_types

    # Test no PII
    result = scanner.scan("Hello, how can I help you?")
    assert not result.detected


def test_health_endpoint():
    """Test health endpoint."""
    from app.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_metrics_endpoint():
    """Test metrics endpoint."""
    from app.main import app

    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200