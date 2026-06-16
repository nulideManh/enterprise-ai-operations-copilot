# Enterprise AI Operations Copilot

A production-grade AI platform demonstrating:

* Enterprise RAG
* Multi-agent workflows
* AI observability
* AI security & guardrails
* Evaluation dashboard
* RBAC & document permissions

---

# Goal

Build a portfolio project that showcases end-to-end AI Product Engineering skills:

* AI Application Development
* Retrieval-Augmented Generation (RAG)
* Agentic Workflows
* AI Security
* AI Observability
* Full-stack Development
* Production Architecture

---

# Tech Stack

## Frontend

* Next.js
* TypeScript
* TailwindCSS
* shadcn/ui

## Backend

* FastAPI
* Python 3.12+

## AI

* OpenAI API
* LangGraph
* LlamaIndex

## Database

* PostgreSQL
* pgvector

## Observability

* Langfuse

## Security

* Microsoft Presidio
* Llama Guard

## Deployment

* Docker
* Railway / VPS

---

# Current Implementation

This repository now includes a runnable first phase:

* FastAPI backend with document upload, parsing, recursive chunking, embeddings, RAG retrieval, RBAC filtering, chat traces, audit logs, evaluations, and workflow agent endpoints
* Next.js + TypeScript + TailwindCSS frontend for RAG chat, document ingestion, user role switching, agent demos, and observability metrics
* PostgreSQL + pgvector database schema bootstrapped by the backend on startup
* Docker Compose packaging for frontend, backend, and database

The AI layer works without external credentials by using a deterministic local embedding fallback and a local answer fallback. Add `OPENAI_API_KEY` to enable OpenAI embeddings and chat generation.

---

# Quick Start

## Docker

```bash
cp .env.example .env
docker compose up --build
```

Open:

* Frontend: http://localhost:3000
* Backend API docs: http://localhost:8000/docs
* Healthcheck: http://localhost:8000/health

If your Docker installation uses the legacy Compose binary:

```bash
docker-compose up --build
```

## Local Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Local Frontend

```bash
cd frontend
npm install
npm run dev
```

Set the frontend API target when needed:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## API User Context

The backend uses headers for the portfolio RBAC demo:

* `X-User-Email`
* `X-User-Role`: `Admin`, `Manager`, or `Employee`
* `X-User-Department`: `Engineering`, `HR`, `Finance`, or `Operations`

Uploaded documents include `department` and `visibility`, and retrieval only returns authorized chunks.

---

# System Architecture

User
↓
Frontend (NextJS)
↓
FastAPI Backend
↓
RAG Layer
↓
Agent Layer
↓
Security Layer
↓
LLM
↓
Observability
↓
Response

---

# Module 1: Enterprise RAG

## Features

### Document Upload

Supported formats:

* PDF
* DOCX
* PPTX

### Parsing

* Unstructured
* LlamaParse (optional)

### Chunking

Implement:

* Recursive Chunking
* Semantic Chunking

### Embeddings

Choose one:

* text-embedding-3-large
* BGE-M3
* E5-large

### Vector Database

* PostgreSQL + pgvector

### Retrieval

Implement:

* Similarity Search
* Hybrid Search
* Metadata Filtering

### Citation Support

Example:

According to HR Policy...

Source:
HR_Policy.pdf - Page 12

### Access Control

Document visibility:

* Admin
* HR
* Engineering
* Finance

Users should only retrieve documents they are authorized to access.

---

# Module 2: AI Workflow Agents

## Agent 1: Ticket Agent

Input:

"My VPN is not working."

Workflow:

Classify Issue
↓
Create Jira Ticket
↓
Assign Team
↓
Generate Summary

Output:

* Category
* Priority
* Assignee
* Ticket Summary

---

## Agent 2: Invoice Extraction Agent

Input:

invoice.pdf

Workflow:

OCR
↓
Extract Fields
↓
Validate

Output:

{
"vendor": "",
"invoice_number": "",
"amount": "",
"currency": "",
"invoice_date": ""
}

---

## Agent 3: Email Classification Agent

Input:

Email content

Output:

* Sales
* Support
* Finance
* Spam

---

## Agent 4: GitHub Assistant Agent

Input:

Issue description

Workflow:

Analyze Issue
↓
Generate Solution
↓
Generate PR Description

Output:

* Root Cause
* Suggested Fix
* PR Draft

---

# Module 3: AI Observability

## Prompt Tracing

Store:

* User Prompt
* System Prompt
* Retrieved Context
* Model
* Response

---

## Cost Tracking

Metrics:

* Cost per User
* Cost per Agent
* Cost per Model
* Daily Cost
* Monthly Cost

---

## Latency Tracking

Track:

* Retrieval Time
* LLM Time
* Tool Time
* Total Time

---

## Analytics Dashboard

Display:

* Most Queried Documents
* Most Used Agents
* Top Users
* Token Usage

---

# Module 4: AI Security Layer

## Prompt Injection Detection

Detect:

* Ignore previous instructions
* Reveal system prompt
* Developer mode attacks
* Context poisoning

Actions:

* Block
* Flag
* Log

---

## PII Detection

Detect:

* Email
* Phone Number
* National ID
* Bank Account

Mask before response.

Example:

0912345678

↓

091*****78

---

## Output Moderation

Check for:

* Toxic Content
* Harmful Content
* Unsafe Output

---

## RBAC

Roles:

* Admin
* Manager
* Employee

Permissions:

Role
↓
Documents
↓
Agents
↓
Actions

---

## Audit Logs

Store:

* User
* Timestamp
* Prompt
* Retrieved Docs
* Output
* Security Events

---

# Module 5: Evaluation Dashboard

## Human Feedback

Thumbs Up
Thumbs Down

Store:

* Feedback
* User Comment

---

## RAG Evaluation

Metrics:

* Context Recall
* Answer Relevancy
* Faithfulness

---

## Hallucination Detection

Pipeline:

Answer
↓
Judge Model
↓
Confidence Score

Store evaluation results.

---

# Database Design

## Users

* id
* email
* role

## Documents

* id
* name
* owner
* department

## Chunks

* id
* document_id
* content
* embedding

## Conversations

* id
* user_id

## Messages

* id
* conversation_id
* prompt
* response

## AuditLogs

* id
* user_id
* event_type
* payload

## Evaluations

* id
* conversation_id
* score
* comments

---

# Project Roadmap

## Phase 1

Core RAG

* Upload files
* Chunking
* Embeddings
* Retrieval
* Citations

Goal:
Enterprise Chat with Documents

---

## Phase 2

Permissions

* Authentication
* RBAC
* Metadata filtering

Goal:
Secure Enterprise RAG

---

## Phase 3

Agents

* Ticket Agent
* Email Agent
* Invoice Agent

Goal:
Workflow Automation

---

## Phase 4

Observability

* Langfuse
* Cost Dashboard
* Latency Dashboard

Goal:
Production Monitoring

---

## Phase 5

Security

* PII Detection
* Prompt Injection Detection
* Audit Logs

Goal:
Enterprise Readiness

---

## Phase 6

Evaluation

* Human Feedback
* RAG Metrics
* Hallucination Detection

Goal:
AI Quality Assurance

---

# Portfolio Outcomes

After completion this project demonstrates:

✓ Enterprise RAG

✓ Vector Search

✓ Embeddings

✓ Citations

✓ RBAC

✓ Agent Workflows

✓ Tool Calling

✓ OCR Pipelines

✓ AI Security

✓ AI Observability

✓ Evaluation Frameworks

✓ Production-grade Architecture

✓ Full-stack AI Engineering

This project should be treated as a mini enterprise AI platform rather than a simple chatbot.
