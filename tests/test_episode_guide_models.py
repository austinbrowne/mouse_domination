"""Tests for Episode Guide models."""
import pytest
from models import EpisodeGuide, EpisodeGuideItem
from extensions import db


class TestEpisodeGuideModel:
    """Tests for EpisodeGuide model."""

    def test_create_guide(self, app):
        """Test creating a guide with required fields."""
        with app.app_context():
            guide = EpisodeGuide(title='Test Episode')
            db.session.add(guide)
            db.session.commit()

            assert guide.id is not None
            assert guide.title == 'Test Episode'

    def test_guide_defaults(self, app):
        """Test guide default values."""
        with app.app_context():
            guide = EpisodeGuide(title='Test')
            db.session.add(guide)
            db.session.commit()

            assert guide.status == 'draft'
            assert guide.created_at is not None
            assert guide.updated_at is not None
            assert guide.episode_number is None
            assert guide.notes is None

    def test_guide_to_dict(self, app):
        """Test guide serialization."""
        with app.app_context():
            guide = EpisodeGuide(
                title='Test Episode',
                episode_number=42,
                status='draft',
                notes='Test notes'
            )
            db.session.add(guide)
            db.session.commit()

            data = guide.to_dict()
            assert data['id'] == guide.id
            assert data['title'] == 'Test Episode'
            assert data['episode_number'] == 42
            assert data['status'] == 'draft'
            assert data['notes'] == 'Test notes'

    def test_formatted_duration_none(self, app):
        """Test formatted_duration when duration is None."""
        with app.app_context():
            guide = EpisodeGuide(title='Test')
            db.session.add(guide)
            db.session.commit()

            assert guide.formatted_duration is None

    def test_formatted_duration_minutes_seconds(self, app):
        """Test formatted_duration for MM:SS format."""
        with app.app_context():
            guide = EpisodeGuide(title='Test', total_duration_seconds=125)
            db.session.add(guide)
            db.session.commit()

            assert guide.formatted_duration == '02:05'

    def test_formatted_duration_hours(self, app):
        """Test formatted_duration for HH:MM:SS format."""
        with app.app_context():
            guide = EpisodeGuide(title='Test', total_duration_seconds=3725)
            db.session.add(guide)
            db.session.commit()

            assert guide.formatted_duration == '1:02:05'

    def test_items_relationship(self, app):
        """Test guide.items relationship."""
        with app.app_context():
            guide = EpisodeGuide(title='Test')
            db.session.add(guide)
            db.session.commit()

            item = EpisodeGuideItem(
                guide_id=guide.id,
                section='introduction',
                title='Test Item'
            )
            db.session.add(item)
            db.session.commit()

            assert len(guide.items) == 1
            assert guide.items[0].title == 'Test Item'

    def test_cascade_delete(self, app):
        """Test deleting guide cascades to items."""
        with app.app_context():
            guide = EpisodeGuide(title='Test')
            db.session.add(guide)
            db.session.commit()
            guide_id = guide.id

            item = EpisodeGuideItem(
                guide_id=guide_id,
                section='introduction',
                title='Test Item'
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

            # Delete guide
            db.session.delete(guide)
            db.session.commit()

            # Item should be gone
            assert EpisodeGuideItem.query.get(item_id) is None


class TestEpisodeGuideItemModel:
    """Tests for EpisodeGuideItem model."""

    def test_create_item(self, app, guide):
        """Test creating an item with required fields."""
        with app.app_context():
            item = EpisodeGuideItem(
                guide_id=guide['id'],
                section='introduction',
                title='Test Item'
            )
            db.session.add(item)
            db.session.commit()

            assert item.id is not None
            assert item.title == 'Test Item'
            assert item.section == 'introduction'

    def test_item_with_links_array(self, app, guide):
        """Test creating item with links JSON array."""
        with app.app_context():
            item = EpisodeGuideItem(
                guide_id=guide['id'],
                section='introduction',
                title='Test Item',
                links=['https://example.com', 'https://test.com']
            )
            db.session.add(item)
            db.session.commit()

            # Reload from db
            item = db.session.get(EpisodeGuideItem, item.id)
            assert item.links == ['https://example.com', 'https://test.com']

    def test_all_links_from_links_field(self, app, guide):
        """Test all_links property returns links array."""
        with app.app_context():
            item = EpisodeGuideItem(
                guide_id=guide['id'],
                section='introduction',
                title='Test Item',
                links=['https://a.com', 'https://b.com']
            )
            db.session.add(item)
            db.session.commit()

            assert item.all_links == ['https://a.com', 'https://b.com']

    def test_all_links_from_legacy_link(self, app, guide):
        """Test all_links property returns [link] for legacy data."""
        with app.app_context():
            item = EpisodeGuideItem(
                guide_id=guide['id'],
                section='introduction',
                title='Test Item',
                link='https://legacy.com'  # Legacy single link field
            )
            db.session.add(item)
            db.session.commit()

            assert item.all_links == ['https://legacy.com']

    def test_all_links_empty(self, app, guide):
        """Test all_links returns empty list when both null."""
        with app.app_context():
            item = EpisodeGuideItem(
                guide_id=guide['id'],
                section='introduction',
                title='Test Item'
            )
            db.session.add(item)
            db.session.commit()

            assert item.all_links == []

    def test_all_links_prefers_links_over_link(self, app, guide):
        """Test all_links prefers links array over legacy link."""
        with app.app_context():
            item = EpisodeGuideItem(
                guide_id=guide['id'],
                section='introduction',
                title='Test Item',
                link='https://legacy.com',
                links=['https://new.com']
            )
            db.session.add(item)
            db.session.commit()

            # Should return links array, not legacy link
            assert item.all_links == ['https://new.com']

    def test_item_to_dict(self, app, guide):
        """Test item serialization includes links."""
        with app.app_context():
            item = EpisodeGuideItem(
                guide_id=guide['id'],
                section='introduction',
                title='Test Item',
                links=['https://example.com'],
                notes='Test notes'
            )
            db.session.add(item)
            db.session.commit()

            data = item.to_dict()
            assert data['title'] == 'Test Item'
            assert data['links'] == ['https://example.com']
            assert data['notes'] == 'Test notes'

    def test_formatted_timestamp_none(self, app, guide):
        """Test formatted_timestamp when timestamp is None."""
        with app.app_context():
            item = EpisodeGuideItem(
                guide_id=guide['id'],
                section='introduction',
                title='Test'
            )
            db.session.add(item)
            db.session.commit()

            assert item.formatted_timestamp is None

    def test_formatted_timestamp_minutes_seconds(self, app, guide):
        """Test formatted_timestamp for MM:SS format."""
        with app.app_context():
            item = EpisodeGuideItem(
                guide_id=guide['id'],
                section='introduction',
                title='Test',
                timestamp_seconds=125
            )
            db.session.add(item)
            db.session.commit()

            assert item.formatted_timestamp == '02:05'

    def test_formatted_timestamp_hours(self, app, guide):
        """Test formatted_timestamp for HH:MM:SS format."""
        with app.app_context():
            item = EpisodeGuideItem(
                guide_id=guide['id'],
                section='introduction',
                title='Test',
                timestamp_seconds=3725
            )
            db.session.add(item)
            db.session.commit()

            assert item.formatted_timestamp == '1:02:05'

    def test_item_position_defaults(self, app, guide):
        """Test item position default value."""
        with app.app_context():
            item = EpisodeGuideItem(
                guide_id=guide['id'],
                section='introduction',
                title='Test'
            )
            db.session.add(item)
            db.session.commit()

            assert item.position == 0
