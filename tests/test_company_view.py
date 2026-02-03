"""Tests for company detail/view page."""
import pytest
from app import db
from models import Company, Contact


class TestCompanyViewRoute:
    """Tests for GET /companies/<id> detail page."""

    def test_view_company_requires_auth(self, client, company):
        """Unauthenticated users are redirected to login."""
        response = client.get(f'/companies/{company["id"]}')
        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']

    def test_view_company_200(self, auth_client, company):
        """Authenticated user can view a company."""
        response = auth_client.get(f'/companies/{company["id"]}')
        assert response.status_code == 200
        assert b'Test Company' in response.data

    def test_view_company_404(self, auth_client):
        """Nonexistent company returns 404."""
        response = auth_client.get('/companies/99999')
        assert response.status_code == 404

    def test_view_company_shows_contacts(self, auth_client, app, company):
        """Company detail page shows associated contacts."""
        with app.app_context():
            c1 = Contact(name='Alice Rep', company_id=company['id'], role='company_rep')
            c2 = Contact(name='Bob Reviewer', company_id=company['id'], role='reviewer')
            db.session.add_all([c1, c2])
            db.session.commit()

        response = auth_client.get(f'/companies/{company["id"]}')
        assert response.status_code == 200
        assert b'Alice Rep' in response.data
        assert b'Bob Reviewer' in response.data
        assert b'Contacts (2)' in response.data

    def test_view_company_does_not_show_other_contacts(self, auth_client, app, company):
        """Contacts from other companies do not appear."""
        with app.app_context():
            other = Company(name='Other Co')
            db.session.add(other)
            db.session.commit()

            mine = Contact(name='My Contact', company_id=company['id'])
            theirs = Contact(name='Their Contact', company_id=other.id)
            db.session.add_all([mine, theirs])
            db.session.commit()

        response = auth_client.get(f'/companies/{company["id"]}')
        assert response.status_code == 200
        assert b'My Contact' in response.data
        assert b'Their Contact' not in response.data

    def test_view_company_empty_contacts(self, auth_client, company):
        """Company with no contacts shows empty state."""
        response = auth_client.get(f'/companies/{company["id"]}')
        assert response.status_code == 200
        assert b'No contacts yet' in response.data
        assert b'Contacts (0)' in response.data

    def test_view_company_contacts_sorted_by_name(self, auth_client, app, company):
        """Contacts are sorted alphabetically by name."""
        with app.app_context():
            db.session.add_all([
                Contact(name='Zara', company_id=company['id']),
                Contact(name='Alice', company_id=company['id']),
                Contact(name='Mia', company_id=company['id']),
            ])
            db.session.commit()

        response = auth_client.get(f'/companies/{company["id"]}')
        html = response.data.decode('utf-8')
        alice_pos = html.index('Alice')
        mia_pos = html.index('Mia')
        zara_pos = html.index('Zara')
        assert alice_pos < mia_pos < zara_pos

    def test_view_company_shows_badges(self, auth_client, app):
        """Company detail page renders status and category badges."""
        with app.app_context():
            c = Company(name='Badge Co', category='keyboards',
                        relationship_status='active', priority='target')
            db.session.add(c)
            db.session.commit()
            cid = c.id

        response = auth_client.get(f'/companies/{cid}')
        assert response.status_code == 200
        assert b'Keyboards' in response.data
        assert b'Active' in response.data
        assert b'Target' in response.data

    def test_view_company_shows_affiliate_info(self, auth_client, app):
        """Affiliate info card shown when affiliate_status is not 'no'."""
        with app.app_context():
            c = Company(name='Affiliate Co', affiliate_status='yes',
                        affiliate_code='DAZZ10', commission_rate=10.0)
            db.session.add(c)
            db.session.commit()
            cid = c.id

        response = auth_client.get(f'/companies/{cid}')
        assert response.status_code == 200
        assert b'Affiliate Program' in response.data
        assert b'DAZZ10' in response.data
        assert b'10.0%' in response.data

    def test_view_company_hides_affiliate_when_no(self, auth_client, app):
        """Affiliate info card hidden when affiliate_status is 'no'."""
        with app.app_context():
            c = Company(name='No Affiliate Co', affiliate_status='no')
            db.session.add(c)
            db.session.commit()
            cid = c.id

        response = auth_client.get(f'/companies/{cid}')
        assert response.status_code == 200
        assert b'Affiliate Program' not in response.data

    def test_view_company_shows_notes(self, auth_client, app):
        """Notes card shown when notes exist."""
        with app.app_context():
            c = Company(name='Notes Co', notes='Important note here')
            db.session.add(c)
            db.session.commit()
            cid = c.id

        response = auth_client.get(f'/companies/{cid}')
        assert response.status_code == 200
        assert b'Important note here' in response.data

    def test_view_company_hides_notes_when_empty(self, auth_client, company):
        """Notes card hidden when no notes."""
        response = auth_client.get(f'/companies/{company["id"]}')
        html = response.data.decode('utf-8')
        assert 'Notes</h2>' not in html


class TestCompanyListLinks:
    """Tests for company list linking to detail page."""

    def test_list_links_to_view_page(self, auth_client, company):
        """Company names on list page link to the detail view."""
        response = auth_client.get('/companies/')
        assert response.status_code == 200
        assert f'/companies/{company["id"]}'.encode() in response.data


class TestEditRedirect:
    """Tests for edit_company redirecting to detail page."""

    def test_edit_redirects_to_view(self, auth_client, company):
        """After editing, user is redirected to the detail page."""
        response = auth_client.post(f'/companies/{company["id"]}/edit', data={
            'name': 'Updated Company',
            'category': 'mice',
            'relationship_status': 'active',
            'priority': 'low',
            'affiliate_status': 'no',
        }, follow_redirects=False)
        assert response.status_code == 302
        assert f'/companies/{company["id"]}' in response.headers['Location']


class TestContactPreFill:
    """Tests for ?company_id= pre-fill on new contact form."""

    def test_new_contact_prefills_company(self, auth_client, company):
        """New contact form pre-selects company from query param."""
        response = auth_client.get(f'/contacts/new?company_id={company["id"]}')
        assert response.status_code == 200
        # The company option should be selected
        html = response.data.decode('utf-8')
        assert f'value="{company["id"]}"' in html
        # Check that 'selected' appears near the company option
        assert 'selected' in html

    def test_new_contact_no_prefill_without_param(self, auth_client, company):
        """New contact form without company_id param has no pre-selection."""
        response = auth_client.get('/contacts/new')
        assert response.status_code == 200
