import pytest
from app import db
from models import Contact, Company, Inventory, Video, PodcastEpisode, AffiliateRevenue
from datetime import date


class TestDashboard:
    """Tests for dashboard route."""

    def test_dashboard_loads(self, client):
        """Test dashboard renders successfully."""
        response = client.get('/')
        assert response.status_code == 200

    def test_dashboard_with_data(self, client, app):
        """Test dashboard shows correct stats."""
        with app.app_context():
            # Add some test data
            company = Company(name='Test Co', relationship_status='active')
            db.session.add(company)
            db.session.commit()

            item = Inventory(
                product_name='Test Mouse',
                company_id=company.id,
                status='in_queue',
            )
            db.session.add(item)
            db.session.commit()

        response = client.get('/')
        assert response.status_code == 200
        assert b'Test Mouse' in response.data or b'1' in response.data  # Shows count or item


class TestContactRoutes:
    """Tests for contact routes."""

    def test_list_contacts_empty(self, client):
        """Test contact list with no data."""
        response = client.get('/contacts/')
        assert response.status_code == 200

    def test_create_contact(self, client, app):
        """Test creating a new contact."""
        response = client.post('/contacts/new', data={
            'name': 'Test Person',
            'role': 'reviewer',
            'relationship_status': 'warm',
            'twitter': '@testperson',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            contact = Contact.query.filter_by(name='Test Person').first()
            assert contact is not None
            assert contact.role == 'reviewer'
            assert contact.twitter == '@testperson'

    def test_create_contact_with_company(self, client, app):
        """Test creating a contact linked to a company."""
        with app.app_context():
            company = Company(name='Pulsar')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = client.post('/contacts/new', data={
            'name': 'Pulsar Rep',
            'role': 'company_rep',
            'company_id': company_id,
            'email': 'rep@pulsar.gg',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            contact = Contact.query.filter_by(name='Pulsar Rep').first()
            assert contact.company.name == 'Pulsar'

    def test_edit_contact(self, client, app):
        """Test editing a contact."""
        with app.app_context():
            contact = Contact(name='Old Name', role='other')
            db.session.add(contact)
            db.session.commit()
            contact_id = contact.id

        response = client.post(f'/contacts/{contact_id}/edit', data={
            'name': 'New Name',
            'role': 'reviewer',
            'relationship_status': 'active',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            contact = Contact.query.get(contact_id)
            assert contact.name == 'New Name'
            assert contact.role == 'reviewer'

    def test_delete_contact(self, client, app):
        """Test deleting a contact."""
        with app.app_context():
            contact = Contact(name='To Delete')
            db.session.add(contact)
            db.session.commit()
            contact_id = contact.id

        response = client.post(f'/contacts/{contact_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            contact = Contact.query.get(contact_id)
            assert contact is None

    def test_filter_contacts_by_role(self, client, app):
        """Test filtering contacts by role."""
        with app.app_context():
            db.session.add(Contact(name='Reviewer 1', role='reviewer'))
            db.session.add(Contact(name='Company Rep', role='company_rep'))
            db.session.commit()

        response = client.get('/contacts/?role=reviewer')
        assert response.status_code == 200
        assert b'Reviewer 1' in response.data


class TestCompanyRoutes:
    """Tests for company routes."""

    def test_list_companies_empty(self, client):
        """Test company list with no data."""
        response = client.get('/companies/')
        assert response.status_code == 200

    def test_create_company(self, client, app):
        """Test creating a new company."""
        response = client.post('/companies/new', data={
            'name': 'Razer',
            'category': 'mice',
            'website': 'https://razer.com',
            'relationship_status': 'active',
            'affiliate_status': 'yes',
            'affiliate_code': 'DAZZ15',
            'commission_rate': '15',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            company = Company.query.filter_by(name='Razer').first()
            assert company is not None
            assert company.affiliate_code == 'DAZZ15'
            assert company.commission_rate == 15.0

    def test_create_duplicate_company_fails(self, client, app):
        """Test that duplicate company names are rejected."""
        with app.app_context():
            company = Company(name='Logitech')
            db.session.add(company)
            db.session.commit()

        response = client.post('/companies/new', data={
            'name': 'Logitech',
            'category': 'mice',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'already exists' in response.data

    def test_edit_company(self, client, app):
        """Test editing a company."""
        with app.app_context():
            company = Company(name='Test Co', affiliate_status='no')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = client.post(f'/companies/{company_id}/edit', data={
            'name': 'Test Co',
            'category': 'keyboards',
            'affiliate_status': 'yes',
            'affiliate_link': 'https://test.com?ref=dazz',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            company = Company.query.get(company_id)
            assert company.category == 'keyboards'
            assert company.affiliate_status == 'yes'

    def test_delete_company(self, client, app):
        """Test deleting a company."""
        with app.app_context():
            company = Company(name='To Delete')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = client.post(f'/companies/{company_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            company = Company.query.get(company_id)
            assert company is None


class TestInventoryRoutes:
    """Tests for inventory routes."""

    def test_list_inventory_empty(self, client):
        """Test inventory list with no data."""
        response = client.get('/inventory/')
        assert response.status_code == 200

    def test_create_review_unit(self, client, app):
        """Test creating a review unit."""
        response = client.post('/inventory/new', data={
            'product_name': 'Pulsar X2',
            'category': 'mouse',
            'source_type': 'review_unit',
            'cost': '0',
            'status': 'in_queue',
            'condition': 'new',
            'date_acquired': '2025-01-09',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.filter_by(product_name='Pulsar X2').first()
            assert item is not None
            assert item.source_type == 'review_unit'
            assert item.cost == 0.0

    def test_create_personal_purchase(self, client, app):
        """Test creating a personal purchase."""
        response = client.post('/inventory/new', data={
            'product_name': 'GPX Superlight',
            'category': 'mouse',
            'source_type': 'personal_purchase',
            'cost': '149.99',
            'status': 'keeping',
            'condition': 'new',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.filter_by(product_name='GPX Superlight').first()
            assert item.source_type == 'personal_purchase'
            assert item.cost == 149.99

    def test_create_item_with_company(self, client, app):
        """Test creating inventory linked to company."""
        with app.app_context():
            company = Company(name='Pulsar')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = client.post('/inventory/new', data={
            'product_name': 'Pulsar X2',
            'company_id': company_id,
            'category': 'mouse',
            'source_type': 'review_unit',
            'cost': '0',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.filter_by(product_name='Pulsar X2').first()
            assert item.company.name == 'Pulsar'

    def test_create_item_with_content_links(self, client, app):
        """Test creating inventory with video links."""
        response = client.post('/inventory/new', data={
            'product_name': 'Reviewed Mouse',
            'category': 'mouse',
            'source_type': 'review_unit',
            'cost': '0',
            'status': 'reviewed',
            'short_url': 'https://youtube.com/shorts/abc123',
            'short_publish_date': '2025-01-05',
            'video_url': 'https://youtube.com/watch?v=xyz789',
            'video_publish_date': '2025-01-08',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.filter_by(product_name='Reviewed Mouse').first()
            assert item.short_url == 'https://youtube.com/shorts/abc123'
            assert item.video_url == 'https://youtube.com/watch?v=xyz789'

    def test_create_sold_item(self, client, app):
        """Test creating a sold item with P/L tracking."""
        response = client.post('/inventory/new', data={
            'product_name': 'Sold Mouse',
            'category': 'mouse',
            'source_type': 'review_unit',
            'cost': '0',
            'status': 'sold',
            'sold': 'yes',
            'sale_price': '80',
            'fees': '10',
            'shipping': '5',
            'marketplace': 'ebay',
            'buyer': 'buyer123',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.filter_by(product_name='Sold Mouse').first()
            assert item.sold is True
            assert item.sale_price == 80.0
            assert item.profit_loss == 65.0  # 80 - 10 - 5

    def test_edit_item(self, client, app):
        """Test editing an inventory item."""
        with app.app_context():
            item = Inventory(product_name='Old Name', status='in_queue')
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        response = client.post(f'/inventory/{item_id}/edit', data={
            'product_name': 'New Name',
            'category': 'keyboard',
            'source_type': 'review_unit',
            'cost': '0',
            'status': 'reviewing',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.get(item_id)
            assert item.product_name == 'New Name'
            assert item.category == 'keyboard'
            assert item.status == 'reviewing'

    def test_delete_item(self, client, app):
        """Test deleting an inventory item."""
        with app.app_context():
            item = Inventory(product_name='To Delete')
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        response = client.post(f'/inventory/{item_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.get(item_id)
            assert item is None

    def test_mark_sold_action(self, client, app):
        """Test quick mark-as-sold action."""
        with app.app_context():
            item = Inventory(product_name='To Sell', status='listed')
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        response = client.post(f'/inventory/{item_id}/mark-sold', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            item = Inventory.query.get(item_id)
            assert item.sold is True
            assert item.status == 'sold'

    def test_filter_by_source_type(self, client, app):
        """Test filtering inventory by source type."""
        with app.app_context():
            db.session.add(Inventory(product_name='Review Unit', source_type='review_unit'))
            db.session.add(Inventory(product_name='Personal', source_type='personal_purchase'))
            db.session.commit()

        response = client.get('/inventory/?source_type=review_unit')
        assert response.status_code == 200
        assert b'Review Unit' in response.data

    def test_filter_by_sold_status(self, client, app):
        """Test filtering inventory by sold status."""
        with app.app_context():
            db.session.add(Inventory(product_name='Unsold Item', sold=False))
            db.session.add(Inventory(product_name='Sold Item', sold=True))
            db.session.commit()

        response = client.get('/inventory/?sold=yes')
        assert response.status_code == 200
        assert b'Sold Item' in response.data


class TestVideoRoutes:
    """Tests for video routes."""

    def test_list_videos_empty(self, client):
        """Test video list with no data."""
        response = client.get('/videos/')
        assert response.status_code == 200

    def test_create_video(self, client, app):
        """Test creating a new video."""
        response = client.post('/videos/new', data={
            'title': 'Pulsar X2 Review',
            'url': 'https://youtube.com/watch?v=abc123',
            'video_type': 'review',
            'publish_date': '2025-01-10',
            'views': '1500',
            'affiliate_links': 'yes',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            video = Video.query.filter_by(title='Pulsar X2 Review').first()
            assert video is not None
            assert video.video_type == 'review'
            assert video.views == 1500
            assert video.affiliate_links is True

    def test_create_sponsored_video(self, client, app):
        """Test creating a sponsored video."""
        response = client.post('/videos/new', data={
            'title': 'Sponsored Video',
            'video_type': 'review',
            'sponsored': 'yes',
            'sponsor_amount': '500.00',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            video = Video.query.filter_by(title='Sponsored Video').first()
            assert video.sponsored is True
            assert video.sponsor_amount == 500.00

    def test_create_video_with_company(self, client, app):
        """Test creating a video linked to a company."""
        with app.app_context():
            company = Company(name='Pulsar')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = client.post('/videos/new', data={
            'title': 'Company Review',
            'video_type': 'review',
            'company_id': company_id,
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            video = Video.query.filter_by(title='Company Review').first()
            assert video.company.name == 'Pulsar'

    def test_create_video_with_products(self, client, app):
        """Test creating a video with linked products."""
        with app.app_context():
            product = Inventory(product_name='Test Mouse')
            db.session.add(product)
            db.session.commit()
            product_id = product.id

        response = client.post('/videos/new', data={
            'title': 'Product Review',
            'video_type': 'review',
            'product_ids': [str(product_id)],
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            video = Video.query.filter_by(title='Product Review').first()
            assert len(video.products) == 1
            assert video.products[0].product_name == 'Test Mouse'

    def test_edit_video(self, client, app):
        """Test editing a video."""
        with app.app_context():
            video = Video(title='Old Title', video_type='review')
            db.session.add(video)
            db.session.commit()
            video_id = video.id

        response = client.post(f'/videos/{video_id}/edit', data={
            'title': 'New Title',
            'video_type': 'comparison',
            'views': '5000',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            video = Video.query.get(video_id)
            assert video.title == 'New Title'
            assert video.video_type == 'comparison'
            assert video.views == 5000

    def test_delete_video(self, client, app):
        """Test deleting a video."""
        with app.app_context():
            video = Video(title='To Delete')
            db.session.add(video)
            db.session.commit()
            video_id = video.id

        response = client.post(f'/videos/{video_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            video = Video.query.get(video_id)
            assert video is None

    def test_filter_videos_by_type(self, client, app):
        """Test filtering videos by type."""
        with app.app_context():
            db.session.add(Video(title='Review Video', video_type='review'))
            db.session.add(Video(title='Guide Video', video_type='guide'))
            db.session.commit()

        response = client.get('/videos/?type=review')
        assert response.status_code == 200
        assert b'Review Video' in response.data

    def test_filter_videos_by_sponsored(self, client, app):
        """Test filtering videos by sponsored status."""
        with app.app_context():
            db.session.add(Video(title='Sponsored', sponsored=True))
            db.session.add(Video(title='Not Sponsored', sponsored=False))
            db.session.commit()

        response = client.get('/videos/?sponsored=yes')
        assert response.status_code == 200
        assert b'Sponsored' in response.data

    def test_search_videos(self, client, app):
        """Test searching videos by title."""
        with app.app_context():
            db.session.add(Video(title='Pulsar X2 Review'))
            db.session.add(Video(title='Logitech GPX Review'))
            db.session.commit()

        response = client.get('/videos/?search=Pulsar')
        assert response.status_code == 200
        assert b'Pulsar X2' in response.data


class TestPodcastRoutes:
    """Tests for podcast episode routes."""

    def test_list_episodes_empty(self, client):
        """Test episode list with no data."""
        response = client.get('/podcast/')
        assert response.status_code == 200

    def test_create_episode(self, client, app):
        """Test creating a new podcast episode."""
        response = client.post('/podcast/new', data={
            'episode_number': '42',
            'title': 'Best Mice of 2025',
            'youtube_url': 'https://youtube.com/watch?v=podcast1',
            'topics': 'mice, reviews, tier lists',
            'publish_date': '2025-01-10',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            episode = PodcastEpisode.query.filter_by(title='Best Mice of 2025').first()
            assert episode is not None
            assert episode.episode_number == 42
            assert 'tier lists' in episode.topics

    def test_create_sponsored_episode(self, client, app):
        """Test creating a sponsored episode."""
        response = client.post('/podcast/new', data={
            'title': 'Sponsored Episode',
            'sponsored': 'yes',
            'sponsor_name': 'Pulsar',
            'sponsor_amount': '200.00',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            episode = PodcastEpisode.query.filter_by(title='Sponsored Episode').first()
            assert episode.sponsored is True
            assert episode.sponsor_name == 'Pulsar'
            assert episode.sponsor_amount == 200.00

    def test_create_episode_with_guests(self, client, app):
        """Test creating an episode with guests."""
        with app.app_context():
            guest = Contact(name='ManPhalanges', role='reviewer')
            db.session.add(guest)
            db.session.commit()
            guest_id = guest.id

        response = client.post('/podcast/new', data={
            'title': 'Guest Episode',
            'guest_ids': [str(guest_id)],
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            episode = PodcastEpisode.query.filter_by(title='Guest Episode').first()
            assert len(episode.guests) == 1
            assert episode.guests[0].name == 'ManPhalanges'

    def test_edit_episode(self, client, app):
        """Test editing an episode."""
        with app.app_context():
            episode = PodcastEpisode(title='Old Title', episode_number=1)
            db.session.add(episode)
            db.session.commit()
            episode_id = episode.id

        response = client.post(f'/podcast/{episode_id}/edit', data={
            'title': 'New Title',
            'episode_number': '5',
            'topics': 'Updated topics',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            episode = PodcastEpisode.query.get(episode_id)
            assert episode.title == 'New Title'
            assert episode.episode_number == 5
            assert episode.topics == 'Updated topics'

    def test_delete_episode(self, client, app):
        """Test deleting an episode."""
        with app.app_context():
            episode = PodcastEpisode(title='To Delete')
            db.session.add(episode)
            db.session.commit()
            episode_id = episode.id

        response = client.post(f'/podcast/{episode_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            episode = PodcastEpisode.query.get(episode_id)
            assert episode is None

    def test_filter_episodes_by_sponsored(self, client, app):
        """Test filtering episodes by sponsored status."""
        with app.app_context():
            db.session.add(PodcastEpisode(title='Sponsored Ep', sponsored=True))
            db.session.add(PodcastEpisode(title='Free Ep', sponsored=False))
            db.session.commit()

        response = client.get('/podcast/?sponsored=yes')
        assert response.status_code == 200
        assert b'Sponsored Ep' in response.data

    def test_search_episodes(self, client, app):
        """Test searching episodes by title."""
        with app.app_context():
            db.session.add(PodcastEpisode(title='MouseCast Episode 42'))
            db.session.add(PodcastEpisode(title='Different Episode'))
            db.session.commit()

        response = client.get('/podcast/?search=MouseCast')
        assert response.status_code == 200
        assert b'MouseCast' in response.data

    def test_auto_increment_episode_number(self, client, app):
        """Test that new episode form suggests next episode number."""
        with app.app_context():
            db.session.add(PodcastEpisode(title='Episode 10', episode_number=10))
            db.session.commit()

        response = client.get('/podcast/new')
        assert response.status_code == 200
        assert b'value="11"' in response.data


class TestAffiliateRoutes:
    """Tests for affiliate revenue routes."""

    def test_list_revenue_empty(self, client):
        """Test revenue list with no data."""
        response = client.get('/affiliates/')
        assert response.status_code == 200

    def test_create_revenue_entry(self, client, app):
        """Test creating a new revenue entry."""
        with app.app_context():
            company = Company(name='Pulsar', affiliate_status='yes')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

        response = client.post('/affiliates/new', data={
            'company_id': company_id,
            'year': '2025',
            'month': '1',
            'revenue': '150.00',
            'sales_count': '12',
            'notes': 'Good month',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            entry = AffiliateRevenue.query.filter_by(company_id=company_id).first()
            assert entry is not None
            assert entry.revenue == 150.00
            assert entry.sales_count == 12
            assert entry.notes == 'Good month'

    def test_duplicate_revenue_entry_fails(self, client, app):
        """Test that duplicate company/month entries are rejected."""
        with app.app_context():
            company = Company(name='Pulsar', affiliate_status='yes')
            db.session.add(company)
            db.session.commit()
            company_id = company.id

            # Create existing entry
            entry = AffiliateRevenue(company_id=company_id, year=2025, month=1, revenue=100)
            db.session.add(entry)
            db.session.commit()

        response = client.post('/affiliates/new', data={
            'company_id': company_id,
            'year': '2025',
            'month': '1',
            'revenue': '200.00',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'already exists' in response.data

    def test_edit_revenue_entry(self, client, app):
        """Test editing a revenue entry."""
        with app.app_context():
            company = Company(name='Pulsar', affiliate_status='yes')
            db.session.add(company)
            db.session.commit()

            entry = AffiliateRevenue(company_id=company.id, year=2025, month=1, revenue=100)
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

        response = client.post(f'/affiliates/{entry_id}/edit', data={
            'revenue': '250.00',
            'sales_count': '20',
            'notes': 'Updated notes',
        }, follow_redirects=True)

        assert response.status_code == 200

        with app.app_context():
            entry = AffiliateRevenue.query.get(entry_id)
            assert entry.revenue == 250.00
            assert entry.sales_count == 20
            assert entry.notes == 'Updated notes'

    def test_delete_revenue_entry(self, client, app):
        """Test deleting a revenue entry."""
        with app.app_context():
            company = Company(name='Pulsar', affiliate_status='yes')
            db.session.add(company)
            db.session.commit()

            entry = AffiliateRevenue(company_id=company.id, year=2025, month=1, revenue=100)
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

        response = client.post(f'/affiliates/{entry_id}/delete', follow_redirects=True)
        assert response.status_code == 200

        with app.app_context():
            entry = AffiliateRevenue.query.get(entry_id)
            assert entry is None

    def test_filter_revenue_by_year(self, client, app):
        """Test filtering revenue by year."""
        with app.app_context():
            company = Company(name='Pulsar', affiliate_status='yes')
            db.session.add(company)
            db.session.commit()

            db.session.add(AffiliateRevenue(company_id=company.id, year=2024, month=12, revenue=100))
            db.session.add(AffiliateRevenue(company_id=company.id, year=2025, month=1, revenue=200))
            db.session.commit()

        response = client.get('/affiliates/?year=2025')
        assert response.status_code == 200

    def test_filter_revenue_by_company(self, client, app):
        """Test filtering revenue by company."""
        with app.app_context():
            company1 = Company(name='Pulsar', affiliate_status='yes')
            company2 = Company(name='Lethal Gaming', affiliate_status='yes')
            db.session.add_all([company1, company2])
            db.session.commit()

            db.session.add(AffiliateRevenue(company_id=company1.id, year=2025, month=1, revenue=100))
            db.session.add(AffiliateRevenue(company_id=company2.id, year=2025, month=1, revenue=50))
            db.session.commit()
            company1_id = company1.id

        response = client.get(f'/affiliates/?company_id={company1_id}')
        assert response.status_code == 200

    def test_revenue_stats_calculation(self, client, app):
        """Test that revenue stats are calculated correctly."""
        with app.app_context():
            company = Company(name='Pulsar', affiliate_status='yes')
            db.session.add(company)
            db.session.commit()

            db.session.add(AffiliateRevenue(company_id=company.id, year=2025, month=1, revenue=100))
            db.session.add(AffiliateRevenue(company_id=company.id, year=2025, month=2, revenue=150))
            db.session.commit()

        response = client.get('/affiliates/')
        assert response.status_code == 200
        # Total should be $250.00
        assert b'250.00' in response.data
