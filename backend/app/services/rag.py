import time
from dataclasses import dataclass
import re

from sqlalchemy import and_, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.chunk import Chunk
from app.models.conversation import Conversation, Message
from app.models.document import Document
from app.models.user import User
from app.schemas.api import Citation
from app.services.document_parser import chunk_text, parse_document
from app.services.embeddings import embed_text


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


@dataclass
class RetrievalResult:
    chunk: Chunk
    document: Document
    score: float | None
    vector_score: float | None = None
    keyword_score: float | None = None
    retrieval_method: str = "similarity"


def visibility_filter(user: User):
    if user.role.lower() == "admin":
        return true()
    allowed = {user.role.lower(), user.department.lower(), "employee", "public"}
    return or_(
        func.lower(Document.visibility).in_(allowed),
        func.lower(Document.department) == user.department.lower(),
        Document.owner_id == user.id,
    )


def _metadata_filters(user: User, department: str | None = None, document_id: str | None = None):
    filters = [visibility_filter(user)]
    if department:
        filters.append(func.lower(Document.department) == department.lower())
    if document_id:
        filters.append(Document.id == document_id)
    return and_(*filters)


def _tokenize(text: str) -> set[str]:
    return {token for token in TOKEN_PATTERN.findall(text.lower()) if len(token) > 2}


def _keyword_score(query: str, content: str) -> float:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0
    content_tokens = _tokenize(content)
    if not content_tokens:
        return 0.0
    overlap = query_tokens.intersection(content_tokens)
    coverage = len(overlap) / len(query_tokens)
    density = len(overlap) / max(len(content_tokens), 1)
    phrase_bonus = 0.15 if query.lower() in content.lower() else 0.0
    return min(1.0, coverage * 0.8 + density * 0.2 + phrase_bonus)


async def ingest_upload(
    session: AsyncSession,
    *,
    user: User,
    filename: str,
    content: bytes,
    department: str,
    visibility: str,
    chunking_strategy: str = "recursive",
) -> tuple[Document, int]:
    pages = parse_document(filename, content)
    document = Document(
        name=filename,
        owner_id=user.id,
        department=department,
        visibility=visibility,
        source_type="upload",
        chunking_strategy=chunking_strategy,
    )
    session.add(document)
    await session.flush()

    created = 0
    for page, text in pages:
        for chunk_content in chunk_text(text, chunking_strategy):
            embedding, _ = await embed_text(chunk_content)
            session.add(
                Chunk(
                    document_id=document.id,
                    content=chunk_content,
                    page=page,
                    token_count=max(1, len(chunk_content.split())),
                    embedding=embedding,
                )
            )
            created += 1

    session.add(
        AuditLog(
            user_id=user.id,
            event_type="document.ingested",
            payload={
                "document": filename,
                "chunks": created,
                "department": department,
                "chunking_strategy": chunking_strategy,
            },
        )
    )
    await session.commit()
    await session.refresh(document)
    return document, created


async def retrieve(
    session: AsyncSession,
    *,
    user: User,
    query: str,
    limit: int = 5,
    mode: str = "hybrid",
    department: str | None = None,
    document_id: str | None = None,
) -> list[RetrievalResult]:
    query_embedding, _ = await embed_text(query)
    distance = Chunk.embedding.cosine_distance(query_embedding)
    candidate_limit = max(limit * 4, 20) if mode == "hybrid" else limit
    stmt = (
        select(Chunk, Document, distance.label("distance"))
        .join(Document, Chunk.document_id == Document.id)
        .where(_metadata_filters(user, department=department, document_id=document_id))
        .order_by(distance)
        .limit(candidate_limit)
    )
    rows = (await session.execute(stmt)).all()
    results = []
    for chunk, document, distance_value in rows:
        vector_score = float(1 - distance_value) if distance_value is not None else None
        keyword_score = _keyword_score(query, chunk.content) if mode == "hybrid" else None
        if mode == "hybrid":
            combined = ((vector_score or 0) * 0.72) + ((keyword_score or 0) * 0.28)
        else:
            combined = vector_score
        results.append(
            RetrievalResult(
                chunk=chunk,
                document=document,
                score=combined,
                vector_score=vector_score,
                keyword_score=keyword_score,
                retrieval_method=mode,
            )
        )
    results.sort(key=lambda result: result.score or 0, reverse=True)
    return results[:limit]


def build_citations(results: list[RetrievalResult]) -> list[Citation]:
    return [
        Citation(
            document_id=result.document.id,
            document_name=result.document.name,
            chunk_id=result.chunk.id,
            page=result.chunk.page,
            department=result.document.department,
            score=result.score,
            vector_score=result.vector_score,
            keyword_score=result.keyword_score,
            retrieval_method=result.retrieval_method,
            excerpt=result.chunk.content[:800],
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
