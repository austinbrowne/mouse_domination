"""Tests for slug generation and publish validation."""
import pytest
from extensions import db
from models import Inventory
from scripts.generate_slugs import slugify, generate_slugs


@pytest.fixture
def user(app, test_user):
    return test_user['id']


# ---------------------------------------------------------------------------
# Slug generation
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_basic_name(self):
        assert slugify('Razer Viper V3 Pro') == 'razer-viper-v3-pro'

    def test_special_characters(self):
        assert slugify('Logitech G Pro X Superlight 2!') == 'logitech-g-pro-x-superlight-2'

    def test_multiple_spaces(self):
        assert slugify('Finalmouse   UltralightX') == 'finalmouse-ultralightx'

    def test_leading_trailing_hyphens(self):
        assert slugify('  -Razer-  ') == 'razer'

    def test_empty_name_fallback(self):
        assert slugify('---') == 'product'

    def test_unicode(self):
        assert slugify('Pulsar X2 Mini (2nd Gen)') == 'pulsar-x2-mini-2nd-gen'

    def test_none_returns_product(self):
        assert slugify(None) == 'product'

    def test_empty_string_returns_product(self):
        assert slugify('') == 'product'

    def test_numeric_only(self):
        assert slugify('12345') == '12345'

    def test_non_ascii_only_fallback(self):
        assert slugify('\u00e9\u00e8\u00ea') == 'product'


class TestGenerateSlugs:
    def test_generates_slugs_for_items_without(self, app, user):
        with app.app_context():
            item = Inventory(user_id=user, product_name='Test Mouse', cost=0.0)
            db.session.add(item)
            db.session.commit()

            count = generate_slugs()

            db.session.refresh(item)
            assert item.slug == 'test-mouse'
            assert count == 1

    def test_skips_items_with_existing_slug(self, app, user):
        with app.app_context():
            item = Inventory(user_id=user, product_name='Test Mouse', slug='custom-slug', cost=0.0)
            db.session.add(item)
            db.session.commit()

            count = generate_slugs()

            db.session.refresh(item)
            assert item.slug == 'custom-slug'
            assert count == 0

    def test_handles_duplicate_names(self, app, user):
        with app.app_context():
            item1 = Inventory(user_id=user, product_name='Test Mouse', slug='test-mouse', cost=0.0)
            item2 = Inventory(user_id=user, product_name='Test Mouse', cost=0.0)
            db.session.add_all([item1, item2])
            db.session.commit()

            count = generate_slugs()

            db.session.refresh(item2)
            assert item2.slug == 'test-mouse-2'
            assert count == 1

    def test_handles_multiple_duplicates(self, app, user):
        with app.app_context():
            existing = Inventory(user_id=user, product_name='Mouse', slug='mouse', cost=0.0)
            dup1 = Inventory(user_id=user, product_name='Mouse', cost=0.0)
            dup2 = Inventory(user_id=user, product_name='Mouse', cost=0.0)
            db.session.add_all([existing, dup1, dup2])
            db.session.commit()

            count = generate_slugs()

            db.session.refresh(dup1)
            db.session.refresh(dup2)
            slugs = {dup1.slug, dup2.slug}
            assert slugs == {'mouse-2', 'mouse-3'}
            assert count == 2

    def test_dry_run_does_not_save(self, app, user):
        with app.app_context():
            item = Inventory(user_id=user, product_name='Dry Run Mouse', cost=0.0)
            db.session.add(item)
            db.session.commit()
            item_id = item.id

            count = generate_slugs(dry_run=True)

            fresh = db.session.get(Inventory, item_id)
            assert fresh.slug is None
            assert count == 1


# ---------------------------------------------------------------------------
# Publish validation
# ---------------------------------------------------------------------------

class TestPublishValidation:
    def _make_item(self, user, **overrides):
        defaults = {
            'user_id': user,
            'product_name': 'Test Product',
            'category': 'mouse',
            'slug': 'test-product',
            'short_verdict': 'Great mouse',
            'rating': 8,
            'cost': 0.0,
        }
        defaults.update(overrides)
        return Inventory(**defaults)

    def test_valid_item_has_no_missing_fields(self, app, user):
        with app.app_context():
            item = self._make_item(user)
            assert item.validate_publishable() == []

    def test_missing_slug(self, app, user):
        with app.app_context():
            item = self._make_item(user, slug=None)
            missing = item.validate_publishable()
            assert 'slug' in missing

    def test_empty_string_slug_rejected(self, app, user):
        with app.app_context():
            item = self._make_item(user, slug='')
            missing = item.validate_publishable()
            assert 'slug' in missing

    def test_missing_short_verdict(self, app, user):
        with app.app_context():
            item = self._make_item(user, short_verdict=None)
            missing = item.validate_publishable()
            assert 'short_verdict' in missing

    def test_empty_string_verdict_rejected(self, app, user):
        with app.app_context():
            item = self._make_item(user, short_verdict='')
            missing = item.validate_publishable()
            assert 'short_verdict' in missing

    def test_missing_rating(self, app, user):
        with app.app_context():
            item = self._make_item(user, rating=None)
            missing = item.validate_publishable()
            assert 'rating' in missing

    def test_rating_zero_rejected(self, app, user):
        with app.app_context():
            item = self._make_item(user, rating=0)
            missing = item.validate_publishable()
            assert any('rating' in m for m in missing)

    def test_rating_negative_rejected(self, app, user):
        with app.app_context():
            item = self._make_item(user, rating=-1)
            missing = item.validate_publishable()
            assert any('rating' in m for m in missing)

    def test_rating_eleven_rejected(self, app, user):
        with app.app_context():
            item = self._make_item(user, rating=11)
            missing = item.validate_publishable()
            assert any('rating' in m for m in missing)

    def test_rating_boundary_one_valid(self, app, user):
        with app.app_context():
            item = self._make_item(user, rating=1)
            missing = item.validate_publishable()
            assert not any('rating' in m for m in missing)

    def test_rating_boundary_ten_valid(self, app, user):
        with app.app_context():
            item = self._make_item(user, rating=10)
            missing = item.validate_publishable()
            assert not any('rating' in m for m in missing)

    def test_category_other_rejected(self, app, user):
        with app.app_context():
            item = self._make_item(user, category='other')
            missing = item.validate_publishable()
            assert 'category' in missing

    def test_empty_category_rejected(self, app, user):
        with app.app_context():
            item = self._make_item(user, category='')
            missing = item.validate_publishable()
            assert 'category' in missing

    def test_none_category_rejected(self, app, user):
        with app.app_context():
            item = self._make_item(user, category=None)
            missing = item.validate_publishable()
            assert 'category' in missing

    def test_multiple_missing_fields(self, app, user):
        with app.app_context():
            item = self._make_item(user, slug=None, rating=None, category='other')
            missing = item.validate_publishable()
            assert len(missing) == 3
            assert 'slug' in missing
            assert 'rating' in missing
            assert 'category' in missing
