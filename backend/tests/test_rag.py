import pytest
from docx import Document as DocxDoc
from io import BytesIO
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.document_parser import recursive_chunk, semantic_chunk
from app.services.rag import ingest_upload, retrieve
from app.models.user import User

def test_recursive_chunking():
    text = "This is sentence one. This is sentence two. This is sentence three."
    chunks = recursive_chunk(text, max_chars=40, overlap=10)
    assert len(chunks) > 0
    assert all(len(c) <= 40 for c in chunks)

def test_semantic_chunking():
    text = "First paragraph here.\n\nSecond paragraph starts here. It has multiple sentences."
    chunks = semantic_chunk(text, max_chars=80, min_chars=10)
    assert len(chunks) > 0

@pytest.mark.asyncio
async def test_ingest_upload_and_retrieval(db_session):
    # Setup test user
    user = User(email="uploader@example.com", role="Employee", department="HR")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Create real docx content
    doc_obj = DocxDoc()
    doc_obj.add_paragraph("This is a corporate HR policy document. It defines leave options. Maternity leave is 12 weeks.")
    file_stream = BytesIO()
    doc_obj.save(file_stream)
    content = file_stream.getvalue()
    
    doc, chunk_count = await ingest_upload(
        db_session,
        user=user,
        filename="hr_test.docx",
        content=content,
        department="HR",
        visibility="Employee"
    )
    
    assert doc.name == "hr_test.docx"
    assert chunk_count > 0
    assert doc.department == "HR"
    assert doc.visibility == "Employee"
    
    # Test retrieval
    results = await retrieve(
        db_session,
        user=user,
        query="Maternity leave",
        limit=5,
        mode="hybrid"
    )
    
    assert len(results) > 0
    assert results[0].document.id == doc.id
    assert "Maternity" in results[0].chunk.content

@pytest.mark.asyncio
async def test_retrieval_rbac_visibility(db_session):
    # Setup users
    admin = User(email="admin_user@example.com", role="Admin", department="Engineering")
    engineer = User(email="eng_user@example.com", role="Employee", department="Engineering")
    hr_emp = User(email="hr_user@example.com", role="Employee", department="HR")
    
    db_session.add_all([admin, engineer, hr_emp])
    await db_session.commit()
    await db_session.refresh(admin)
    await db_session.refresh(engineer)
    await db_session.refresh(hr_emp)
    
    # Create real docx content
    doc_obj = DocxDoc()
    doc_obj.add_paragraph("HR Confidential salary bands. Admin and HR role only.")
    file_stream = BytesIO()
    doc_obj.save(file_stream)
    content = file_stream.getvalue()
    
    doc, _ = await ingest_upload(
        db_session,
        user=admin,
        filename="confidential.docx",
        content=content,
        department="HR",
        visibility="HR"
    )
    
    # Engineer (role Employee, department Engineering) should NOT be able to retrieve it
    eng_results = await retrieve(
        db_session,
        user=engineer,
        query="salary bands",
        limit=5
    )
    assert len(eng_results) == 0
    
    # Admin should be able to retrieve it (Admin bypasses all filters)
    admin_results = await retrieve(
        db_session,
        user=admin,
        query="salary bands",
        limit=5
    )
    assert len(admin_results) > 0
    
    # HR Employee (department HR) should be able to retrieve it due to department match
    hr_results = await retrieve(
        db_session,
        user=hr_emp,
        query="salary bands",
        limit=5
    )
    assert len(hr_results) > 0
