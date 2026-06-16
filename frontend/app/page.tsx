"use client";

import { Activity, Bot, FileText, RefreshCw, Send, Shield, Upload } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { apiFetch, type UserContext } from "@/lib/api";
import { Button, GhostButton, Input, Panel, Select, Textarea } from "@/components/ui";

type DocumentItem = {
  id: string;
  name: string;
  department: string;
  visibility: string;
  chunks: number;
  chunking_strategy: string;
};

type Citation = {
  document_name: string;
  chunk_id: string;
  page: number | null;
  department: string;
  score: number | null;
  vector_score: number | null;
  keyword_score: number | null;
  retrieval_method: string;
  excerpt: string;
};

type ChatResponse = {
  conversation_id: string;
  response: string;
  citations: Citation[];
  blocked: boolean;
  security_events: string[];
  latency_ms: number;
  model: string;
};

type Metrics = {
  documents: number;
  chunks: number;
  conversations: number;
  messages: number;
  audit_logs: number;
  tickets: number;
  emails: number;
  invoices: number;
  github_issues: number;
};

type TicketResponse = {
  id?: string | null;
  category: string;
  priority: string;
  assignee: string;
  ticket_summary: string;
};

type EmailResponse = {
  id?: string | null;
  category: string;
  confidence: number;
};

const departments = ["Engineering", "HR", "Finance", "Operations"];
const roles = ["Admin", "Manager", "Employee"];

export default function Home() {
  const [user, setUser] = useState<UserContext>({
    email: "admin@example.com",
    role: "Admin",
    department: "Engineering"
  });
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadDepartment, setUploadDepartment] = useState("Engineering");
  const [uploadVisibility, setUploadVisibility] = useState("Employee");
  const [chunkingStrategy, setChunkingStrategy] = useState("semantic");
  const [query, setQuery] = useState("Chính sách nghỉ phép năm của nhân viên là gì?");
  const [retrievalMode, setRetrievalMode] = useState("hybrid");
  const [retrievalDepartment, setRetrievalDepartment] = useState("");
  const [retrievalLimit, setRetrievalLimit] = useState(5);
  const [chat, setChat] = useState<ChatResponse | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [ticketIssue, setTicketIssue] = useState("VPN của tôi không kết nối được.");
  const [ticketResult, setTicketResult] = useState<TicketResponse | null>(null);
  const [emailContent, setEmailContent] = useState("Bạn có thể gửi báo giá cho gói doanh nghiệp không?");
  const [emailResult, setEmailResult] = useState<EmailResponse | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const metricItems = useMemo(
    () => [
      ["Tài liệu", metrics?.documents ?? 0],
      ["Đoạn", metrics?.chunks ?? 0],
      ["Hội thoại", metrics?.conversations ?? 0],
      ["Tin nhắn", metrics?.messages ?? 0],
      ["Audit log", metrics?.audit_logs ?? 0],
      ["Ticket", metrics?.tickets ?? 0],
      ["Emails", metrics?.emails ?? 0],
      ["Hóa đơn", metrics?.invoices ?? 0],
      ["GitHub issue", metrics?.github_issues ?? 0]
    ],
    [metrics]
  );

  async function refresh() {
    const [docs, nextMetrics] = await Promise.all([
      apiFetch<DocumentItem[]>("/api/documents", user),
      apiFetch<Metrics>("/api/observability/metrics", user)
    ]);
    setDocuments(docs);
    setMetrics(nextMetrics);
  }

  useEffect(() => {
    refresh().catch((error) => setStatus(error.message));
  }, [user.email, user.role, user.department]);

  async function onUpload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setStatus("Đang tải lên tài liệu");
    const body = new FormData();
    body.set("file", file);
    body.set("department", uploadDepartment);
    body.set("visibility", uploadVisibility);
    body.set("chunking_strategy", chunkingStrategy);
    try {
      await apiFetch<DocumentItem>("/api/documents", user, { method: "POST", body });
      setFile(null);
      setStatus("Tài liệu đã được lập chỉ mục");
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Tải tài liệu thất bại");
    } finally {
      setBusy(false);
    }
  }

  async function onChat(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setStatus("Đang truy xuất tài liệu");
    try {
      const result = await apiFetch<ChatResponse>("/api/chat", user, {
        method: "POST",
        body: JSON.stringify({
          message: query,
          conversation_id: conversationId,
          retrieval_mode: retrievalMode,
          department: retrievalDepartment || null,
          limit: retrievalLimit
        })
      });
      setChat(result);
      setConversationId(result.conversation_id || null);
      setStatus(result.blocked ? "Bị chặn bởi guardrail" : "Đã tạo câu trả lời");
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Chat thất bại");
    } finally {
      setBusy(false);
    }
  }

  async function runTicketAgent() {
    setBusy(true);
    try {
      const result = await apiFetch<TicketResponse>("/api/agents/ticket", user, {
        method: "POST",
        body: JSON.stringify({ issue: ticketIssue })
      });
      setTicketResult(result);
      setStatus("Ticket agent đã hoàn tất");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Ticket agent thất bại");
    } finally {
      setBusy(false);
    }
  }

  async function runEmailAgent() {
    setBusy(true);
    try {
      const result = await apiFetch<EmailResponse>("/api/agents/email", user, {
        method: "POST",
        body: JSON.stringify({ content: emailContent })
      });
      setEmailResult(result);
      setStatus("Email agent đã hoàn tất");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Email agent thất bại");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-normal text-ink">Enterprise AI Operations Copilot</h1>
            <p className="mt-1 text-sm text-muted">RAG, agent, guardrail, RBAC và observability trong một workspace.</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 md:w-[620px]">
            <Input value={user.email} onChange={(event) => setUser({ ...user, email: event.target.value })} aria-label="Email" />
            <Select value={user.role} onChange={(event) => setUser({ ...user, role: event.target.value })} aria-label="Role">
              {roles.map((role) => (
                <option key={role}>{role}</option>
              ))}
            </Select>
            <Select
              value={user.department}
              onChange={(event) => setUser({ ...user, department: event.target.value })}
              aria-label="Department"
            >
              {departments.map((department) => (
                <option key={department}>{department}</option>
              ))}
            </Select>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-4 px-4 py-5 lg:grid-cols-[1.3fr_0.7fr]">
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-5">
            {metricItems.map(([label, value]) => (
              <Panel key={label} className="rounded-lg px-3 py-3">
                <div className="text-xs font-medium uppercase text-muted">{label}</div>
                <div className="mt-1 text-2xl font-semibold text-ink">{value}</div>
              </Panel>
            ))}
          </div>

          <Panel className="rounded-lg">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                <FileText size={18} /> RAG doanh nghiệp
              </div>
              <GhostButton onClick={() => refresh().catch((error) => setStatus(error.message))}>
                <RefreshCw size={16} /> Làm mới
              </GhostButton>
            </div>
            <div className="grid gap-4 p-4 lg:grid-cols-[0.8fr_1.2fr]">
              <form onSubmit={onUpload} className="space-y-3">
                <Input type="file" accept=".pdf,.docx,.pptx" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
                <div className="grid grid-cols-2 gap-3">
                  <Select value={uploadDepartment} onChange={(event) => setUploadDepartment(event.target.value)}>
                    {departments.map((department) => (
                      <option key={department}>{department}</option>
                    ))}
                  </Select>
                  <Select value={uploadVisibility} onChange={(event) => setUploadVisibility(event.target.value)}>
                    {["Admin", "Manager", "Employee", "Public", ...departments].map((visibility) => (
                      <option key={visibility}>{visibility}</option>
                    ))}
                  </Select>
                </div>
                <Select value={chunkingStrategy} onChange={(event) => setChunkingStrategy(event.target.value)}>
                  <option value="semantic">Chia đoạn semantic</option>
                  <option value="recursive">Chia đoạn recursive</option>
                </Select>
                <Button type="submit" disabled={!file || busy}>
                  <Upload size={16} /> Tải lên
                </Button>
              </form>

              <div className="max-h-56 overflow-auto rounded-md border border-line">
                <table className="w-full border-collapse text-left text-sm">
                  <thead className="bg-[#edf0f4] text-xs uppercase text-muted">
                    <tr>
                      <th className="px-3 py-2">Tài liệu</th>
                      <th className="px-3 py-2">Phòng ban</th>
                      <th className="px-3 py-2">Quyền xem</th>
                      <th className="px-3 py-2">Đoạn</th>
                      <th className="px-3 py-2">Kiểu chia đoạn</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((document) => (
                      <tr key={document.id} className="border-t border-line">
                        <td className="px-3 py-2 font-medium text-ink">{document.name}</td>
                        <td className="px-3 py-2 text-muted">{document.department}</td>
                        <td className="px-3 py-2 text-muted">{document.visibility}</td>
                        <td className="px-3 py-2 text-muted">{document.chunks}</td>
                        <td className="px-3 py-2 text-muted">{document.chunking_strategy}</td>
                      </tr>
                    ))}
                    {documents.length === 0 && (
                      <tr>
                        <td className="px-3 py-8 text-center text-muted" colSpan={5}>
                          Chưa có tài liệu được lập chỉ mục
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </Panel>

          <Panel className="rounded-lg">
            <div className="flex items-center gap-2 border-b border-line px-4 py-3 text-sm font-semibold text-ink">
              <Shield size={18} /> Chat bảo mật
            </div>
            <div className="grid gap-4 p-4 lg:grid-cols-[0.9fr_1.1fr]">
              <form onSubmit={onChat} className="space-y-3">
                <Textarea value={query} onChange={(event) => setQuery(event.target.value)} />
                <div className="grid gap-3 sm:grid-cols-3">
                  <Select value={retrievalMode} onChange={(event) => setRetrievalMode(event.target.value)}>
                    <option value="hybrid">Tìm kiếm hybrid</option>
                    <option value="similarity">Tìm kiếm similarity</option>
                  </Select>
                  <Select value={retrievalDepartment} onChange={(event) => setRetrievalDepartment(event.target.value)}>
                    <option value="">Tất cả phòng ban</option>
                    {departments.map((department) => (
                      <option key={department}>{department}</option>
                    ))}
                  </Select>
                  <Input
                    aria-label="Số trích dẫn"
                    min={1}
                    max={12}
                    type="number"
                    value={retrievalLimit}
                    onChange={(event) => {
                      const value = Number(event.target.value);
                      setRetrievalLimit(Number.isFinite(value) ? Math.min(12, Math.max(1, value)) : 5);
                    }}
                  />
                </div>
                <Button type="submit" disabled={busy || !query.trim()}>
                  <Send size={16} /> Gửi
                </Button>
              </form>
              <div className="min-h-52 rounded-md border border-line bg-[#fbfcfe] p-3 text-sm">
                {chat ? (
                  <div className="space-y-3">
                    <div className="flex flex-wrap gap-2 text-xs text-muted">
                      <span>{chat.model}</span>
                      <span>{chat.latency_ms} ms</span>
                      {chat.blocked && <span className="font-semibold text-danger">đã chặn</span>}
                    </div>
                    <p className="whitespace-pre-wrap leading-6 text-ink">{chat.response}</p>
                    <div className="space-y-2">
                      {chat.citations.map((citation, index) => (
                        <div key={`${citation.chunk_id}-${index}`} className="rounded-md border border-line bg-white p-2">
                          <div className="text-xs font-semibold text-ink">
                            {citation.document_name} {citation.page ? `- trang ${citation.page}` : ""}
                          </div>
                          <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-muted">
                            <span>{citation.retrieval_method}</span>
                            {citation.score !== null && <span>điểm {citation.score.toFixed(3)}</span>}
                            {citation.vector_score !== null && <span>vector {citation.vector_score.toFixed(3)}</span>}
                            {citation.keyword_score !== null && <span>keyword {citation.keyword_score.toFixed(3)}</span>}
                          </div>
                          <p className="mt-1 line-clamp-3 text-xs leading-5 text-muted">{citation.excerpt}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="flex h-full items-center justify-center text-muted">Chưa có câu trả lời</div>
                )}
              </div>
            </div>
          </Panel>
        </div>

        <aside className="space-y-4">
          <Panel className="rounded-lg">
            <div className="flex items-center gap-2 border-b border-line px-4 py-3 text-sm font-semibold text-ink">
              <Bot size={18} /> Workflow Agents
            </div>
            <div className="space-y-4 p-4">
              <div className="space-y-2">
                <Textarea value={ticketIssue} onChange={(event) => setTicketIssue(event.target.value)} />
                <Button onClick={runTicketAgent} disabled={busy}>
                  <Bot size={16} /> Ticket
                </Button>
                {ticketResult && (
                  <div className="rounded-md border border-line bg-[#fbfcfe] p-3 text-sm text-ink">
                    <div>{ticketResult.category} / {ticketResult.priority}</div>
                    <div className="text-muted">{ticketResult.assignee}</div>
                    <div className="mt-2">{ticketResult.ticket_summary}</div>
                  </div>
                )}
              </div>

              <div className="space-y-2 border-t border-line pt-4">
                <Textarea value={emailContent} onChange={(event) => setEmailContent(event.target.value)} />
                <Button onClick={runEmailAgent} disabled={busy}>
                  <Bot size={16} /> Email
                </Button>
                {emailResult && (
                  <div className="rounded-md border border-line bg-[#fbfcfe] p-3 text-sm text-ink">
                    {emailResult.category} - {Math.round(emailResult.confidence * 100)}%
                  </div>
                )}
              </div>
            </div>
          </Panel>

          <Panel className="rounded-lg">
            <div className="flex items-center gap-2 border-b border-line px-4 py-3 text-sm font-semibold text-ink">
              <Activity size={18} /> Runtime
            </div>
            <div className="space-y-3 p-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted">API</span>
                <span className="font-medium text-ink">FastAPI</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">Database</span>
                <span className="font-medium text-ink">PostgreSQL + pgvector</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">Security</span>
                <span className="font-medium text-ink">Guardrails active</span>
              </div>
              <div className="rounded-md border border-line bg-[#fbfcfe] p-3 text-muted">{status || "Ready"}</div>
            </div>
          </Panel>
        </aside>
      </div>
    </main>
  );
}
