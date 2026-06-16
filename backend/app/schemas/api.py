from pydantic import BaseModel, Field


class Citation(BaseModel):
    document_id: str
    document_name: str
    page: int | None = None
    department: str
    score: float | None = None
    excerpt: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None


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


class TicketRequest(BaseModel):
    issue: str = Field(min_length=1)


class TicketResponse(BaseModel):
    category: str
    priority: str
    assignee: str
    ticket_summary: str


class EmailClassificationRequest(BaseModel):
    content: str = Field(min_length=1)


class EmailClassificationResponse(BaseModel):
    category: str
    confidence: float


class InvoiceExtractionResponse(BaseModel):
    vendor: str
    invoice_number: str
    amount: str
    currency: str
    invoice_date: str


class GitHubAssistantRequest(BaseModel):
    issue_description: str = Field(min_length=1)


class GitHubAssistantResponse(BaseModel):
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
