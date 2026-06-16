import re


INJECTION_PATTERNS = [
    re.compile(r"ignore (all )?(previous|prior) instructions", re.IGNORECASE),
    re.compile(r"reveal (the )?(system|developer) prompt", re.IGNORECASE),
    re.compile(r"developer mode", re.IGNORECASE),
    re.compile(r"you are now unrestricted", re.IGNORECASE),
    re.compile(r"context poisoning", re.IGNORECASE),
]

PII_PATTERNS = [
    re.compile(r"(?P<email>[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.IGNORECASE),
    re.compile(r"(?P<phone>(?:\+?\d[\s.-]?){9,14}\d)"),
    re.compile(r"(?P<bank>\b\d{10,16}\b)"),
]


def detect_prompt_injection(text: str) -> list[str]:
    return [pattern.pattern for pattern in INJECTION_PATTERNS if pattern.search(text)]


def mask_pii(text: str) -> str:
    def mask_email(match: re.Match[str]) -> str:
        value = match.group("email")
        name, domain = value.split("@", 1)
        return f"{name[:2]}***@{domain}"

    def mask_number(match: re.Match[str]) -> str:
        value = match.group(0)
        digits = re.sub(r"\D", "", value)
        if len(digits) < 8:
            return value
        return f"{digits[:3]}*****{digits[-2:]}"

    masked = PII_PATTERNS[0].sub(mask_email, text)
    masked = PII_PATTERNS[1].sub(mask_number, masked)
    masked = PII_PATTERNS[2].sub(mask_number, masked)
    return masked
