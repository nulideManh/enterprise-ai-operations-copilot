import re

from openai import AsyncOpenAI

from app.core.config import get_settings


settings = get_settings()
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
FINAL_ANSWER_PATTERN = re.compile(r"(?:final answer|answer)\s*:\s*", re.IGNORECASE)
THINKING_MARKER_PATTERN = re.compile(r"^\s*(?:thinking process|reasoning|analysis)\s*:", re.IGNORECASE)
REASONING_HINT_PATTERN = re.compile(
    r"(look for keywords|found in section|text:\s*\"|note\s*:|analyze the request|analyze the context)",
    re.IGNORECASE,
)


def _query_tokens(prompt: str) -> set[str]:
    return {token for token in re.findall(r"[\wÀ-ỹ]+", prompt.lower()) if len(token) > 2}


def _context_fallback_answer(context: str, prompt: str = "") -> str:
    block = re.split(r"\n\n(?:Source|Nguồn):", context.strip(), maxsplit=1)[0]
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if not lines:
        return "Tôi chưa tìm thấy đủ ngữ cảnh tài liệu được phép truy cập để trả lời câu hỏi này."

    source_line = lines[0]
    source = re.sub(r"^(Source|Nguồn):\s*", "", source_line).split("|", 1)[0].strip()
    excerpt = " ".join(lines[1:]).strip()
    if not excerpt:
        excerpt = " ".join(lines).strip()

    query_tokens = _query_tokens(prompt)
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+|\n+", excerpt) if sentence.strip()]
    if query_tokens and sentences:
        ranked = sorted(
            sentences,
            key=lambda sentence: len(query_tokens.intersection(_query_tokens(sentence))),
            reverse=True,
        )
        selected = [sentence for sentence in ranked[:2] if query_tokens.intersection(_query_tokens(sentence))]
        if selected:
            excerpt = " ".join(selected)
    return f"Theo {source}, {excerpt[:700]}"


def _sanitize_answer(answer: str, context: str, prompt: str) -> str:
    clean = THINK_BLOCK_PATTERN.sub("", answer or "").strip()
    final_parts = FINAL_ANSWER_PATTERN.split(clean)
    if len(final_parts) > 1:
        clean = final_parts[-1].strip()
    if THINKING_MARKER_PATTERN.match(clean) or REASONING_HINT_PATTERN.search(clean[:500]):
        return _context_fallback_answer(context, prompt)
    return clean or _context_fallback_answer(context, prompt)


def _messages(prompt: str, context: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Bạn là trợ lý AI vận hành doanh nghiệp. Luôn trả lời bằng tiếng Việt. "
                "Khi có ngữ cảnh, chỉ trả lời dựa trên ngữ cảnh được cung cấp, nêu tên tài liệu nguồn "
                "và giữ câu trả lời ngắn gọn, rõ ràng. Chỉ trả về câu trả lời cuối cùng. "
                "Không tiết lộ chain-of-thought, suy luận ẩn hoặc quá trình suy nghĩ."
            ),
        },
        {"role": "user", "content": f"/no_think\n\nNgữ cảnh:\n{context}\n\nCâu hỏi:\n{prompt}"},
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
    return _sanitize_answer(completion.choices[0].message.content or "", context, prompt), model


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
            "Tôi chưa tìm thấy tài liệu được phép truy cập để trả lời câu hỏi này. Hãy tải lên tài liệu phù hợp hoặc kiểm tra quyền/phòng ban của bạn.",
            "local-fallback",
        )
    return (
        "Dựa trên các tài liệu được phép truy cập, thông tin liên quan nhất là:\n\n"
        f"{context[:1200]}\n\n"
        "Bạn có thể dùng phần trích dẫn bên dưới để kiểm tra nguồn.",
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
