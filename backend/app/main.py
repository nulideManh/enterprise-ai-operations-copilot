import asyncio
import json
import re
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine, get_session
from app.models import (
    AuditLog,
    Chunk,
    Conversation,
    Document,
    Email,
    Evaluation,
    GitHubIssue,
    Invoice,
    Message,
    Ticket,
)
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


AGENT_LLM_TIMEOUT_SECONDS = 8


async def _call_llm_agent(prompt: str, fallback_dict: dict) -> dict:
    try:
        response_text, model = await asyncio.wait_for(
            generate_answer(prompt, context=""),
            timeout=AGENT_LLM_TIMEOUT_SECONDS,
        )
        if model == "local-fallback":
            return fallback_dict

        cleaned = response_text.strip()
        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1)
        data = json.loads(cleaned)
        for key in fallback_dict:
            if key not in data:
                data[key] = fallback_dict[key]
        return data
    except Exception:
        return fallback_dict


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
async def ticket_agent(
    payload: TicketRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> TicketResponse:
    prompt = (
        f"You are a ticket classification agent. Classify the following IT issue: '{payload.issue}'. "
        "Return a JSON object with keys: "
        "\"category\" (e.g. Network, IT Support, HR, Finance), "
        "\"priority\" (Low, Medium, High, Urgent), "
        "\"assignee\" (e.g. Network Operations, Service Desk, HR Team, Finance Team), "
        "\"ticket_summary\" (a brief professional summary of the issue). "
        "Return ONLY the raw JSON object, no other text."
    )
    issue_lower = payload.issue.lower()
    category = "Network" if any(word in issue_lower for word in ["vpn", "wifi", "network"]) else "IT Support"
    priority = "High" if any(word in issue_lower for word in ["down", "blocked", "urgent"]) else "Medium"
    assignee = "Network Operations" if category == "Network" else "Service Desk"
    fallback = {
        "category": category,
        "priority": priority,
        "assignee": assignee,
        "ticket_summary": f"{category} issue reported: {payload.issue.strip()}"
    }
    result = await _call_llm_agent(prompt, fallback)
    ticket = Ticket(
        user_id=user.id,
        issue=payload.issue,
        category=result["category"],
        priority=result["priority"],
        assignee=result["assignee"],
        status="Open"
    )
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return TicketResponse(
        id=ticket.id,
        category=ticket.category,
        priority=ticket.priority,
        assignee=ticket.assignee,
        ticket_summary=result.get("ticket_summary", ticket.issue)
    )


@app.post("/api/agents/email", response_model=EmailClassificationResponse)
async def email_agent(
    payload: EmailClassificationRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EmailClassificationResponse:
    prompt = (
        f"You are an email classification agent. Classify the following email content: '{payload.content}'. "
        "Return a JSON object with keys: "
        "\"category\" (exactly one of: Sales, Support, Finance, Spam), "
        "\"confidence\" (a float between 0.0 and 1.0 representing classification confidence). "
        "Return ONLY the raw JSON object, no other text."
    )
    content_lower = payload.content.lower()
    category = "Support"
    confidence = 0.55
    if any(word in content_lower for word in ["invoice", "payment", "bank", "receipt"]):
        category, confidence = "Finance", 0.86
    elif any(word in content_lower for word in ["bug", "help", "issue", "support"]):
        category, confidence = "Support", 0.82
    elif any(word in content_lower for word in ["buy", "pricing", "demo", "quote"]):
        category, confidence = "Sales", 0.80
    elif any(word in content_lower for word in ["winner", "crypto", "free money"]):
        category, confidence = "Spam", 0.90
    fallback = {"category": category, "confidence": confidence}
    result = await _call_llm_agent(prompt, fallback)
    email_record = Email(
        sender=payload.sender,
        content=payload.content,
        category=result["category"],
        confidence=result["confidence"]
    )
    session.add(email_record)
    await session.commit()
    await session.refresh(email_record)
    return EmailClassificationResponse(
        id=email_record.id,
        category=email_record.category,
        confidence=email_record.confidence
    )


@app.post("/api/agents/invoice", response_model=InvoiceExtractionResponse)
async def invoice_agent(
    file: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
) -> InvoiceExtractionResponse:
    content = await file.read()
    try:
        pages = parse_document(file.filename or "invoice.pdf", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    text_content = "\n".join(text for _, text in pages)
    prompt = (
        "You are an invoice extraction agent. Extract structured fields from the following invoice text:\n"
        f"'{text_content}'\n\n"
        "Return a JSON object with keys: "
        "\"vendor\" (name of the company issuing the invoice), "
        "\"invoice_number\" (the invoice identifier), "
        "\"amount\" (numeric amount like 1000, 150.50), "
        "\"currency\" (e.g. USD, EUR, VND, etc.), "
        "\"invoice_date\" (the date of the invoice). "
        "Return ONLY the raw JSON object, no other text."
    )
    lines = [line.strip() for line in text_content.splitlines() if line.strip()]
    amount = next((line for line in lines if any(symbol in line for symbol in ["$", "USD", "EUR", "VND"])), "")
    invoice_number = next((line for line in lines if "invoice" in line.lower() and any(char.isdigit() for char in line)), "")
    fallback = {
        "vendor": lines[0] if lines else "Unknown Vendor",
        "invoice_number": invoice_number or "INV-UNKNOWN",
        "amount": amount or "0.0",
        "currency": "USD" if "USD" in amount or "$" in amount else "VND" if "VND" in amount else "VND",
        "invoice_date": next((line for line in lines if "/" in line or "-" in line), "Unknown Date")
    }
    result = await _call_llm_agent(prompt, fallback)
    invoice = Invoice(
        user_id=user.id,
        vendor=result["vendor"],
        invoice_number=result["invoice_number"],
        amount=result["amount"],
        currency=result["currency"],
        invoice_date=result["invoice_date"],
        status="Pending Approval"
    )
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return InvoiceExtractionResponse(
        id=invoice.id,
        vendor=invoice.vendor,
        invoice_number=invoice.invoice_number,
        amount=invoice.amount,
        currency=invoice.currency,
        invoice_date=invoice.invoice_date
    )


@app.post("/api/agents/github", response_model=GitHubAssistantResponse)
async def github_agent(
    payload: GitHubAssistantRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GitHubAssistantResponse:
    prompt = (
        "You are an expert software engineering assistant. Analyze the following GitHub issue description "
        f"and suggest a solution:\n'{payload.issue_description}'\n\n"
        "Return a JSON object with keys: "
        "\"root_cause\" (explanation of why the issue happens), "
        "\"suggested_fix\" (step by step instructions or code to fix it), "
        "\"pr_draft\" (a markdown Pull Request description template). "
        "Return ONLY the raw JSON object, no other text."
    )
    fallback = {
        "root_cause": "Likely missing validation, state handling, or integration coverage around the reported path.",
        "suggested_fix": f"Reproduce the issue, add a failing test, then update the smallest affected module. Issue: {payload.issue_description.strip()}",
        "pr_draft": (
            "## Summary\n"
            "- Fixes the reported issue with focused validation and error handling\n"
            "- Adds regression coverage\n\n"
            "## Testing\n"
            "- Run backend and frontend test suites"
        )
    }
    result = await _call_llm_agent(prompt, fallback)
    gh_issue = GitHubIssue(
        issue_description=payload.issue_description,
        root_cause=result["root_cause"],
        suggested_fix=result["suggested_fix"],
        pr_draft=result["pr_draft"]
    )
    session.add(gh_issue)
    await session.commit()
    await session.refresh(gh_issue)
    return GitHubAssistantResponse(
        id=gh_issue.id,
        root_cause=gh_issue.root_cause,
        suggested_fix=gh_issue.suggested_fix,
        pr_draft=gh_issue.pr_draft
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
        tickets=await count(Ticket),
        emails=await count(Email),
        invoices=await count(Invoice),
        github_issues=await count(GitHubIssue)
    )
