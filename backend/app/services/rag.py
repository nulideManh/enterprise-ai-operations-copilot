import time
from dataclasses import dataclass

from sqlalchemy import func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.chunk import Chunk
from app.models.conversation import Conversation, Message
from app.models.document import Document
from app.models.user import User
from app.schemas.api import Citation
from app.services.document_parser import parse_document, recursive_chunk
from app.services.embeddings import embed_text


@dataclass
class RetrievalResult:
    chunk: Chunk
    document: Document
    score: float | None


def visibility_filter(user: User):
    if user.role.lower() == "admin":
        return true()
    allowed = {user.role.lower(), user.department.lower(), "employee", "public"}
    return or_(
        func.lower(Document.visibility).in_(allowed),
        func.lower(Document.department) == user.department.lower(),
        Document.owner_id == user.id,
    )


async def ingest_upload(
    session: AsyncSession,
    *,
    user: User,
    filename: str,
    content: bytes,
    department: str,
    visibility: str,
) -> tuple[Document, int]:
    pages = parse_document(filename, content)
    document = Document(
        name=filename,
        owner_id=user.id,
        department=department,
        visibility=visibility,
        source_type="upload",
    )
    session.add(document)
    await session.flush()

    created = 0
    for page, text in pages:
        for chunk_text in recursive_chunk(text):
            embedding, _ = await embed_text(chunk_text)
            session.add(
                Chunk(
                    document_id=document.id,
                    content=chunk_text,
                    page=page,
                    token_count=max(1, len(chunk_text.split())),
                    embedding=embedding,
                )
            )
            created += 1

    session.add(
        AuditLog(
            user_id=user.id,
            event_type="document.ingested",
            payload={"document": filename, "chunks": created, "department": department},
        )
    )
    await session.commit()
    await session.refresh(document)
    return document, created


async def retrieve(session: AsyncSession, *, user: User, query: str, limit: int = 5) -> list[RetrievalResult]:
    query_embedding, _ = await embed_text(query)
    distance = Chunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(Chunk, Document, distance.label("distance"))
        .join(Document, Chunk.document_id == Document.id)
        .where(visibility_filter(user))
        .order_by(distance)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        RetrievalResult(
            chunk=chunk,
            document=document,
            score=float(1 - distance_value) if distance_value is not None else None,
        )
        for chunk, document, distance_value in rows
    ]


def build_citations(results: list[RetrievalResult]) -> list[Citation]:
    return [
        Citation(
            document_id=result.document.id,
            document_name=result.document.name,
            page=result.chunk.page,
            department=result.document.department,
            score=result.score,
            excerpt=result.chunk.content[:300],
        )
        for result in results
    ]


async def save_chat_trace(
    session: AsyncSession,
    *,
    user: User,
    prompt: str,
    response: str,
    model: str,
    citations: list[Citation],
    conversation_id: str | None,
    latency_ms: int,
) -> str:
    conversation = None
    if conversation_id:
        conversation = await session.get(Conversation, conversation_id)
    if not conversation:
        conversation = Conversation(user_id=user.id, title=prompt[:80])
        session.add(conversation)
        await session.flush()

    message = Message(
        conversation_id=conversation.id,
        prompt=prompt,
        response=response,
        model=model,
        prompt_tokens=max(1, len(prompt.split())),
        completion_tokens=max(1, len(response.split())),
        retrieved_context={"citations": [citation.model_dump() for citation in citations]},
        latency_ms=latency_ms,
    )
    session.add(message)
    session.add(
        AuditLog(
            user_id=user.id,
            event_type="chat.completed",
            payload={
                "conversation_id": conversation.id,
                "prompt": prompt,
                "retrieved_docs": [citation.document_name for citation in citations],
                "latency_ms": latency_ms,
            },
        )
    )
    await session.commit()
    return conversation.id


def now_ms() -> int:
    return int(time.perf_counter() * 1000)
