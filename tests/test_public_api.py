"""Tests for the public API blueprint."""
import pytest
from app import create_app
from extensions import db
from models import User, Inventory, Company, CreatorProfile
from config import TestConfig


class PublicAPITestConfig(TestConfig):
    """Test config with a known API key."""
    PUBLIC_API_KEY = 'test-api-key-123'


@pytest.fixture
def api_app():
    """Create app with public API key configured."""
    app = create_app(PublicAPITestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def api_client(api_app):
    return api_app.test_client()


@pytest.fixture
def api_headers():
    return {'X-API-Key': 'test-api-key-123'}


@pytest.fixture
def seed_data(api_app):
    """Seed DB with test data for API tests."""
    with api_app.app_context():
        # Need a user for inventory FK
        user = User(email='api@test.com', name='API User', is_approved=True)
        user.set_password('TestPassword123!')
        db.session.add(user)
        db.session.flush()

        company = Company(
            name='Razer',
            category='mice',
            website='https://razer.com',
            affiliate_status='yes',
            affiliate_link='https://razer.com/?ref=dazz',
            commission_rate=8.0,
            notes='Internal note about Razer',
            priority='active',
            relationship_status='active',
        )
        db.session.add(company)
        db.session.flush()

        published = Inventory(
            user_id=user.id,
            product_name='Razer Viper V3 Pro',
            company_id=company.id,
            category='mouse',
            slug='razer-viper-v3-pro',
            is_published=True,
            image_url='https://img.example.com/viper.jpg',
            retail_price=159.99,
            short_verdict='Best wireless mouse for FPS',
            pros=['lightweight', 'great sensor'],
            cons=['expensive', 'no Bluetooth'],
            rating=9,
            specs={'weight': '58g', 'sensor': 'Focus Pro 4K'},
            pick_category='best-lightweight',
            video_url='https://youtube.com/watch?v=abc',
            cost=0.0,
            sale_price=None,
            fees=None,
            shipping=None,
            marketplace=None,
            buyer=None,
            sale_notes=None,
            notes='Internal review notes',
        )

        unpublished = Inventory(
            user_id=user.id,
            product_name='Secret Prototype',
            company_id=company.id,
            category='mouse',
            slug='secret-prototype',
            is_published=False,
            cost=500.0,
            notes='NDA product',
        )

        db.session.add_all([published, unpublished])

        profile = CreatorProfile(
            user_id=user.id,
            display_name='DazzTrazak',
            tagline='Gaming peripherals reviewer',
            bio='I review mice and stuff.',
            photo_url='https://img.example.com/dazz.jpg',
            location='Austin, TX',
            contact_email='secret@dazz.com',
            website_url='https://dazztrazak.com',
            social_links={'youtube': '@dazztrazak', 'twitter': '@dazztrazak'},
            platform_stats={'youtube': {'subscribers': 4500, 'engagement_rate': 8.2}},
            content_niches=['gaming peripherals', 'tech reviews'],
            public_token='secret-token-abc123',
            is_public=True,
        )
        db.session.add(profile)
        db.session.commit()

        return {
            'user_id': user.id,
            'company_id': company.id,
            'published_slug': 'razer-viper-v3-pro',
            'unpublished_slug': 'secret-prototype',
        }


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

class TestAPIAuth:
    def test_missing_api_key_returns_401(self, api_client):
        resp = api_client.get('/api/v1/public/products')
        assert resp.status_code == 401
        assert resp.json['error'] == 'Unauthorized'

    def test_wrong_api_key_returns_401(self, api_client):
        resp = api_client.get('/api/v1/public/products', headers={'X-API-Key': 'wrong'})
        assert resp.status_code == 401

    def test_valid_api_key_succeeds(self, api_client, api_headers, seed_data):
        resp = api_client.get('/api/v1/public/products', headers=api_headers)
        assert resp.status_code == 200

    def test_unconfigured_api_key_returns_503(self):
        """If PUBLIC_API_KEY is empty, API returns 503."""
        class NoKeyConfig(TestConfig):
            PUBLIC_API_KEY = ''

        app = create_app(NoKeyConfig)
        with app.app_context():
            db.create_all()
            client = app.test_client()
            resp = client.get('/api/v1/public/products', headers={'X-API-Key': 'anything'})
            assert resp.status_code == 503
            db.drop_all()


# ---------------------------------------------------------------------------
# to_public_dict() forbidden field tests
# ---------------------------------------------------------------------------

INVENTORY_FORBIDDEN_FIELDS = {
    'cost', 'sale_price', 'fees', 'shipping', 'profit_loss',
    'buyer', 'sale_notes', 'marketplace', 'notes', 'user_id',
    'id', 'company_id', 'source_type', 'date_acquired', 'on_amazon',
    'deadline', 'return_by_date', 'status', 'condition',
    'short_url', 'short_publish_date', 'video_publish_date',
    'sold', 'created_at', 'updated_at',
}

COMPANY_FORBIDDEN_FIELDS = {
    'commission_rate', 'notes', 'priority', 'relationship_status',
    'id', 'affiliate_code', 'created_at', 'updated_at',
}

CREATOR_PROFILE_FORBIDDEN_FIELDS = {
    'contact_email', 'public_token', 'user_id', 'id',
    'is_public', 'audience_demographics',
    'created_at', 'updated_at',
}


class TestPublicDictForbiddenFields:
    def test_inventory_to_public_dict_excludes_forbidden(self, api_app, seed_data):
        with api_app.app_context():
            product = Inventory.query.filter_by(slug='razer-viper-v3-pro').first()
            public = product.to_public_dict()
            exposed_forbidden = INVENTORY_FORBIDDEN_FIELDS & set(public.keys())
            assert exposed_forbidden == set(), f"Forbidden fields exposed: {exposed_forbidden}"

    def test_company_to_public_dict_excludes_forbidden(self, api_app, seed_data):
        with api_app.app_context():
            company = Company.query.first()
            public = company.to_public_dict()
            exposed_forbidden = COMPANY_FORBIDDEN_FIELDS & set(public.keys())
            assert exposed_forbidden == set(), f"Forbidden fields exposed: {exposed_forbidden}"

    def test_creator_profile_to_public_dict_excludes_forbidden(self, api_app, seed_data):
        with api_app.app_context():
            profile = CreatorProfile.query.first()
            public = profile.to_public_dict()
            exposed_forbidden = CREATOR_PROFILE_FORBIDDEN_FIELDS & set(public.keys())
            assert exposed_forbidden == set(), f"Forbidden fields exposed: {exposed_forbidden}"


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

class TestListProducts:
    def test_returns_published_only(self, api_client, api_headers, seed_data):
        resp = api_client.get('/api/v1/public/products', headers=api_headers)
        assert resp.status_code == 200
        data = resp.json
        assert len(data) == 1
        assert data[0]['slug'] == 'razer-viper-v3-pro'

    def test_filter_by_pick_category(self, api_client, api_headers, seed_data):
        resp = api_client.get('/api/v1/public/products?pick_category=best-lightweight', headers=api_headers)
        assert resp.status_code == 200
        assert len(resp.json) == 1

    def test_filter_by_nonexistent_category_returns_empty(self, api_client, api_headers, seed_data):
        resp = api_client.get('/api/v1/public/products?pick_category=nonexistent', headers=api_headers)
        assert resp.status_code == 200
        assert resp.json == []

    def test_unpublished_not_returned(self, api_client, api_headers, seed_data):
        resp = api_client.get('/api/v1/public/products', headers=api_headers)
        slugs = [p['slug'] for p in resp.json]
        assert 'secret-prototype' not in slugs


class TestGetProduct:
    def test_returns_published_product(self, api_client, api_headers, seed_data):
        resp = api_client.get('/api/v1/public/products/razer-viper-v3-pro', headers=api_headers)
        assert resp.status_code == 200
        assert resp.json['product_name'] == 'Razer Viper V3 Pro'
        assert resp.json['rating'] == 9

    def test_unpublished_product_returns_404(self, api_client, api_headers, seed_data):
        resp = api_client.get('/api/v1/public/products/secret-prototype', headers=api_headers)
        assert resp.status_code == 404

    def test_nonexistent_slug_returns_404(self, api_client, api_headers, seed_data):
        resp = api_client.get('/api/v1/public/products/does-not-exist', headers=api_headers)
        assert resp.status_code == 404

    def test_invalid_slug_returns_404(self, api_client, api_headers, seed_data):
        """Slugs with special chars should be rejected without hitting DB."""
        resp = api_client.get('/api/v1/public/products/DROP TABLE--', headers=api_headers)
        assert resp.status_code == 404

    def test_no_forbidden_fields_in_response(self, api_client, api_headers, seed_data):
        resp = api_client.get('/api/v1/public/products/razer-viper-v3-pro', headers=api_headers)
        exposed_forbidden = INVENTORY_FORBIDDEN_FIELDS & set(resp.json.keys())
        assert exposed_forbidden == set(), f"Forbidden fields in response: {exposed_forbidden}"

    def test_product_with_no_company(self, api_app, api_client, api_headers, seed_data):
        """Published product with company_id=None should return company_name: null."""
        with api_app.app_context():
            user_id = seed_data['user_id']
            orphan = Inventory(
                user_id=user_id,
                product_name='No-Brand Mouse',
                company_id=None,
                category='mouse',
                slug='no-brand-mouse',
                is_published=True,
                cost=0.0,
            )
            db.session.add(orphan)
            db.session.commit()

        resp = api_client.get('/api/v1/public/products/no-brand-mouse', headers=api_headers)
        assert resp.status_code == 200
        assert resp.json['company_name'] is None


class TestListCompanies:
    def test_returns_affiliate_companies(self, api_client, api_headers, seed_data):
        resp = api_client.get('/api/v1/public/companies', headers=api_headers)
        assert resp.status_code == 200
        assert len(resp.json) == 1
        assert resp.json[0]['name'] == 'Razer'

    def test_no_forbidden_fields_in_company_response(self, api_client, api_headers, seed_data):
        resp = api_client.get('/api/v1/public/companies', headers=api_headers)
        for company in resp.json:
            exposed_forbidden = COMPANY_FORBIDDEN_FIELDS & set(company.keys())
            assert exposed_forbidden == set(), f"Forbidden fields: {exposed_forbidden}"


class TestCreatorProfile:
    def test_returns_public_profile(self, api_client, api_headers, seed_data):
        resp = api_client.get('/api/v1/public/creator-profile', headers=api_headers)
        assert resp.status_code == 200
        assert resp.json['display_name'] == 'DazzTrazak'

    def test_no_forbidden_fields_in_profile_response(self, api_client, api_headers, seed_data):
        resp = api_client.get('/api/v1/public/creator-profile', headers=api_headers)
        exposed_forbidden = CREATOR_PROFILE_FORBIDDEN_FIELDS & set(resp.json.keys())
        assert exposed_forbidden == set(), f"Forbidden fields: {exposed_forbidden}"

    def test_no_public_profile_returns_404(self, api_app):
        """When no profile has is_public=True, return 404."""
        with api_app.app_context():
            client = api_app.test_client()
            resp = client.get(
                '/api/v1/public/creator-profile',
                headers={'X-API-Key': 'test-api-key-123'},
            )
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# HTTP method restriction tests
# ---------------------------------------------------------------------------

class TestHTTPMethods:
    """Ensure all endpoints reject non-GET methods."""

    @pytest.mark.parametrize("endpoint", [
        '/api/v1/public/products',
        '/api/v1/public/products/any-slug',
        '/api/v1/public/companies',
        '/api/v1/public/creator-profile',
    ])
    @pytest.mark.parametrize("method", ['post', 'put', 'patch', 'delete'])
    def test_non_get_methods_rejected(self, api_client, api_headers, endpoint, method):
        resp = getattr(api_client, method)(endpoint, headers=api_headers)
        assert resp.status_code == 405
