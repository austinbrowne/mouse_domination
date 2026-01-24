"""Authentication and security models."""
from datetime import datetime, timezone, timedelta
import secrets
from extensions import db
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError


class User(db.Model):
    """Authenticated users with Flask-Login support."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime, nullable=True)

    # Authentication fields
    password_hash = db.Column(db.String(255), nullable=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    password_changed_at = db.Column(db.DateTime, nullable=True)

    # Password reset fields
    password_reset_token = db.Column(db.String(100), nullable=True, unique=True, index=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)

    # Email verification fields
    email_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(100), nullable=True, unique=True, index=True)
    email_verification_expires = db.Column(db.DateTime, nullable=True)

    # 2FA/TOTP fields
    totp_secret = db.Column(db.String(32), nullable=True)  # Base32 encoded secret
    totp_enabled = db.Column(db.Boolean, default=False)
    recovery_codes = db.Column(db.Text, nullable=True)  # JSON array of hashed codes

    # Authorization fields
    is_approved = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)

    # OAuth fields
    google_id = db.Column(db.String(255), unique=True, nullable=True, index=True)
    google_linked_at = db.Column(db.DateTime, nullable=True)
    auth_provider = db.Column(db.String(20), nullable=True)  # 'local', 'google'

    # Relationships
    inventory_items = db.relationship('Inventory', back_populates='user', lazy='dynamic')

    # Argon2id password hasher (OWASP recommended)
    _ph = PasswordHasher(
        time_cost=3,
        memory_cost=65536,
        parallelism=4,
        hash_len=32,
        salt_len=16
    )

    # Flask-Login required properties
    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return self.is_approved

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    # Password methods
    def set_password(self, password: str) -> None:
        """Hash and set password using Argon2id."""
        self.password_hash = self._ph.hash(password)
        self.password_changed_at = datetime.now(timezone.utc)

    def check_password(self, password: str) -> bool:
        """Verify password. Returns False for any error."""
        if not self.password_hash:
            return False
        try:
            self._ph.verify(self.password_hash, password)
            if self._ph.check_needs_rehash(self.password_hash):
                self.password_hash = self._ph.hash(password)
            return True
        except (VerifyMismatchError, InvalidHashError):
            return False

    def is_locked(self) -> bool:
        """Check if account is locked due to failed attempts."""
        if not self.locked_until:
            return False
        # Handle both naive (from SQLite) and aware datetimes
        locked_until = self.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= locked_until:
            self.locked_until = None
            self.failed_login_attempts = 0
            return False
        return True

    def record_failed_login(self) -> None:
        """Record failed login and apply progressive lockout."""
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= 5:
            lockout_minutes = [5, 15, 60, 1440][min(self.failed_login_attempts - 5, 3)]
            self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)

    def record_successful_login(self) -> None:
        """Reset failed attempts and update last login."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login_at = datetime.now(timezone.utc)

    def generate_password_reset_token(self) -> str:
        """Generate a secure password reset token valid for 1 hour."""
        self.password_reset_token = secrets.token_urlsafe(32)
        self.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        return self.password_reset_token

    def verify_password_reset_token(self, token: str) -> bool:
        """Verify password reset token is valid and not expired."""
        if not self.password_reset_token or not self.password_reset_expires:
            return False
        if self.password_reset_token != token:
            return False
        # Handle timezone-naive datetimes
        expires = self.password_reset_expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            return False
        return True

    def clear_password_reset_token(self) -> None:
        """Clear the password reset token after use."""
        self.password_reset_token = None
        self.password_reset_expires = None

    def generate_email_verification_token(self) -> str:
        """Generate a secure email verification token valid for 24 hours."""
        self.email_verification_token = secrets.token_urlsafe(32)
        self.email_verification_expires = datetime.now(timezone.utc) + timedelta(hours=24)
        return self.email_verification_token

    def verify_email_verification_token(self, token: str) -> bool:
        """Verify email verification token is valid and not expired."""
        if not self.email_verification_token or not self.email_verification_expires:
            return False
        if self.email_verification_token != token:
            return False
        # Handle timezone-naive datetimes
        expires = self.email_verification_expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            return False
        return True

    def mark_email_verified(self) -> None:
        """Mark email as verified and clear token."""
        self.email_verified = True
        self.email_verification_token = None
        self.email_verification_expires = None

    def generate_totp_secret(self) -> str:
        """Generate a new TOTP secret for 2FA setup."""
        import pyotp
        self.totp_secret = pyotp.random_base32()
        return self.totp_secret

    def get_totp_uri(self, app_name: str = 'Creator Hub') -> str:
        """Get provisioning URI for QR code generation."""
        import pyotp
        if not self.totp_secret:
            return None
        totp = pyotp.TOTP(self.totp_secret)
        return totp.provisioning_uri(name=self.email, issuer_name=app_name)

    def verify_totp(self, code: str) -> bool:
        """Verify a TOTP code."""
        import pyotp
        if not self.totp_secret:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(code, valid_window=1)  # Allow 1 window (30s) drift

    def enable_totp(self) -> None:
        """Enable 2FA for this user."""
        self.totp_enabled = True

    def disable_totp(self) -> None:
        """Disable 2FA for this user."""
        self.totp_enabled = False
        self.totp_secret = None
        self.recovery_codes = None

    def generate_recovery_codes(self) -> list[str]:
        """Generate 10 recovery codes and store hashed versions."""
        import json
        import hashlib
        codes = [secrets.token_hex(4).upper() for _ in range(10)]  # 8-char hex codes
        hashed = [hashlib.sha256(code.encode()).hexdigest() for code in codes]
        self.recovery_codes = json.dumps(hashed)
        return codes  # Return plain codes for user to save

    def verify_recovery_code(self, code: str) -> bool:
        """Verify and consume a recovery code."""
        import json
        import hashlib
        if not self.recovery_codes:
            return False
        hashed_codes = json.loads(self.recovery_codes)
        code_hash = hashlib.sha256(code.upper().encode()).hexdigest()
        if code_hash in hashed_codes:
            hashed_codes.remove(code_hash)
            self.recovery_codes = json.dumps(hashed_codes) if hashed_codes else None
            return True
        return False

    # OAuth helper methods
    def has_password(self) -> bool:
        """Check if user has a local password set."""
        return bool(self.password_hash)

    def has_google_linked(self) -> bool:
        """Check if user has Google account linked."""
        return bool(self.google_id)

    def can_use_local_login(self) -> bool:
        """Check if user can log in with email/password."""
        return self.has_password()

    def link_google(self, google_id: str) -> None:
        """Link a Google account to this user."""
        self.google_id = google_id
        self.google_linked_at = datetime.now(timezone.utc)

    def unlink_google(self) -> bool:
        """Unlink Google account. Returns False if user would have no login method."""
        if not self.has_password():
            return False  # Can't unlink if no password
        self.google_id = None
        self.google_linked_at = None
        if self.auth_provider == 'google':
            self.auth_provider = 'local'
        return True

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'is_approved': self.is_approved,
            'is_admin': self.is_admin,
            'has_google': self.has_google_linked(),
            'has_password': self.has_password(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
        }


class AuditLog(db.Model):
    """Audit log for tracking admin and security-relevant actions."""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Who performed the action
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    actor_email = db.Column(db.String(120), nullable=True)  # Stored separately in case user deleted

    # What action was performed
    action = db.Column(db.String(50), nullable=False, index=True)  # e.g., 'user_approved', 'user_rejected'

    # Target of the action (if applicable)
    target_type = db.Column(db.String(50), nullable=True)  # e.g., 'user'
    target_id = db.Column(db.Integer, nullable=True)
    target_email = db.Column(db.String(120), nullable=True)  # For user targets

    # Additional details
    details = db.Column(db.Text, nullable=True)  # JSON or text for extra context
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6

    # Relationships
    actor = db.relationship('User', foreign_keys=[actor_id], backref='audit_actions')

    # Action type constants
    ACTION_USER_APPROVED = 'user_approved'
    ACTION_USER_REJECTED = 'user_rejected'
    ACTION_USER_DELETED = 'user_deleted'
    ACTION_ADMIN_GRANTED = 'admin_granted'
    ACTION_ADMIN_REVOKED = 'admin_revoked'
    ACTION_PASSWORD_RESET_REQUESTED = 'password_reset_requested'
    ACTION_PASSWORD_CHANGED = 'password_changed'
    ACTION_LOGIN_SUCCESS = 'login_success'
    ACTION_LOGIN_FAILED = 'login_failed'
    ACTION_ACCOUNT_LOCKED = 'account_locked'
    ACTION_GOOGLE_LOGIN = 'google_login'
    ACTION_GOOGLE_SIGNUP = 'google_signup'
    ACTION_GOOGLE_ACCOUNT_LINKED = 'google_account_linked'
    ACTION_GOOGLE_ACCOUNT_UNLINKED = 'google_account_unlinked'

    @classmethod
    def log(cls, action: str, actor=None, target_type: str = None,
            target_id: int = None, target_email: str = None,
            details: str = None, ip_address: str = None):
        """Create an audit log entry."""
        from extensions import db
        entry = cls(
            action=action,
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else None,
            target_type=target_type,
            target_id=target_id,
            target_email=target_email,
            details=details,
            ip_address=ip_address
        )
        db.session.add(entry)
        return entry

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'actor_email': self.actor_email,
            'action': self.action,
            'target_type': self.target_type,
            'target_email': self.target_email,
            'details': self.details,
        }


class LoginHistory(db.Model):
    """Track user login history for security awareness."""
    __tablename__ = 'login_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6
    user_agent = db.Column(db.String(500), nullable=True)
    success = db.Column(db.Boolean, default=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('login_history', lazy='dynamic', order_by='LoginHistory.timestamp.desc()'))

    @classmethod
    def record(cls, user, ip_address: str = None, user_agent: str = None, success: bool = True):
        """Record a login attempt."""
        from extensions import db
        entry = cls(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,  # Truncate long user agents
            success=success
        )
        db.session.add(entry)
        return entry

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'success': self.success,
        }
