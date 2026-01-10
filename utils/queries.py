"""Query utilities for reducing database duplication."""
from functools import lru_cache
from flask import g
from models import Company, Contact


def get_companies_for_dropdown():
    """Get companies list for dropdown menus.

    Uses Flask's g object to cache within a single request,
    avoiding duplicate queries when rendering forms with errors.
    """
    if not hasattr(g, '_companies_dropdown'):
        g._companies_dropdown = Company.query.order_by(Company.name).all()
    return g._companies_dropdown


def get_contacts_for_dropdown():
    """Get contacts list for dropdown menus.

    Uses Flask's g object to cache within a single request,
    avoiding duplicate queries when rendering forms with errors.
    """
    if not hasattr(g, '_contacts_dropdown'):
        g._contacts_dropdown = Contact.query.order_by(Contact.name).all()
    return g._contacts_dropdown


def get_companies_and_contacts_for_dropdown():
    """Get both companies and contacts for dropdown menus.

    Convenience function for forms that need both.
    Returns tuple: (companies, contacts)
    """
    return get_companies_for_dropdown(), get_contacts_for_dropdown()
