from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    vendor: Mapped[str] = mapped_column(String(255))
    invoice_number: Mapped[str] = mapped_column(String(128))
    amount: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(16))
    invoice_date: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="Pending Approval")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
