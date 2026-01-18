"""Configuration models - custom options and settings."""
from datetime import datetime, timezone
from extensions import db


class CustomOption(db.Model):
    """User-defined custom options for dropdowns (supplements built-in defaults)."""
    __tablename__ = 'custom_options'

    id = db.Column(db.Integer, primary_key=True)
    option_type = db.Column(db.String(50), nullable=False, index=True)
    # Types: inventory_category, inventory_status, company_category, collab_type, deal_type, contact_role
    value = db.Column(db.String(100), nullable=False)  # e.g., 'flashlight'
    label = db.Column(db.String(100), nullable=False)  # e.g., 'Flashlight'
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Unique constraint: one value per option_type
    __table_args__ = (
        db.UniqueConstraint('option_type', 'value', name='unique_option_type_value'),
    )

    # Relationship
    creator = db.relationship('User', backref='custom_options')

    def to_dict(self):
        return {
            'id': self.id,
            'option_type': self.option_type,
            'value': self.value,
            'label': self.label,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
