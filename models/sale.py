from datetime import datetime, timezone
from decimal import Decimal
from extensions import db

class Sale(db.Model):
    __tablename__ = "sales"
    __table_args__ = (db.CheckConstraint("total_amount >= 0", name="ck_sales_total_nonnegative"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("cashier_shifts.id", ondelete="SET NULL"), nullable=True, index=True)
    total_amount = db.Column(db.Numeric(12, 4), nullable=False, default=Decimal("0.0000"))
    payment_method = db.Column(db.String(30), nullable=False, default="cash")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", back_populates="sales")
    shift = db.relationship("CashierShift", back_populates="sales")
    items = db.relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    returns = db.relationship("SaleReturn", back_populates="sale")

    def to_dict(self):
        return {"id": self.id, "user_id": self.user_id, "total_amount": str(self.total_amount),
                "shift_id": self.shift_id, "payment_method": self.payment_method,
                "created_at": self.created_at.isoformat(),
                "returns": [return_record.to_dict() for return_record in self.returns],
                "items": [item.to_dict() for item in self.items]}
