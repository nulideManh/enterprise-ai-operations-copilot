import asyncio
import os
import sys

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal, engine
from app.db.base import Base
from app.models import User, Ticket, Email, Invoice, GitHubIssue, AuditLog, Conversation, Message, Evaluation
from app.services.rag import ingest_upload

async def seed():
    # Setup tables first
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        print("Starting database seeding...")
        
        # 1. Create or get Users
        users_data = [
            {"email": "admin@example.com", "role": "Admin", "department": "Engineering"},
            {"email": "hr_mgr@example.com", "role": "Manager", "department": "HR"},
            {"email": "finance_emp@example.com", "role": "Employee", "department": "Finance"},
            {"email": "ops_emp@example.com", "role": "Employee", "department": "Operations"},
        ]
        
        users = {}
        for u_data in users_data:
            stmt = select(User).where(User.email == u_data["email"])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                user = User(
                    email=u_data["email"],
                    role=u_data["role"],
                    department=u_data["department"]
                )
                session.add(user)
                await session.flush()
                users[u_data["email"]] = user
                print(f"Created user: {u_data['email']}")
            else:
                users[u_data["email"]] = existing
                print(f"User already exists: {u_data['email']}")
                
        # 2. Ingest Sample Documents
        sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../sample_documents"))
        if os.path.exists(sample_dir):
            docs_to_ingest = [
                {
                    "filename": "hr_policy.docx",
                    "user_email": "hr_mgr@example.com",
                    "department": "HR",
                    "visibility": "Employee",
                },
                {
                    "filename": "it_security_guide.pptx",
                    "user_email": "admin@example.com",
                    "department": "Engineering",
                    "visibility": "Employee",
                },
                {
                    "filename": "finance_instructions.docx",
                    "user_email": "finance_emp@example.com",
                    "department": "Finance",
                    "visibility": "Manager",
                }
            ]
            
            for doc_info in docs_to_ingest:
                filepath = os.path.join(sample_dir, doc_info["filename"])
                if os.path.exists(filepath):
                    with open(filepath, "rb") as f:
                        content = f.read()
                    
                    user = users[doc_info["user_email"]]
                    print(f"Ingesting document: {doc_info['filename']}...")
                    try:
                        doc, chunks = await ingest_upload(
                            session,
                            user=user,
                            filename=doc_info["filename"],
                            content=content,
                            department=doc_info["department"],
                            visibility=doc_info["visibility"],
                            chunking_strategy="recursive"
                        )
                        print(f"Ingested {doc.name} successfully. Created {chunks} chunks.")
                    except Exception as e:
                        print(f"Error ingesting {doc_info['filename']}: {e}")
                else:
                    print(f"File not found: {filepath}")
        else:
            print(f"Sample directory not found: {sample_dir}")

        # 3. Seed Tickets
        tickets_data = [
            {
                "user_email": "admin@example.com",
                "issue": "VPN connection times out after 5 minutes.",
                "category": "Network",
                "priority": "High",
                "assignee": "Network Operations",
                "status": "Open"
            },
            {
                "user_email": "ops_emp@example.com",
                "issue": "Monitor screen is flickering.",
                "category": "IT Support",
                "priority": "Medium",
                "assignee": "Service Desk",
                "status": "Resolved"
            }
        ]
        
        for t_data in tickets_data:
            user = users[t_data["user_email"]]
            ticket = Ticket(
                user_id=user.id,
                issue=t_data["issue"],
                category=t_data["category"],
                priority=t_data["priority"],
                assignee=t_data["assignee"],
                status=t_data["status"]
            )
            session.add(ticket)
            print(f"Seeded ticket: {t_data['issue']}")

        # 4. Seed Emails
        emails_data = [
            {
                "sender": "external-client@company.com",
                "content": "Hi, I would like to get a pricing quote for the enterprise plan.",
                "category": "Sales",
                "confidence": 0.88,
                "status": "Processed"
            },
            {
                "sender": "spammer99@gmail.com",
                "content": "CONGRATULATIONS! You won 1 million dollars. Click here to claim your free reward now!",
                "category": "Spam",
                "confidence": 0.95,
                "status": "Processed"
            }
        ]
        
        for e_data in emails_data:
            email_record = Email(
                sender=e_data["sender"],
                content=e_data["content"],
                category=e_data["category"],
                confidence=e_data["confidence"],
                status=e_data["status"]
            )
            session.add(email_record)
            print(f"Seeded email: from {e_data['sender']}")

        # 5. Seed Invoices
        invoices_data = [
            {
                "user_email": "finance_emp@example.com",
                "vendor": "Acme Corp",
                "invoice_number": "INV-2026-001",
                "amount": "1250.00",
                "currency": "USD",
                "invoice_date": "2026-06-01",
                "status": "Pending Approval"
            },
            {
                "user_email": "admin@example.com",
                "vendor": "Cloud Services Provider",
                "invoice_number": "CSP-9876",
                "amount": "4500.00",
                "currency": "USD",
                "invoice_date": "2026-05-28",
                "status": "Approved"
            }
        ]
        
        for i_data in invoices_data:
            user = users[i_data["user_email"]]
            invoice = Invoice(
                user_id=user.id,
                vendor=i_data["vendor"],
                invoice_number=i_data["invoice_number"],
                amount=i_data["amount"],
                currency=i_data["currency"],
                invoice_date=i_data["invoice_date"],
                status=i_data["status"]
            )
            session.add(invoice)
            print(f"Seeded invoice: {i_data['invoice_number']}")

        # 6. Seed GitHub Issues
        github_data = [
            {
                "issue_description": "NullPointerException when loading customer profile page with empty address list.",
                "root_cause": "The customer profile component attempts to access index 0 of the address array without validation.",
                "suggested_fix": "Add an empty array check before addressing the index. For example, if(addresses.length > 0) ...",
                "pr_draft": "## PR Description\n- Fix customer profile crash by introducing address validation check."
            }
        ]
        
        for g_data in github_data:
            gh_issue = GitHubIssue(
                issue_description=g_data["issue_description"],
                root_cause=g_data["root_cause"],
                suggested_fix=g_data["suggested_fix"],
                pr_draft=g_data["pr_draft"]
            )
            session.add(gh_issue)
            print(f"Seeded GitHub Issue: {g_data['issue_description'][:40]}...")

        # 7. Seed Chat Conversation and Message
        user = users["admin@example.com"]
        conversation = Conversation(
            user_id=user.id,
            title="HR Leave Policy Inquiry"
        )
        session.add(conversation)
        await session.flush()
        
        message = Message(
            conversation_id=conversation.id,
            prompt="How many days of annual leave do I get?",
            response="Based on the HR Policy, all full-time employees are entitled to 15 days of paid annual leave per calendar year.",
            model="local-fallback",
            prompt_tokens=10,
            completion_tokens=25,
            latency_ms=120,
            retrieved_context={"citations": [{"document_name": "hr_policy.docx", "page": 1, "excerpt": "annual leave"}]}
        )
        session.add(message)
        await session.flush()
        
        # Add Evaluation
        evaluation = Evaluation(
            conversation_id=conversation.id,
            score=0.9,
            comments="Very accurate and fast response.",
            metrics={"answer_relevancy": 0.9, "faithfulness": 0.9, "context_recall": 0.9}
        )
        session.add(evaluation)
        
        # Add Audit log
        audit_log = AuditLog(
            user_id=user.id,
            event_type="chat.completed",
            payload={"conversation_id": conversation.id, "latency_ms": 120}
        )
        session.add(audit_log)
        print("Seeded conversation, message, evaluation and audit log.")

        await session.commit()
        print("Database seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed())
