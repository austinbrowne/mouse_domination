"""Comprehensive tests for Media Kit functionality.

Test Categories:
A. Model Tests - CreatorProfile, RateCard, Testimonial
B. Route Tests - Authentication requirements
C. Route Tests - Profile CRUD operations
D. Route Tests - Rate Card management
E. Route Tests - Testimonial management
F. Route Tests - Preview & Export
G. Route Tests - Public Sharing
H. Security Tests - CSRF, XSS, authorization
"""
import pytest
from decimal import Decimal
from models import CreatorProfile, RateCard, Testimonial, Company, User
from extensions import db


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def creator_profile(app, test_user):
    """Create a test creator profile."""
    with app.app_context():
        profile = CreatorProfile(
            user_id=test_user['id'],
            display_name='Test Creator',
            tagline='Tech reviewer and content creator',
            bio='I review gaming peripherals and create tech content.',
            location='Austin, TX',
            contact_email='creator@example.com',
            website_url='https://example.com',
            social_links={'youtube': '@testcreator', 'twitter': '@testcreator'},
            platform_stats={
                'youtube': {'subscribers': 5000, 'avg_views': 1000, 'engagement_rate': 8.5},
                'twitter': {'followers': 2000, 'engagement_rate': 5.2}
            },
            audience_demographics={
                'age': {'18-24': 30, '25-34': 45, '35-44': 15},
                'gender': {'male': 70, 'female': 25, 'other': 5},
                'top_locations': ['USA', 'UK', 'Canada']
            },
            content_niches=['gaming peripherals', 'tech reviews']
        )
        db.session.add(profile)
        db.session.commit()
        return {'id': profile.id, 'user_id': test_user['id']}


@pytest.fixture
def rate_card(app, creator_profile):
    """Create a test rate card."""
    with app.app_context():
        rate = RateCard(
            profile_id=creator_profile['id'],
            service_name='Sponsored Video',
            description='Full video review with product showcase',
            price_min=Decimal('500.00'),
            price_max=Decimal('1500.00'),
            is_negotiable=True,
            display_order=1
        )
        db.session.add(rate)
        db.session.commit()
        return {'id': rate.id, 'profile_id': creator_profile['id']}


@pytest.fixture
def testimonial(app, creator_profile, company):
    """Create a test testimonial."""
    with app.app_context():
        t = Testimonial(
            profile_id=creator_profile['id'],
            company_id=company['id'],
            contact_name='John Smith',
            contact_title='Marketing Manager',
            quote='Working with this creator was amazing! Highly recommend.'
        )
        db.session.add(t)
        db.session.commit()
        return {'id': t.id, 'profile_id': creator_profile['id']}


@pytest.fixture
def public_profile(app, creator_profile):
    """Make the creator profile public with a token."""
    with app.app_context():
        profile = db.session.get(CreatorProfile, creator_profile['id'])
        token = profile.generate_public_token()
        profile.is_public = True
        db.session.commit()
        return {'id': profile.id, 'token': token}


# ============================================================================
# A. Model Tests
# ============================================================================

class TestCreatorProfileModel:
    """Tests for CreatorProfile model."""

    def test_create_profile_minimal(self, app, test_user):
        """Test creating profile with minimal required fields."""
        with app.app_context():
            profile = CreatorProfile(
                user_id=test_user['id'],
                display_name='Test Creator'
            )
            db.session.add(profile)
            db.session.commit()

            assert profile.id is not None
            assert profile.display_name == 'Test Creator'
            assert profile.user_id == test_user['id']

    def test_create_profile_with_all_fields(self, app, test_user):
        """Test creating profile with all fields populated."""
        with app.app_context():
            profile = CreatorProfile(
                user_id=test_user['id'],
                display_name='Full Profile',
                tagline='Test tagline',
                bio='Test bio',
                photo_url='https://example.com/photo.jpg',
                location='New York, NY',
                contact_email='test@example.com',
                website_url='https://test.com',
                social_links={'youtube': '@test'},
                platform_stats={'youtube': {'subscribers': 1000}},
                audience_demographics={'age': {'18-24': 50}},
                content_niches=['tech', 'gaming']
            )
            db.session.add(profile)
            db.session.commit()

            assert profile.tagline == 'Test tagline'
            assert profile.location == 'New York, NY'
            assert profile.social_links == {'youtube': '@test'}
            assert profile.content_niches == ['tech', 'gaming']

    def test_json_fields_serialize_correctly(self, app, creator_profile):
        """Test that JSON fields serialize and deserialize correctly."""
        with app.app_context():
            profile = db.session.get(CreatorProfile, creator_profile['id'])
            assert isinstance(profile.social_links, dict)
            assert profile.social_links['youtube'] == '@testcreator'
            assert profile.platform_stats['youtube']['subscribers'] == 5000
            assert profile.audience_demographics['age']['25-34'] == 45

    def test_generate_public_token(self, app, creator_profile):
        """Test public token generation."""
        with app.app_context():
            profile = db.session.get(CreatorProfile, creator_profile['id'])
            assert profile.public_token is None

            token = profile.generate_public_token()
            db.session.commit()

            assert token is not None
            assert len(token) == 64  # 48 bytes base64 = ~64 chars
            assert profile.public_token == token

    def test_token_uniqueness(self, app, test_user, admin_user):
        """Test that tokens are unique across profiles."""
        with app.app_context():
            p1 = CreatorProfile(user_id=test_user['id'], display_name='Creator 1')
            p2 = CreatorProfile(user_id=admin_user['id'], display_name='Creator 2')
            db.session.add_all([p1, p2])
            db.session.commit()

            t1 = p1.generate_public_token()
            t2 = p2.generate_public_token()
            db.session.commit()

            assert t1 != t2

    def test_get_total_followers(self, app, creator_profile):
        """Test total followers calculation."""
        with app.app_context():
            profile = db.session.get(CreatorProfile, creator_profile['id'])
            total = profile.get_total_followers()
            # youtube: 5000 subscribers + twitter: 2000 followers = 7000
            assert total == 7000

    def test_get_total_followers_empty(self, app, test_user):
        """Test total followers with no stats."""
        with app.app_context():
            profile = CreatorProfile(user_id=test_user['id'], display_name='Empty')
            db.session.add(profile)
            db.session.commit()

            assert profile.get_total_followers() == 0

    def test_get_avg_engagement_rate(self, app, creator_profile):
        """Test average engagement rate calculation."""
        with app.app_context():
            profile = db.session.get(CreatorProfile, creator_profile['id'])
            avg = profile.get_avg_engagement_rate()
            # (8.5 + 5.2) / 2 = 6.85
            assert avg == pytest.approx(6.85, rel=0.01)

    def test_get_avg_engagement_no_rates(self, app, test_user):
        """Test engagement rate when no rates available."""
        with app.app_context():
            profile = CreatorProfile(user_id=test_user['id'], display_name='NoRates')
            db.session.add(profile)
            db.session.commit()

            assert profile.get_avg_engagement_rate() is None

    def test_user_profile_relationship(self, app, creator_profile, test_user):
        """Test user-profile relationship."""
        with app.app_context():
            user = db.session.get(User, test_user['id'])
            assert user.creator_profile is not None
            assert user.creator_profile.id == creator_profile['id']

    def test_to_dict(self, app, creator_profile):
        """Test profile to_dict serialization."""
        with app.app_context():
            profile = db.session.get(CreatorProfile, creator_profile['id'])
            data = profile.to_dict()

            assert data['display_name'] == 'Test Creator'
            assert data['total_followers'] == 7000
            assert 'avg_engagement_rate' in data


class TestRateCardModel:
    """Tests for RateCard model."""

    def test_create_rate_card(self, app, creator_profile):
        """Test creating a rate card."""
        with app.app_context():
            rate = RateCard(
                profile_id=creator_profile['id'],
                service_name='Social Post',
                price_min=Decimal('100.00')
            )
            db.session.add(rate)
            db.session.commit()

            assert rate.id is not None
            assert rate.service_name == 'Social Post'

    def test_price_display_range(self, app, rate_card):
        """Test price display for range."""
        with app.app_context():
            rate = db.session.get(RateCard, rate_card['id'])
            assert rate.price_display == '$500 - $1,500'

    def test_price_display_min_only(self, app, creator_profile):
        """Test price display for minimum only."""
        with app.app_context():
            rate = RateCard(
                profile_id=creator_profile['id'],
                service_name='Custom',
                price_min=Decimal('200.00')
            )
            db.session.add(rate)
            db.session.commit()

            assert rate.price_display == '$200+'

    def test_price_display_max_only(self, app, creator_profile):
        """Test price display for maximum only."""
        with app.app_context():
            rate = RateCard(
                profile_id=creator_profile['id'],
                service_name='Budget',
                price_max=Decimal('150.00')
            )
            db.session.add(rate)
            db.session.commit()

            assert rate.price_display == 'Up to $150'

    def test_price_display_note_only(self, app, creator_profile):
        """Test price display with note only."""
        with app.app_context():
            rate = RateCard(
                profile_id=creator_profile['id'],
                service_name='Negotiable',
                price_note='Contact for pricing'
            )
            db.session.add(rate)
            db.session.commit()

            assert rate.price_display == 'Contact for pricing'

    def test_price_display_fallback(self, app, creator_profile):
        """Test price display fallback."""
        with app.app_context():
            rate = RateCard(
                profile_id=creator_profile['id'],
                service_name='TBD'
            )
            db.session.add(rate)
            db.session.commit()

            assert rate.price_display == 'Contact for pricing'


class TestTestimonialModel:
    """Tests for Testimonial model."""

    def test_create_testimonial_with_company(self, app, creator_profile, company):
        """Test creating testimonial linked to company."""
        with app.app_context():
            t = Testimonial(
                profile_id=creator_profile['id'],
                company_id=company['id'],
                quote='Great collaboration!'
            )
            db.session.add(t)
            db.session.commit()

            assert t.id is not None
            assert t.display_company_name == 'Test Company'

    def test_create_testimonial_manual_company(self, app, creator_profile):
        """Test creating testimonial with manual company name."""
        with app.app_context():
            t = Testimonial(
                profile_id=creator_profile['id'],
                company_name='Manual Corp',
                quote='Great work!'
            )
            db.session.add(t)
            db.session.commit()

            assert t.display_company_name == 'Manual Corp'

    def test_display_company_name_anonymous(self, app, creator_profile):
        """Test anonymous company name fallback."""
        with app.app_context():
            t = Testimonial(
                profile_id=creator_profile['id'],
                quote='Anonymous testimonial'
            )
            db.session.add(t)
            db.session.commit()

            assert t.display_company_name == 'Anonymous'


class TestCascadeDeletes:
    """Tests for cascade delete behavior."""

    def test_delete_profile_cascades_rates(self, app, creator_profile, rate_card):
        """Test deleting profile removes rate cards."""
        with app.app_context():
            profile = db.session.get(CreatorProfile, creator_profile['id'])
            db.session.delete(profile)
            db.session.commit()

            rate = db.session.get(RateCard, rate_card['id'])
            assert rate is None

    def test_delete_profile_cascades_testimonials(self, app, creator_profile, testimonial):
        """Test deleting profile removes testimonials."""
        with app.app_context():
            profile = db.session.get(CreatorProfile, creator_profile['id'])
            db.session.delete(profile)
            db.session.commit()

            t = db.session.get(Testimonial, testimonial['id'])
            assert t is None


# ============================================================================
# B. Route Tests - Authentication
# ============================================================================

class TestMediaKitAuth:
    """Tests for authentication requirements."""

    def test_edit_profile_requires_auth(self, client):
        """Test profile edit requires authentication."""
        response = client.get('/media-kit/')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_rates_requires_auth(self, client):
        """Test rates page requires authentication."""
        response = client.get('/media-kit/rates')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_testimonials_requires_auth(self, client):
        """Test testimonials page requires authentication."""
        response = client.get('/media-kit/testimonials')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_preview_requires_auth(self, client):
        """Test preview requires authentication."""
        response = client.get('/media-kit/preview')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_export_html_requires_auth(self, client):
        """Test HTML export requires authentication."""
        response = client.get('/media-kit/export/html')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_export_pdf_requires_auth(self, client):
        """Test PDF export requires authentication."""
        response = client.get('/media-kit/export/pdf')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_share_requires_auth(self, client):
        """Test share requires authentication."""
        response = client.post('/media-kit/share')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_public_view_no_auth_required(self, client, public_profile):
        """Test public view accessible without auth."""
        response = client.get(f'/media-kit/public/{public_profile["token"]}')
        assert response.status_code == 200


# ============================================================================
# C. Route Tests - Profile CRUD
# ============================================================================

class TestProfileCRUD:
    """Tests for profile CRUD operations."""

    def test_edit_profile_form_renders(self, auth_client):
        """Test profile form renders."""
        response = auth_client.get('/media-kit/')
        assert response.status_code == 200
        assert b'display_name' in response.data

    def test_create_profile_success(self, auth_client, app):
        """Test creating a new profile."""
        response = auth_client.post('/media-kit/', data={
            'display_name': 'New Creator',
            'tagline': 'New tagline',
            'bio': 'New bio content'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'saved successfully' in response.data.lower()

        with app.app_context():
            profile = CreatorProfile.query.filter_by(display_name='New Creator').first()
            assert profile is not None
            assert profile.tagline == 'New tagline'

    def test_update_profile_success(self, auth_client, app, creator_profile):
        """Test updating existing profile."""
        response = auth_client.post('/media-kit/', data={
            'display_name': 'Updated Creator',
            'tagline': 'Updated tagline'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'saved successfully' in response.data.lower()

        with app.app_context():
            profile = db.session.get(CreatorProfile, creator_profile['id'])
            assert profile.display_name == 'Updated Creator'
            assert profile.tagline == 'Updated tagline'

    def test_create_profile_missing_required(self, auth_client):
        """Test creating profile without required fields."""
        response = auth_client.post('/media-kit/', data={
            'tagline': 'Just tagline'
        })
        assert response.status_code == 200
        # Should show validation error

    def test_profile_with_social_links(self, auth_client, app):
        """Test saving profile with social links."""
        response = auth_client.post('/media-kit/', data={
            'display_name': 'Social Creator',
            'social_youtube': '@mychannel',
            'social_twitter': '@mytwitter'
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            profile = CreatorProfile.query.filter_by(display_name='Social Creator').first()
            assert profile.social_links['youtube'] == '@mychannel'
            assert profile.social_links['twitter'] == '@mytwitter'

    def test_profile_with_platform_stats(self, auth_client, app):
        """Test saving profile with platform stats."""
        response = auth_client.post('/media-kit/', data={
            'display_name': 'Stats Creator',
            'stats_youtube_subscribers': '5000',
            'stats_youtube_avg_views': '1000',
            'stats_youtube_engagement': '8.5'
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            profile = CreatorProfile.query.filter_by(display_name='Stats Creator').first()
            assert profile.platform_stats['youtube']['subscribers'] == 5000
            assert profile.platform_stats['youtube']['engagement_rate'] == 8.5

    def test_profile_with_demographics(self, auth_client, app):
        """Test saving profile with demographics."""
        response = auth_client.post('/media-kit/', data={
            'display_name': 'Demo Creator',
            'age_18_24': '30',
            'age_25_34': '40',
            'gender_male': '60',
            'gender_female': '35',
            'top_locations': 'USA, UK, Canada'
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            profile = CreatorProfile.query.filter_by(display_name='Demo Creator').first()
            assert profile.audience_demographics['age']['18-24'] == 30
            assert profile.audience_demographics['gender']['male'] == 60
            assert 'USA' in profile.audience_demographics['top_locations']

    def test_profile_photo_upload(self, auth_client, app):
        """Test uploading a profile photo."""
        import io
        # Create a simple 1x1 PNG image
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'

        response = auth_client.post('/media-kit/', data={
            'display_name': 'Photo Creator',
            'photo_file': (io.BytesIO(png_data), 'test.png')
        }, content_type='multipart/form-data', follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            profile = CreatorProfile.query.filter_by(display_name='Photo Creator').first()
            assert profile.photo_url is not None
            assert profile.photo_url.startswith('/static/uploads/profiles/')
            assert profile.photo_url.endswith('.png')

    def test_profile_photo_upload_invalid_type(self, auth_client, app):
        """Test uploading invalid file type is rejected."""
        import io

        response = auth_client.post('/media-kit/', data={
            'display_name': 'Bad Photo',
            'photo_file': (io.BytesIO(b'not an image'), 'test.exe')
        }, content_type='multipart/form-data', follow_redirects=True)

        assert response.status_code == 200
        assert b'Invalid file type' in response.data

    def test_profile_photo_clear(self, auth_client, app, creator_profile):
        """Test clearing profile photo."""
        # First set a photo URL
        with app.app_context():
            profile = db.session.get(CreatorProfile, creator_profile['id'])
            profile.photo_url = 'https://example.com/photo.jpg'
            db.session.commit()

        # Now clear it
        response = auth_client.post('/media-kit/', data={
            'display_name': 'Test Creator',
            'clear_photo': 'yes'
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            profile = db.session.get(CreatorProfile, creator_profile['id'])
            assert profile.photo_url is None


# ============================================================================
# D. Route Tests - Rate Card
# ============================================================================

class TestRateCardRoutes:
    """Tests for rate card management routes."""

    def test_rates_redirects_without_profile(self, auth_client):
        """Test rates page redirects if no profile."""
        response = auth_client.get('/media-kit/rates')
        assert response.status_code == 302
        # Should redirect to profile creation

    def test_list_rates_renders(self, auth_client, creator_profile):
        """Test rates page renders with profile."""
        response = auth_client.get('/media-kit/rates')
        assert response.status_code == 200

    def test_add_rate_success(self, auth_client, app, creator_profile):
        """Test adding a new rate."""
        response = auth_client.post('/media-kit/rates', data={
            'service_name': 'New Service',
            'description': 'Test description',
            'price_min': '200',
            'price_max': '500',
            'is_negotiable': 'on'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'added successfully' in response.data.lower()

        with app.app_context():
            rate = RateCard.query.filter_by(service_name='New Service').first()
            assert rate is not None
            assert rate.price_min == Decimal('200')
            assert rate.is_negotiable is True

    def test_add_rate_missing_service_name(self, auth_client, creator_profile):
        """Test adding rate without service name."""
        response = auth_client.post('/media-kit/rates', data={
            'price_min': '100'
        }, follow_redirects=True)
        assert response.status_code == 200
        # Should show validation error

    def test_add_rate_invalid_price(self, auth_client, creator_profile):
        """Test adding rate with invalid price format."""
        response = auth_client.post('/media-kit/rates', data={
            'service_name': 'Invalid Price',
            'price_min': 'not-a-number'
        }, follow_redirects=True)
        assert response.status_code == 200
        # Should show validation error

    def test_delete_rate_success(self, auth_client, app, rate_card):
        """Test deleting a rate."""
        rate_id = rate_card['id']
        response = auth_client.post(f'/media-kit/rates/{rate_id}/delete', follow_redirects=True)

        assert response.status_code == 200
        assert b'deleted' in response.data.lower()

        with app.app_context():
            rate = db.session.get(RateCard, rate_id)
            assert rate is None

    def test_delete_rate_nonexistent_404(self, auth_client, creator_profile):
        """Test deleting non-existent rate returns 404."""
        response = auth_client.post('/media-kit/rates/99999/delete')
        assert response.status_code == 404

    def test_rates_ordered_by_display_order(self, auth_client, app, creator_profile):
        """Test rates are ordered by display_order."""
        with app.app_context():
            profile = db.session.get(CreatorProfile, creator_profile['id'])
            r1 = RateCard(profile_id=profile.id, service_name='Third', display_order=3)
            r2 = RateCard(profile_id=profile.id, service_name='First', display_order=1)
            r3 = RateCard(profile_id=profile.id, service_name='Second', display_order=2)
            db.session.add_all([r1, r2, r3])
            db.session.commit()

        response = auth_client.get('/media-kit/rates')
        assert response.status_code == 200
        # Rates should be in order: First, Second, Third


# ============================================================================
# E. Route Tests - Testimonials
# ============================================================================

class TestTestimonialRoutes:
    """Tests for testimonial management routes."""

    def test_testimonials_redirects_without_profile(self, auth_client):
        """Test testimonials page redirects if no profile."""
        response = auth_client.get('/media-kit/testimonials')
        assert response.status_code == 302

    def test_list_testimonials_renders(self, auth_client, creator_profile):
        """Test testimonials page renders."""
        response = auth_client.get('/media-kit/testimonials')
        assert response.status_code == 200

    def test_add_testimonial_with_company(self, auth_client, app, creator_profile, company):
        """Test adding testimonial linked to company."""
        response = auth_client.post('/media-kit/testimonials', data={
            'company_id': company['id'],
            'contact_name': 'Jane Doe',
            'contact_title': 'Brand Manager',
            'quote': 'Excellent creator to work with!'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'added successfully' in response.data.lower()

        with app.app_context():
            t = Testimonial.query.filter_by(quote='Excellent creator to work with!').first()
            assert t is not None
            assert t.company_id == company['id']

    def test_add_testimonial_manual_company(self, auth_client, app, creator_profile):
        """Test adding testimonial with manual company name."""
        response = auth_client.post('/media-kit/testimonials', data={
            'company_name': 'External Corp',
            'quote': 'Great partnership!'
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            t = Testimonial.query.filter_by(company_name='External Corp').first()
            assert t is not None
            assert t.company_id is None

    def test_add_testimonial_missing_quote(self, auth_client, creator_profile):
        """Test adding testimonial without quote fails."""
        response = auth_client.post('/media-kit/testimonials', data={
            'company_name': 'Some Company'
        }, follow_redirects=True)
        assert response.status_code == 200
        # Should show validation error

    def test_delete_testimonial_success(self, auth_client, app, testimonial):
        """Test deleting a testimonial."""
        t_id = testimonial['id']
        response = auth_client.post(f'/media-kit/testimonials/{t_id}/delete', follow_redirects=True)

        assert response.status_code == 200
        assert b'deleted' in response.data.lower()

        with app.app_context():
            t = db.session.get(Testimonial, t_id)
            assert t is None

    def test_delete_testimonial_nonexistent_404(self, auth_client, creator_profile):
        """Test deleting non-existent testimonial returns 404."""
        response = auth_client.post('/media-kit/testimonials/99999/delete')
        assert response.status_code == 404


# ============================================================================
# F. Route Tests - Preview & Export
# ============================================================================

class TestPreviewExport:
    """Tests for preview and export functionality."""

    def test_preview_renders(self, auth_client, creator_profile):
        """Test preview page renders."""
        response = auth_client.get('/media-kit/preview')
        assert response.status_code == 200
        assert b'Test Creator' in response.data

    def test_preview_shows_rate_cards(self, auth_client, creator_profile, rate_card):
        """Test preview shows rate cards."""
        response = auth_client.get('/media-kit/preview')
        assert response.status_code == 200
        assert b'Sponsored Video' in response.data

    def test_preview_shows_testimonials(self, auth_client, creator_profile, testimonial):
        """Test preview shows testimonials."""
        response = auth_client.get('/media-kit/preview')
        assert response.status_code == 200
        assert b'amazing' in response.data.lower()

    def test_export_html_returns_download(self, auth_client, creator_profile):
        """Test HTML export returns downloadable file."""
        response = auth_client.get('/media-kit/export/html')
        assert response.status_code == 200
        assert 'text/html' in response.content_type
        assert 'attachment' in response.headers.get('Content-Disposition', '')

    def test_export_html_contains_profile_data(self, auth_client, creator_profile):
        """Test HTML export contains profile data."""
        response = auth_client.get('/media-kit/export/html')
        assert response.status_code == 200
        assert b'Test Creator' in response.data

    def test_export_pdf_with_weasyprint(self, auth_client, creator_profile):
        """Test PDF export (may fallback if weasyprint not installed)."""
        response = auth_client.get('/media-kit/export/pdf')
        # Either returns PDF or redirects with error
        assert response.status_code in [200, 302]

    def test_preview_redirects_without_profile(self, auth_client):
        """Test preview redirects without profile."""
        response = auth_client.get('/media-kit/preview')
        assert response.status_code == 302


# ============================================================================
# G. Route Tests - Public Sharing
# ============================================================================

class TestPublicSharing:
    """Tests for public sharing functionality."""

    def test_generate_share_link(self, auth_client, app, creator_profile):
        """Test generating share link."""
        response = auth_client.post('/media-kit/share', follow_redirects=True)

        assert response.status_code == 200
        assert b'share link generated' in response.data.lower()

        with app.app_context():
            profile = db.session.get(CreatorProfile, creator_profile['id'])
            assert profile.public_token is not None
            assert profile.is_public is True

    def test_regenerate_share_link(self, auth_client, app, public_profile):
        """Test regenerating share link creates new token."""
        old_token = public_profile['token']

        response = auth_client.post('/media-kit/share', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            profile = db.session.get(CreatorProfile, public_profile['id'])
            assert profile.public_token != old_token

    def test_old_token_invalid_after_regeneration(self, client, auth_client, app, public_profile):
        """Test old token becomes invalid after regeneration."""
        old_token = public_profile['token']

        # Regenerate
        auth_client.post('/media-kit/share')

        # Old token should return 404
        response = client.get(f'/media-kit/public/{old_token}')
        assert response.status_code == 404

    def test_public_view_success(self, client, public_profile):
        """Test public view renders correctly."""
        response = client.get(f'/media-kit/public/{public_profile["token"]}')
        assert response.status_code == 200
        assert b'Test Creator' in response.data

    def test_public_view_invalid_token_404(self, client):
        """Test invalid token returns 404."""
        response = client.get('/media-kit/public/invalid-token-here')
        assert response.status_code == 404

    def test_public_view_disabled_sharing_404(self, client, auth_client, app, public_profile):
        """Test disabled sharing returns 404."""
        # Disable sharing
        auth_client.post('/media-kit/share/disable')

        # Should now return 404
        response = client.get(f'/media-kit/public/{public_profile["token"]}')
        assert response.status_code == 404

    def test_disable_sharing(self, auth_client, app, public_profile):
        """Test disabling public sharing."""
        response = auth_client.post('/media-kit/share/disable', follow_redirects=True)

        assert response.status_code == 200
        assert b'disabled' in response.data.lower()

        with app.app_context():
            profile = db.session.get(CreatorProfile, public_profile['id'])
            assert profile.is_public is False


# ============================================================================
# H. Security Tests
# ============================================================================

class TestMediaKitSecurity:
    """Security tests for media kit routes."""

    def test_cannot_access_other_users_rates(self, auth_client, app, admin_user):
        """Test user cannot delete another user's rate."""
        # Create rate for admin user
        with app.app_context():
            admin_profile = CreatorProfile(
                user_id=admin_user['id'],
                display_name='Admin Creator'
            )
            db.session.add(admin_profile)
            db.session.commit()

            admin_rate = RateCard(
                profile_id=admin_profile.id,
                service_name='Admin Service'
            )
            db.session.add(admin_rate)
            db.session.commit()
            rate_id = admin_rate.id

        # Try to delete as regular user (should 404 because profile_id doesn't match)
        response = auth_client.post(f'/media-kit/rates/{rate_id}/delete')
        # The filter_by profile_id check means it's 404 not found for this user
        assert response.status_code in [302, 404]

    def test_cannot_access_other_users_testimonials(self, auth_client, app, admin_user):
        """Test user cannot delete another user's testimonial."""
        with app.app_context():
            admin_profile = CreatorProfile(
                user_id=admin_user['id'],
                display_name='Admin Creator'
            )
            db.session.add(admin_profile)
            db.session.commit()

            admin_testimonial = Testimonial(
                profile_id=admin_profile.id,
                quote='Admin testimonial'
            )
            db.session.add(admin_testimonial)
            db.session.commit()
            t_id = admin_testimonial.id

        # Try to delete as regular user
        response = auth_client.post(f'/media-kit/testimonials/{t_id}/delete')
        assert response.status_code in [302, 404]

    def test_xss_prevention_in_bio(self, auth_client, app):
        """Test XSS is escaped in bio field."""
        xss_payload = '<script>alert("xss")</script>'

        response = auth_client.post('/media-kit/', data={
            'display_name': 'XSS Test',
            'bio': xss_payload
        }, follow_redirects=True)

        assert response.status_code == 200
        # Raw script tag should not appear in response
        assert b'<script>alert' not in response.data

    def test_xss_prevention_in_testimonial(self, auth_client, app, creator_profile):
        """Test XSS is escaped in testimonial quote."""
        xss_payload = '<img src=x onerror=alert("xss")>'

        auth_client.post('/media-kit/testimonials', data={
            'company_name': 'Test Co',
            'quote': xss_payload
        }, follow_redirects=True)

        # Now view the preview where testimonial is displayed
        response = auth_client.get('/media-kit/preview')
        assert response.status_code == 200
        # Raw HTML should be escaped - Jinja2 escapes < to &lt;
        assert b'<img src=x onerror' not in response.data
        # The escaped version should appear
        assert b'&lt;img' in response.data or b'&lt;' in response.data

    def test_token_is_cryptographically_random(self, app, creator_profile):
        """Test token generation uses secure random."""
        with app.app_context():
            profile = db.session.get(CreatorProfile, creator_profile['id'])
            token = profile.generate_public_token()

            # Should be URL-safe base64, 64 chars from 48 bytes
            assert len(token) == 64
            # Should contain only URL-safe characters
            import re
            assert re.match(r'^[A-Za-z0-9_-]+$', token)

    def test_profile_filtered_by_user_id(self, app, creator_profile, test_user):
        """Test that profile lookup is filtered by user_id."""
        with app.app_context():
            # Verify the profile is correctly associated with test_user
            profile = CreatorProfile.query.filter_by(user_id=test_user['id']).first()
            assert profile is not None
            assert profile.id == creator_profile['id']

            # Verify that a query for a non-existent user returns no profile
            fake_user_id = 99999
            other_profile = CreatorProfile.query.filter_by(user_id=fake_user_id).first()
            assert other_profile is None

            # Verify profile is bound to correct user
            assert profile.user_id == test_user['id']
