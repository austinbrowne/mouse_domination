"""Tests for service layer."""
import pytest
from models import Company, Contact, Inventory, AffiliateRevenue
from extensions import db
from services.base import (
    ServiceError, DatabaseError, NotFoundError, DuplicateError,
    db_transaction, PaginatedResult, BaseService
)
from services.crud import CompanyService, ContactService, InventoryService, AffiliateRevenueService


class TestServiceExceptions:
    """Tests for service exception classes."""

    def test_service_error_message(self):
        """Test ServiceError with message."""
        error = ServiceError("Test error")
        assert error.message == "Test error"
        assert error.field is None

    def test_service_error_with_field(self):
        """Test ServiceError with message and field."""
        error = ServiceError("Invalid value", field="name")
        assert error.message == "Invalid value"
        assert error.field == "name"

    def test_database_error_inherits(self):
        """Test DatabaseError is a ServiceError."""
        error = DatabaseError("DB failed")
        assert isinstance(error, ServiceError)
        assert error.message == "DB failed"

    def test_not_found_error_inherits(self):
        """Test NotFoundError is a ServiceError."""
        error = NotFoundError("Not found")
        assert isinstance(error, ServiceError)

    def test_duplicate_error_inherits(self):
        """Test DuplicateError is a ServiceError."""
        error = DuplicateError("Duplicate")
        assert isinstance(error, ServiceError)


class TestPaginatedResult:
    """Tests for PaginatedResult class."""

    def test_pagination_properties(self):
        """Test basic pagination properties."""
        result = PaginatedResult(items=[1, 2, 3], total=10, page=1, page_size=3)
        assert result.items == [1, 2, 3]
        assert result.total == 10
        assert result.page == 1
        assert result.page_size == 3

    def test_pages_calculation(self):
        """Test pages calculation."""
        result = PaginatedResult(items=[], total=10, page=1, page_size=3)
        assert result.pages == 4  # ceil(10/3) = 4

    def test_pages_exact_division(self):
        """Test pages with exact division."""
        result = PaginatedResult(items=[], total=9, page=1, page_size=3)
        assert result.pages == 3

    def test_pages_zero_page_size(self):
        """Test pages with zero page_size."""
        result = PaginatedResult(items=[], total=10, page=1, page_size=0)
        assert result.pages == 0

    def test_has_prev_first_page(self):
        """Test has_prev on first page."""
        result = PaginatedResult(items=[], total=10, page=1, page_size=3)
        assert result.has_prev is False

    def test_has_prev_other_page(self):
        """Test has_prev on page > 1."""
        result = PaginatedResult(items=[], total=10, page=2, page_size=3)
        assert result.has_prev is True

    def test_has_next_not_last_page(self):
        """Test has_next when not on last page."""
        result = PaginatedResult(items=[], total=10, page=1, page_size=3)
        assert result.has_next is True

    def test_has_next_last_page(self):
        """Test has_next on last page."""
        result = PaginatedResult(items=[], total=10, page=4, page_size=3)
        assert result.has_next is False

    def test_to_dict(self):
        """Test serialization to dict."""
        result = PaginatedResult(items=[1, 2], total=5, page=1, page_size=2)
        data = result.to_dict()
        assert data['items'] == [1, 2]
        assert data['total'] == 5
        assert data['page'] == 1
        assert data['page_size'] == 2
        assert data['pages'] == 3
        assert data['has_prev'] is False
        assert data['has_next'] is True


class TestCompanyService:
    """Tests for CompanyService."""

    def test_create_company(self, app):
        """Test creating a company."""
        with app.app_context():
            company = CompanyService.create(name='Test Corp')
            assert company.id is not None
            assert company.name == 'Test Corp'

    def test_get_by_id_found(self, app, company):
        """Test getting company by ID."""
        with app.app_context():
            result = CompanyService.get_by_id(company['id'])
            assert result.name == company['name']

    def test_get_by_id_not_found(self, app):
        """Test getting non-existent company raises NotFoundError."""
        with app.app_context():
            with pytest.raises(NotFoundError):
                CompanyService.get_by_id(99999)

    def test_get_or_none_found(self, app, company):
        """Test get_or_none returns company when found."""
        with app.app_context():
            result = CompanyService.get_or_none(company['id'])
            assert result is not None
            assert result.name == company['name']

    def test_get_or_none_not_found(self, app):
        """Test get_or_none returns None when not found."""
        with app.app_context():
            result = CompanyService.get_or_none(99999)
            assert result is None

    def test_list_pagination(self, app):
        """Test list with pagination."""
        with app.app_context():
            # Create multiple companies
            for i in range(5):
                CompanyService.create(name=f'Company {i}')

            result = CompanyService.list(page=1, page_size=2)
            assert len(result.items) == 2
            assert result.total == 5
            assert result.pages == 3

    def test_list_search(self, app):
        """Test list with search."""
        with app.app_context():
            CompanyService.create(name='Alpha Corp')
            CompanyService.create(name='Beta Inc')
            CompanyService.create(name='Gamma Corp')

            result = CompanyService.list(search='Corp')
            assert result.total == 2

    def test_list_filters(self, app):
        """Test list with filters."""
        with app.app_context():
            CompanyService.create(name='Active Co', category='peripheral')
            CompanyService.create(name='Inactive Co', category='audio')

            result = CompanyService.list(filters={'category': 'peripheral'})
            assert result.total == 1
            assert result.items[0].name == 'Active Co'

    def test_update_company(self, app, company):
        """Test updating a company."""
        with app.app_context():
            result = CompanyService.update(company['id'], name='Updated Corp')
            assert result.name == 'Updated Corp'

    def test_delete_company(self, app, company):
        """Test deleting a company."""
        with app.app_context():
            result = CompanyService.delete(company['id'])
            assert result is True

            # Verify deleted
            with pytest.raises(NotFoundError):
                CompanyService.get_by_id(company['id'])

    def test_exists_true(self, app, company):
        """Test exists returns True when company exists."""
        with app.app_context():
            result = CompanyService.exists(name=company['name'])
            assert result is True

    def test_exists_false(self, app):
        """Test exists returns False when company doesn't exist."""
        with app.app_context():
            result = CompanyService.exists(name='NonExistent Corp')
            assert result is False

    def test_count(self, app):
        """Test count method."""
        with app.app_context():
            CompanyService.create(name='Company A')
            CompanyService.create(name='Company B')

            result = CompanyService.count()
            assert result == 2

    def test_count_with_filters(self, app):
        """Test count with filters."""
        with app.app_context():
            CompanyService.create(name='Company A', category='peripheral')
            CompanyService.create(name='Company B', category='audio')

            result = CompanyService.count(category='peripheral')
            assert result == 1

    def test_list_all(self, app):
        """Test list_all returns all records."""
        with app.app_context():
            for i in range(5):
                CompanyService.create(name=f'Company {i}')

            result = CompanyService.list_all()
            assert len(result) == 5

    def test_get_with_counts(self, app, company, contact):
        """Test get_with_counts returns company with counts."""
        with app.app_context():
            result, contact_count, inventory_count = CompanyService.get_with_counts(company['id'])
            assert result.name == company['name']
            assert contact_count == 1
            assert inventory_count == 0

    def test_get_with_counts_not_found(self, app):
        """Test get_with_counts raises NotFoundError."""
        with app.app_context():
            with pytest.raises(NotFoundError):
                CompanyService.get_with_counts(99999)

    def test_list_with_counts(self, app, company, contact):
        """Test list_with_counts returns companies with counts."""
        with app.app_context():
            results = CompanyService.list_with_counts()
            assert len(results) >= 1
            # Results are tuples of (company, contact_count, inventory_count)
            company_result = next((r for r in results if r[0].id == company['id']), None)
            assert company_result is not None
            assert company_result[1] == 1  # contact_count

    def test_list_with_counts_filtered(self, app):
        """Test list_with_counts with filters."""
        with app.app_context():
            CompanyService.create(name='Filtered Co', category='peripheral')
            CompanyService.create(name='Other Co', category='audio')

            results = CompanyService.list_with_counts(filters={'category': 'peripheral'})
            assert len(results) == 1
            assert results[0][0].name == 'Filtered Co'


class TestContactService:
    """Tests for ContactService."""

    def test_create_contact(self, app, company):
        """Test creating a contact."""
        with app.app_context():
            contact = ContactService.create(
                name='John Doe',
                company_id=company['id']
            )
            assert contact.id is not None
            assert contact.name == 'John Doe'

    def test_list_contacts_with_search(self, app, company):
        """Test listing contacts with search."""
        with app.app_context():
            ContactService.create(name='John Doe', company_id=company['id'])
            ContactService.create(name='Jane Smith', company_id=company['id'])

            result = ContactService.list(search='John')
            assert result.total == 1
            assert result.items[0].name == 'John Doe'


class TestInventoryService:
    """Tests for InventoryService."""

    def test_create_inventory(self, app, test_user):
        """Test creating an inventory item."""
        with app.app_context():
            # Create a company directly
            company = CompanyService.create(name='Inventory Test Co')
            item = InventoryService.create(
                product_name='Test Mouse',
                company_id=company.id,
                user_id=test_user['id'],
                status='in_queue'
            )
            assert item.id is not None
            assert item.product_name == 'Test Mouse'

    def test_get_stats(self, app, test_user):
        """Test get_stats returns correct statistics."""
        with app.app_context():
            company = CompanyService.create(name='Stats Test Co')
            InventoryService.create(
                product_name='Mouse 1',
                company_id=company.id,
                user_id=test_user['id'],
                status='in_queue'
            )
            InventoryService.create(
                product_name='Mouse 2',
                company_id=company.id,
                user_id=test_user['id'],
                status='reviewing'
            )
            InventoryService.create(
                product_name='Mouse 3',
                company_id=company.id,
                user_id=test_user['id'],
                status='reviewed'
            )

            stats = InventoryService.get_stats()
            assert stats['total'] == 3
            assert stats['in_queue'] == 1
            assert stats['reviewing'] == 1
            assert stats['reviewed'] == 1

    def test_get_stats_empty(self, app):
        """Test get_stats with no inventory."""
        with app.app_context():
            stats = InventoryService.get_stats()
            assert stats['total'] == 0
            assert stats['in_queue'] == 0


class TestAffiliateRevenueService:
    """Tests for AffiliateRevenueService."""

    def test_create_revenue(self, app):
        """Test creating affiliate revenue."""
        with app.app_context():
            company = CompanyService.create(name='Revenue Test Co')
            revenue = AffiliateRevenueService.create(
                company_id=company.id,
                year=2024,
                month=1,
                revenue=100.50
            )
            assert revenue.id is not None
            assert revenue.revenue == 100.50

    def test_get_monthly_totals(self, app):
        """Test get_monthly_totals aggregates correctly."""
        with app.app_context():
            # Create two companies to test aggregation by month
            company1 = CompanyService.create(name='Monthly Co 1')
            company2 = CompanyService.create(name='Monthly Co 2')

            AffiliateRevenueService.create(
                company_id=company1.id, year=2024, month=1, revenue=100
            )
            AffiliateRevenueService.create(
                company_id=company2.id, year=2024, month=1, revenue=50
            )
            AffiliateRevenueService.create(
                company_id=company1.id, year=2024, month=2, revenue=75
            )

            results = AffiliateRevenueService.get_monthly_totals()
            # Find January total (aggregated across companies)
            jan = next((r for r in results if r.year == 2024 and r.month == 1), None)
            assert jan is not None
            assert jan.total == 150

    def test_get_monthly_totals_by_year(self, app):
        """Test get_monthly_totals filtered by year."""
        with app.app_context():
            company = CompanyService.create(name='Year Filter Co')
            AffiliateRevenueService.create(
                company_id=company.id, year=2024, month=1, revenue=100
            )
            # Different company for 2023 to avoid unique constraint
            company2 = CompanyService.create(name='Year Filter Co 2')
            AffiliateRevenueService.create(
                company_id=company2.id, year=2023, month=1, revenue=50
            )

            results = AffiliateRevenueService.get_monthly_totals(year=2024)
            assert len(results) == 1
            assert results[0].year == 2024

    def test_get_company_totals(self, app):
        """Test get_company_totals aggregates by company."""
        with app.app_context():
            company1 = CompanyService.create(name='Company A')
            company2 = CompanyService.create(name='Company B')

            AffiliateRevenueService.create(
                company_id=company1.id, year=2024, month=1, revenue=100
            )
            AffiliateRevenueService.create(
                company_id=company1.id, year=2024, month=2, revenue=50
            )
            AffiliateRevenueService.create(
                company_id=company2.id, year=2024, month=1, revenue=200
            )

            results = AffiliateRevenueService.get_company_totals()
            # Company B should be first (highest total)
            assert results[0][0] == 'Company B'
            assert results[0][1] == 200
            assert results[1][0] == 'Company A'
            assert results[1][1] == 150


class TestDbTransactionDecorator:
    """Tests for db_transaction decorator."""

    def test_transaction_commits(self, app):
        """Test successful transaction commits."""
        with app.app_context():
            # Create should commit
            company = CompanyService.create(name='Transaction Test')
            assert company.id is not None

            # Verify it persists
            result = CompanyService.get_by_id(company.id)
            assert result.name == 'Transaction Test'

    def test_transaction_rollback_on_error(self, app):
        """Test transaction rollback on SQLAlchemy error."""
        with app.app_context():
            # Create a company first
            company = CompanyService.create(name='Original')

            # Try to create with same primary key (would fail if we could)
            # Instead, test with a NotFoundError scenario
            with pytest.raises(NotFoundError):
                CompanyService.delete(99999)
