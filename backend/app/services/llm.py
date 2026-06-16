import re

from openai import AsyncOpenAI

from app.core.config import get_settings


settings = get_settings()
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
FINAL_ANSWER_PATTERN = re.compile(r"(?:final answer|answer)\s*:\s*", re.IGNORECASE)
THINKING_MARKER_PATTERN = re.compile(r"^\s*(?:thinking process|reasoning|analysis)\s*:", re.IGNORECASE)


def _context_fallback_answer(context: str) -> str:
    block = context.strip().split("\n\nSource:", 1)[0]
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if not lines:
        return "I could not find enough authorized context to answer this."

    source_line = lines[0]
    source = source_line.removeprefix("Source:").split("|", 1)[0].strip()
    excerpt = " ".join(lines[1:]).strip()
    if not excerpt:
        excerpt = " ".join(lines).strip()
    return f"Based on {source}, {excerpt[:700]}"


def _sanitize_answer(answer: str, context: str) -> str:
    clean = THINK_BLOCK_PATTERN.sub("", answer or "").strip()
    final_parts = FINAL_ANSWER_PATTERN.split(clean)
    if len(final_parts) > 1:
        clean = final_parts[-1].strip()
    if THINKING_MARKER_PATTERN.match(clean):
        return _context_fallback_answer(context)
    return clean or _context_fallback_answer(context)


def _messages(prompt: str, context: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are an enterprise AI operations copilot. Answer only from the provided "
                "context when possible, cite document names, and be concise. "
                "Return only the final answer. Do not reveal chain-of-thought, hidden reasoning, "
                "or a thinking process."
            ),
        },
        {"role": "user", "content": f"/no_think\n\nContext:\n{context}\n\nQuestion:\n{prompt}"},
    ]


async def _chat_with_client(
    *,
    client: AsyncOpenAI,
    model: str,
    prompt: str,
    context: str,
) -> tuple[str, str]:
    completion = await client.chat.completions.create(
        model=model,
        messages=_messages(prompt, context),
        max_tokens=settings.llm_max_tokens,
    )
    return _sanitize_answer(completion.choices[0].message.content or "", context), model


async def generate_answer(prompt: str, context: str) -> tuple[str, str]:
    provider = settings.llm_provider.lower()

    if settings.local_llm_base_url and provider in {"auto", "local"}:
        try:
            client = AsyncOpenAI(
                api_key=settings.local_llm_api_key,
                base_url=settings.local_llm_base_url.rstrip("/"),
            )
            return await _chat_with_client(
                client=client,
                model=settings.local_chat_model,
                prompt=prompt,
                context=context,
            )
        except Exception:
            if provider == "local":
                raise

    if settings.openai_api_key and provider in {"auto", "openai"}:
        try:
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            return await _chat_with_client(
                client=client,
                model=settings.chat_model,
                prompt=prompt,
                context=context,
            )
        except Exception:
            if provider == "openai":
                raise

    if not context.strip():
        return (
            "I could not find an authorized document that answers this. Upload a relevant document or check your role/department access.",
            "local-fallback",
        )
    return (
        "Based on the authorized documents, the most relevant information is:\n\n"
        f"{context[:1200]}\n\n"
        "Use the citations below to verify the source.",
        "local-fallback",
    )


async def list_local_models() -> list[str]:
    if not settings.local_llm_base_url:
        return []
    client = AsyncOpenAI(
        api_key=settings.local_llm_api_key,
        base_url=settings.local_llm_base_url.rstrip("/"),
    )
    models = await client.models.list()
    return [model.id for model in models.data]
