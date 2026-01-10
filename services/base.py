"""Base service class with common CRUD operations and error handling."""
from functools import wraps
from typing import TypeVar, Generic, Type, Any
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import joinedload
from app import db
from constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

T = TypeVar('T')


class ServiceError(Exception):
    """Base exception for service layer errors."""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(message)


class DatabaseError(ServiceError):
    """Database operation failed."""
    pass


class NotFoundError(ServiceError):
    """Resource not found."""
    pass


class DuplicateError(ServiceError):
    """Duplicate resource exists."""
    pass


def db_transaction(func):
    """Decorator for database transaction handling with automatic rollback."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            db.session.commit()
            return result
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.error(f"Integrity error in {func.__name__}: {e}")
            raise DuplicateError("A record with this value already exists.")
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Database error in {func.__name__}: {e}")
            raise DatabaseError(f"Database operation failed: {str(e)}")
    return wrapper


class PaginatedResult:
    """Container for paginated query results."""
    def __init__(self, items: list, total: int, page: int, page_size: int):
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size
        self.pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        self.has_prev = page > 1
        self.has_next = page < self.pages

    def to_dict(self):
        return {
            'items': [item.to_dict() if hasattr(item, 'to_dict') else item for item in self.items],
            'total': self.total,
            'page': self.page,
            'page_size': self.page_size,
            'pages': self.pages,
            'has_prev': self.has_prev,
            'has_next': self.has_next,
        }


class BaseService(Generic[T]):
    """Base service class with common CRUD operations."""

    model: Type[T] = None
    searchable_fields: list = []
    default_order_by: str = 'id'
    eager_load: list = []  # Relationships to eager load

    @classmethod
    def get_by_id(cls, id: int, eager: bool = True) -> T:
        """Get a single record by ID."""
        query = cls.model.query
        if eager and cls.eager_load:
            for rel in cls.eager_load:
                query = query.options(joinedload(getattr(cls.model, rel)))

        result = query.get(id)
        if not result:
            raise NotFoundError(f"{cls.model.__name__} with id {id} not found")
        return result

    @classmethod
    def get_or_none(cls, id: int, eager: bool = True) -> T | None:
        """Get a single record by ID, returns None if not found."""
        try:
            return cls.get_by_id(id, eager)
        except NotFoundError:
            return None

    @classmethod
    def list(cls, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE,
             filters: dict = None, search: str = None,
             order_by: str = None, eager: bool = True) -> PaginatedResult:
        """List records with pagination, filtering, and search."""
        page_size = min(page_size, MAX_PAGE_SIZE)
        query = cls.model.query

        # Apply eager loading
        if eager and cls.eager_load:
            for rel in cls.eager_load:
                query = query.options(joinedload(getattr(cls.model, rel)))

        # Apply filters
        if filters:
            for field, value in filters.items():
                if value is not None and hasattr(cls.model, field):
                    query = query.filter(getattr(cls.model, field) == value)

        # Apply search across searchable fields
        if search and cls.searchable_fields:
            search_term = f"%{search}%"
            search_conditions = [
                getattr(cls.model, field).ilike(search_term)
                for field in cls.searchable_fields
                if hasattr(cls.model, field)
            ]
            if search_conditions:
                from sqlalchemy import or_
                query = query.filter(or_(*search_conditions))

        # Get total before pagination
        total = query.count()

        # Apply ordering
        order_field = order_by or cls.default_order_by
        if hasattr(cls.model, order_field):
            query = query.order_by(getattr(cls.model, order_field))

        # Apply pagination
        offset = (page - 1) * page_size
        items = query.offset(offset).limit(page_size).all()

        return PaginatedResult(items, total, page, page_size)

    @classmethod
    def list_all(cls, filters: dict = None, order_by: str = None, eager: bool = True) -> list[T]:
        """List all records without pagination (use sparingly)."""
        query = cls.model.query

        if eager and cls.eager_load:
            for rel in cls.eager_load:
                query = query.options(joinedload(getattr(cls.model, rel)))

        if filters:
            for field, value in filters.items():
                if value is not None and hasattr(cls.model, field):
                    query = query.filter(getattr(cls.model, field) == value)

        order_field = order_by or cls.default_order_by
        if hasattr(cls.model, order_field):
            query = query.order_by(getattr(cls.model, order_field))

        return query.all()

    @classmethod
    @db_transaction
    def create(cls, **data) -> T:
        """Create a new record."""
        instance = cls.model(**data)
        db.session.add(instance)
        return instance

    @classmethod
    @db_transaction
    def update(cls, id: int, **data) -> T:
        """Update an existing record."""
        instance = cls.get_by_id(id, eager=False)
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        return instance

    @classmethod
    @db_transaction
    def delete(cls, id: int) -> bool:
        """Delete a record by ID."""
        instance = cls.get_by_id(id, eager=False)
        db.session.delete(instance)
        return True

    @classmethod
    def exists(cls, **filters) -> bool:
        """Check if a record exists matching the filters."""
        query = cls.model.query
        for field, value in filters.items():
            if hasattr(cls.model, field):
                query = query.filter(getattr(cls.model, field) == value)
        return query.first() is not None

    @classmethod
    def count(cls, **filters) -> int:
        """Count records matching the filters."""
        query = cls.model.query
        for field, value in filters.items():
            if value is not None and hasattr(cls.model, field):
                query = query.filter(getattr(cls.model, field) == value)
        return query.count()
