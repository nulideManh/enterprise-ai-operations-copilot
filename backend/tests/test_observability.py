import pytest
from app.models.document import Document
from app.models.ticket import Ticket
from app.models.email import Email

@pytest.mark.asyncio
async def test_metrics_endpoint(async_client, db_session):
    # Seed some dummy objects to test metrics counts
    doc = Document(name="doc1.docx", department="Engineering", visibility="Employee")
    ticket = Ticket(issue="Issue 1", category="IT Support", priority="Low", assignee="Desk")
    email = Email(sender="test@test.com", content="Test", category="Support", confidence=0.9)
    
    db_session.add_all([doc, ticket, email])
    await db_session.commit()
    
    response = await async_client.get("/api/observability/metrics")
    assert response.status_code == 200
    data = response.json()
    
    assert data["documents"] >= 1
    assert data["tickets"] >= 1
    assert data["emails"] >= 1
    assert data["invoices"] >= 0
    assert data["github_issues"] >= 0
