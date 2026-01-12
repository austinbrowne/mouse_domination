"""Entity-specific service classes."""
from models import Company, Contact, Inventory, AffiliateRevenue
from .base import BaseService


class CompanyService(BaseService[Company]):
    """Service for Company operations."""
    model = Company
    searchable_fields = ['name']
    default_order_by = 'name'
    eager_load = []  # No eager loading needed for list view

    @classmethod
    def get_with_counts(cls, id: int) -> tuple[Company, int, int]:
        """Get company with contact and inventory counts in single query."""
        from app import db
        from sqlalchemy import func

        result = db.session.query(
            Company,
            func.count(Contact.id.distinct()).label('contact_count'),
            func.count(Inventory.id.distinct()).label('inventory_count')
        ).outerjoin(Contact, Contact.company_id == Company.id
        ).outerjoin(Inventory, Inventory.company_id == Company.id
        ).filter(Company.id == id
        ).group_by(Company.id
        ).first()

        if not result:
            from .base import NotFoundError
            raise NotFoundError(f"Company with id {id} not found")

        return result[0], result[1], result[2]

    @classmethod
    def list_with_counts(cls, filters: dict = None, search: str = None):
        """List companies with contact/inventory counts in efficient query."""
        from app import db
        from sqlalchemy import func

        query = db.session.query(
            Company,
            func.count(Contact.id.distinct()).label('contact_count'),
            func.count(Inventory.id.distinct()).label('inventory_count')
        ).outerjoin(Contact, Contact.company_id == Company.id
        ).outerjoin(Inventory, Inventory.company_id == Company.id
        ).group_by(Company.id)

        if filters:
            if filters.get('category'):
                query = query.filter(Company.category == filters['category'])
            if filters.get('relationship_status'):
                query = query.filter(Company.relationship_status == filters['relationship_status'])
            if filters.get('priority'):
                query = query.filter(Company.priority == filters['priority'])

        if search:
            query = query.filter(Company.name.ilike(f"%{search}%"))

        query = query.order_by(Company.name)
        return query.all()


class ContactService(BaseService[Contact]):
    """Service for Contact operations."""
    model = Contact
    searchable_fields = ['name', 'email', 'notes']
    default_order_by = 'name'
    eager_load = ['company']


class InventoryService(BaseService[Inventory]):
    """Service for Inventory operations."""
    model = Inventory
    searchable_fields = ['product_name', 'notes']
    default_order_by = 'date_acquired'
    eager_load = ['company']

    @classmethod
    def get_stats(cls) -> dict:
        """Get inventory statistics in a single query."""
        from app import db
        from sqlalchemy import func, case

        result = db.session.query(
            func.count(Inventory.id).label('total'),
            func.sum(case((Inventory.status == 'in_queue', 1), else_=0)).label('in_queue'),
            func.sum(case((Inventory.status == 'reviewing', 1), else_=0)).label('reviewing'),
            func.sum(case((Inventory.status == 'reviewed', 1), else_=0)).label('reviewed'),
            func.sum(case((Inventory.sold == True, 1), else_=0)).label('sold'),
            func.sum(case((Inventory.deadline != None, 1), else_=0)).label('with_deadline'),
        ).first()

        return {
            'total': result.total or 0,
            'in_queue': result.in_queue or 0,
            'reviewing': result.reviewing or 0,
            'reviewed': result.reviewed or 0,
            'sold': result.sold or 0,
            'with_deadline': result.with_deadline or 0,
        }


class AffiliateRevenueService(BaseService[AffiliateRevenue]):
    """Service for AffiliateRevenue operations."""
    model = AffiliateRevenue
    searchable_fields = []
    default_order_by = 'year'
    eager_load = ['company']

    @classmethod
    def get_monthly_totals(cls, year: int = None) -> list:
        """Get monthly revenue totals."""
        from app import db
        from sqlalchemy import func

        query = db.session.query(
            AffiliateRevenue.year,
            AffiliateRevenue.month,
            func.sum(AffiliateRevenue.revenue).label('total')
        ).group_by(AffiliateRevenue.year, AffiliateRevenue.month
        ).order_by(AffiliateRevenue.year, AffiliateRevenue.month)

        if year:
            query = query.filter(AffiliateRevenue.year == year)

        return query.all()

    @classmethod
    def get_company_totals(cls, year: int = None) -> list:
        """Get revenue totals by company."""
        from app import db
        from sqlalchemy import func

        query = db.session.query(
            Company.name,
            func.sum(AffiliateRevenue.revenue).label('total')
        ).join(Company
        ).group_by(Company.id
        ).order_by(func.sum(AffiliateRevenue.revenue).desc())

        if year:
            query = query.filter(AffiliateRevenue.year == year)

        return query.all()
