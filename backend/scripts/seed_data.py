import asyncio
import os
import sys

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal, engine
from app.db.base import Base
from app.models import AuditLog, Conversation, Document, Email, Evaluation, GitHubIssue, Invoice, Message, Ticket, User
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

            sample_filenames = [doc_info["filename"] for doc_info in docs_to_ingest]
            existing_docs = await session.execute(select(Document).where(Document.name.in_(sample_filenames)))
            for existing_doc in existing_docs.scalars():
                await session.delete(existing_doc)
            await session.flush()
            
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
                "issue": "Kết nối VPN bị ngắt sau 5 phút sử dụng.",
                "category": "Network",
                "priority": "High",
                "assignee": "Network Operations",
                "status": "Open"
            },
            {
                "user_email": "ops_emp@example.com",
                "issue": "Màn hình làm việc bị nhấp nháy liên tục.",
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
                "content": "Xin chào, tôi muốn nhận báo giá cho gói doanh nghiệp.",
                "category": "Sales",
                "confidence": 0.88,
                "status": "Processed"
            },
            {
                "sender": "spammer99@gmail.com",
                "content": "CHÚC MỪNG! Bạn đã trúng 1 triệu đô. Bấm vào đây để nhận thưởng miễn phí ngay!",
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
                "issue_description": "Lỗi NullPointerException khi tải trang hồ sơ khách hàng có danh sách địa chỉ rỗng.",
                "root_cause": "Component hồ sơ khách hàng đang truy cập phần tử đầu tiên của mảng địa chỉ mà chưa kiểm tra dữ liệu rỗng.",
                "suggested_fix": "Bổ sung kiểm tra mảng địa chỉ trước khi truy cập index. Ví dụ: if (addresses.length > 0) ...",
                "pr_draft": "## Mô tả PR\n- Sửa lỗi crash trang hồ sơ khách hàng bằng cách thêm kiểm tra dữ liệu địa chỉ."
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
            title="Tra cứu chính sách nghỉ phép HR"
        )
        session.add(conversation)
        await session.flush()
        
        message = Message(
            conversation_id=conversation.id,
            prompt="Tôi được nghỉ phép năm bao nhiêu ngày?",
            response="Theo chính sách HR, nhân viên toàn thời gian được hưởng 15 ngày nghỉ phép có lương trong mỗi năm dương lịch.",
            model="local-fallback",
            prompt_tokens=10,
            completion_tokens=25,
            latency_ms=120,
            retrieved_context={"citations": [{"document_name": "hr_policy.docx", "page": 1, "excerpt": "nghỉ phép năm"}]}
        )
        session.add(message)
        await session.flush()
        
        # Add Evaluation
        evaluation = Evaluation(
            conversation_id=conversation.id,
            score=0.9,
            comments="Câu trả lời chính xác và phản hồi nhanh.",
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
