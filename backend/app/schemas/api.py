from pydantic import BaseModel, Field


class Citation(BaseModel):
    document_id: str
    document_name: str
    chunk_id: str
    page: int | None = None
    department: str
    score: float | None = None
    vector_score: float | None = None
    keyword_score: float | None = None
    retrieval_method: str = "similarity"
    excerpt: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    retrieval_mode: str = Field(default="hybrid", pattern="^(similarity|hybrid)$")
    department: str | None = None
    document_id: str | None = None
    limit: int = Field(default=5, ge=1, le=12)


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    citations: list[Citation]
    blocked: bool = False
    security_events: list[str] = []
    latency_ms: int
    model: str


class DocumentResponse(BaseModel):
    id: str
    name: str
    department: str
    visibility: str
    chunks: int
    chunking_strategy: str = "recursive"


class TicketRequest(BaseModel):
    issue: str = Field(min_length=1)


class TicketResponse(BaseModel):
    id: str | None = None
    category: str
    priority: str
    assignee: str
    ticket_summary: str


class EmailClassificationRequest(BaseModel):
    sender: str = Field(default="customer@example.com")
    content: str = Field(min_length=1)


class EmailClassificationResponse(BaseModel):
    id: str | None = None
    category: str
    confidence: float


class InvoiceExtractionResponse(BaseModel):
    id: str | None = None
    vendor: str
    invoice_number: str
    amount: str
    currency: str
    invoice_date: str


class GitHubAssistantRequest(BaseModel):
    issue_description: str = Field(min_length=1)


class GitHubAssistantResponse(BaseModel):
    id: str | None = None
    root_cause: str
    suggested_fix: str
    pr_draft: str


class EvaluationRequest(BaseModel):
    conversation_id: str
    score: float = Field(ge=0, le=1)
    comments: str = ""


class MetricsResponse(BaseModel):
    documents: int
    chunks: int
    conversations: int
    messages: int
    audit_logs: int
    tickets: int
    emails: int
    invoices: int
    github_issues: int
