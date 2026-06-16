from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine, get_session
from app.models import AuditLog, Chunk, Conversation, Document, Evaluation, Message
from app.models.user import User
from app.schemas.api import (
    ChatRequest,
    ChatResponse,
    DocumentResponse,
    EmailClassificationRequest,
    EmailClassificationResponse,
    EvaluationRequest,
    GitHubAssistantRequest,
    GitHubAssistantResponse,
    InvoiceExtractionResponse,
    MetricsResponse,
    TicketRequest,
    TicketResponse,
)
from app.services.auth import get_or_create_user
from app.services.document_parser import parse_document
from app.services.llm import generate_answer, list_local_models
from app.services.rag import build_citations, ingest_upload, now_ms, retrieve, save_chat_trace, visibility_filter
from app.services.security import detect_prompt_injection, mask_pii


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _format_context_citation(citation) -> str:
    page = f" page {citation.page}" if citation.page else ""
    score = f" | score: {citation.score:.3f}" if citation.score is not None else ""
    return (
        f"Source: {citation.document_name}{page}"
        f" | department: {citation.department}"
        f" | retrieval: {citation.retrieval_method}{score}\n"
        f"{citation.excerpt}"
    )


async def current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    email: Annotated[str, Header(alias="X-User-Email")] = "admin@example.com",
    role: Annotated[str, Header(alias="X-User-Role")] = "Admin",
    department: Annotated[str, Header(alias="X-User-Department")] = "Engineering",
) -> User:
    return await get_or_create_user(session, email=email, role=role, department=department)


@app.on_event("startup")
async def startup() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunking_strategy VARCHAR(32) DEFAULT 'recursive'")
        )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/api/me")
async def me(user: Annotated[User, Depends(current_user)]) -> dict[str, str]:
    return {"id": user.id, "email": user.email, "role": user.role, "department": user.department}


@app.get("/api/llm/status")
async def llm_status() -> dict[str, object]:
    models: list[str] = []
    local_available = False
    if settings.local_llm_base_url:
        try:
            models = await list_local_models()
            local_available = True
        except Exception:
            local_available = False

    return {
        "provider": settings.llm_provider,
        "openai_configured": bool(settings.openai_api_key),
        "local_base_url": settings.local_llm_base_url,
        "local_chat_model": settings.local_chat_model,
        "local_available": local_available,
        "local_models": models,
    }


@app.post("/api/documents", response_model=DocumentResponse)
async def upload_document(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
    file: Annotated[UploadFile, File()],
    department: Annotated[str, Form()] = "Engineering",
    visibility: Annotated[str, Form()] = "Employee",
    chunking_strategy: Annotated[str, Form(pattern="^(recursive|semantic)$")] = "recursive",
) -> DocumentResponse:
    content = await file.read()
    try:
        document, chunks = await ingest_upload(
            session,
            user=user,
            filename=file.filename or "document",
            content=content,
            department=department,
            visibility=visibility,
            chunking_strategy=chunking_strategy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DocumentResponse(
        id=document.id,
        name=document.name,
        department=document.department,
        visibility=document.visibility,
        chunks=chunks,
        chunking_strategy=document.chunking_strategy,
    )


@app.get("/api/documents", response_model=list[DocumentResponse])
async def list_documents(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> list[DocumentResponse]:
    stmt = (
        select(Document, func.count(Chunk.id))
        .outerjoin(Chunk)
        .where(visibility_filter(user))
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()
    return [
        DocumentResponse(
            id=document.id,
            name=document.name,
            department=document.department,
            visibility=document.visibility,
            chunks=chunk_count,
            chunking_strategy=document.chunking_strategy,
        )
        for document, chunk_count in rows
    ]


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> ChatResponse:
    started = now_ms()
    security_events = detect_prompt_injection(payload.message)
    if security_events:
        session.add(
            AuditLog(
                user_id=user.id,
                event_type="security.prompt_injection.blocked",
                payload={"prompt": payload.message, "matches": security_events},
            )
        )
        await session.commit()
        return ChatResponse(
            conversation_id=payload.conversation_id or "",
            response="Request blocked by the prompt injection guardrail.",
            citations=[],
            blocked=True,
            security_events=["prompt_injection"],
            latency_ms=now_ms() - started,
            model="security-layer",
        )

    results = await retrieve(
        session,
        user=user,
        query=payload.message,
        limit=payload.limit,
        mode=payload.retrieval_mode,
        department=payload.department,
        document_id=payload.document_id,
    )
    citations = build_citations(results)
    context = "\n\n".join(_format_context_citation(citation) for citation in citations)
    try:
        response, model = await generate_answer(payload.message, context)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM provider failed: {exc}") from exc
    response = mask_pii(response)
    latency_ms = now_ms() - started
    conversation_id = await save_chat_trace(
        session,
        user=user,
        prompt=payload.message,
        response=response,
        model=model,
        citations=citations,
        conversation_id=payload.conversation_id,
        latency_ms=latency_ms,
    )
    return ChatResponse(
        conversation_id=conversation_id,
        response=response,
        citations=citations,
        security_events=[],
        latency_ms=latency_ms,
        model=model,
    )


@app.post("/api/agents/ticket", response_model=TicketResponse)
async def ticket_agent(payload: TicketRequest) -> TicketResponse:
    issue = payload.issue.lower()
    category = "Network" if any(word in issue for word in ["vpn", "wifi", "network"]) else "IT Support"
    priority = "High" if any(word in issue for word in ["down", "blocked", "urgent"]) else "Medium"
    assignee = "Network Operations" if category == "Network" else "Service Desk"
    return TicketResponse(
        category=category,
        priority=priority,
        assignee=assignee,
        ticket_summary=f"{category} issue reported: {payload.issue.strip()}",
    )


@app.post("/api/agents/email", response_model=EmailClassificationResponse)
async def email_agent(payload: EmailClassificationRequest) -> EmailClassificationResponse:
    content = payload.content.lower()
    if any(word in content for word in ["invoice", "payment", "bank", "receipt"]):
        return EmailClassificationResponse(category="Finance", confidence=0.86)
    if any(word in content for word in ["bug", "help", "issue", "support"]):
        return EmailClassificationResponse(category="Support", confidence=0.82)
    if any(word in content for word in ["buy", "pricing", "demo", "quote"]):
        return EmailClassificationResponse(category="Sales", confidence=0.8)
    if any(word in content for word in ["winner", "crypto", "free money"]):
        return EmailClassificationResponse(category="Spam", confidence=0.9)
    return EmailClassificationResponse(category="Support", confidence=0.55)


@app.post("/api/agents/invoice", response_model=InvoiceExtractionResponse)
async def invoice_agent(file: Annotated[UploadFile, File()]) -> InvoiceExtractionResponse:
    content = await file.read()
    try:
        pages = parse_document(file.filename or "invoice.pdf", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    text_content = "\n".join(text for _, text in pages)
    lines = [line.strip() for line in text_content.splitlines() if line.strip()]
    amount = next((line for line in lines if any(symbol in line for symbol in ["$", "USD", "EUR", "VND"])), "")
    invoice_number = next((line for line in lines if "invoice" in line.lower() and any(char.isdigit() for char in line)), "")
    return InvoiceExtractionResponse(
        vendor=lines[0] if lines else "",
        invoice_number=invoice_number,
        amount=amount,
        currency="USD" if "USD" in amount or "$" in amount else "VND" if "VND" in amount else "",
        invoice_date=next((line for line in lines if "/" in line or "-" in line), ""),
    )


@app.post("/api/agents/github", response_model=GitHubAssistantResponse)
async def github_agent(payload: GitHubAssistantRequest) -> GitHubAssistantResponse:
    issue = payload.issue_description.strip()
    return GitHubAssistantResponse(
        root_cause="Likely missing validation, state handling, or integration coverage around the reported path.",
        suggested_fix=f"Reproduce the issue, add a failing test, then update the smallest affected module. Issue: {issue}",
        pr_draft=(
            "## Summary\n"
            "- Fixes the reported issue with focused validation and error handling\n"
            "- Adds regression coverage\n\n"
            "## Testing\n"
            "- Run backend and frontend test suites"
        ),
    )


@app.post("/api/evaluations")
async def create_evaluation(
    payload: EvaluationRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    evaluation = Evaluation(
        conversation_id=payload.conversation_id,
        score=payload.score,
        comments=payload.comments,
        metrics={
            "answer_relevancy": payload.score,
            "faithfulness": payload.score,
            "context_recall": payload.score,
        },
    )
    session.add(evaluation)
    await session.commit()
    return {"status": "created", "id": evaluation.id}


@app.get("/api/observability/metrics", response_model=MetricsResponse)
async def metrics(session: Annotated[AsyncSession, Depends(get_session)]) -> MetricsResponse:
    async def count(model) -> int:
        return int((await session.execute(select(func.count(model.id)))).scalar_one())

    return MetricsResponse(
        documents=await count(Document),
        chunks=await count(Chunk),
        conversations=await count(Conversation),
        messages=await count(Message),
        audit_logs=await count(AuditLog),
    )
