from datetime import date
from flask import Blueprint, render_template, request, jsonify, url_for
from flask_login import login_required
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from models import EpisodeGuide, Inventory, SalesPipeline, Collaboration
from extensions import db

calendar_bp = Blueprint('calendar', __name__)

# Event type colors (matching plan)
EVENT_COLORS = {
    'inventory_deadline': '#ef4444',     # Red
    'inventory_return': '#f97316',       # Orange
    'episode': '#3b82f6',                # Blue
    'pipeline_deadline': '#22c55e',      # Green
    'pipeline_deliverable': '#14b8a6',   # Teal
    'pipeline_payment': '#8b5cf6',       # Purple
    'collab': '#ec4899',                 # Pink
    'follow_up': '#6b7280',              # Gray
}


@calendar_bp.route('/')
@login_required
def view():
    """Main calendar view with month/week toggle."""
    return render_template('calendar/view.html')


@calendar_bp.route('/api/events')
@login_required
def get_events():
    """API endpoint to get calendar events within a date range."""
    # Parse date range from query params
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    event_types = request.args.get('types', '').split(',') if request.args.get('types') else None

    try:
        start_date = date.fromisoformat(start_str) if start_str else None
        end_date = date.fromisoformat(end_str) if end_str else None
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    events = []

    # Episode Guide events (scheduled_date)
    if not event_types or 'episode' in event_types:
        episode_query = EpisodeGuide.query.filter(EpisodeGuide.scheduled_date.isnot(None))
        if start_date:
            episode_query = episode_query.filter(EpisodeGuide.scheduled_date >= start_date)
        if end_date:
            episode_query = episode_query.filter(EpisodeGuide.scheduled_date <= end_date)

        for episode in episode_query.all():
            events.append({
                'id': f'episode-{episode.id}',
                'title': f'Episode: {episode.title}',
                'date': episode.scheduled_date.isoformat(),
                'type': 'episode',
                'color': EVENT_COLORS['episode'],
                'url': url_for('episode_guide.view_guide', id=episode.id),
            })

    # Inventory events (deadline, return_by_date)
    if not event_types or 'inventory_deadline' in event_types:
        inv_deadline_query = Inventory.query.filter(
            Inventory.deadline.isnot(None),
            Inventory.status != 'reviewed'  # Hide deadline for reviewed items
        )
        if start_date:
            inv_deadline_query = inv_deadline_query.filter(Inventory.deadline >= start_date)
        if end_date:
            inv_deadline_query = inv_deadline_query.filter(Inventory.deadline <= end_date)

        for item in inv_deadline_query.all():
            events.append({
                'id': f'inventory-deadline-{item.id}',
                'title': f'Deadline: {item.product_name}',
                'date': item.deadline.isoformat(),
                'type': 'inventory_deadline',
                'color': EVENT_COLORS['inventory_deadline'],
                'url': url_for('inventory.edit_item', id=item.id),
            })

    if not event_types or 'inventory_return' in event_types:
        inv_return_query = Inventory.query.filter(Inventory.return_by_date.isnot(None))
        if start_date:
            inv_return_query = inv_return_query.filter(Inventory.return_by_date >= start_date)
        if end_date:
            inv_return_query = inv_return_query.filter(Inventory.return_by_date <= end_date)

        for item in inv_return_query.all():
            events.append({
                'id': f'inventory-return-{item.id}',
                'title': f'Return: {item.product_name}',
                'date': item.return_by_date.isoformat(),
                'type': 'inventory_return',
                'color': EVENT_COLORS['inventory_return'],
                'url': url_for('inventory.edit_item', id=item.id),
            })

    # Pipeline events (deadline, deliverable_date, payment_date)
    if not event_types or 'pipeline_deadline' in event_types:
        pipeline_deadline_query = SalesPipeline.query.options(
            joinedload(SalesPipeline.company)
        ).filter(SalesPipeline.deadline.isnot(None))
        if start_date:
            pipeline_deadline_query = pipeline_deadline_query.filter(SalesPipeline.deadline >= start_date)
        if end_date:
            pipeline_deadline_query = pipeline_deadline_query.filter(SalesPipeline.deadline <= end_date)

        for deal in pipeline_deadline_query.all():
            company_name = deal.company.name if deal.company else 'Unknown'
            events.append({
                'id': f'pipeline-deadline-{deal.id}',
                'title': f'Pipeline: {company_name}',
                'date': deal.deadline.isoformat(),
                'type': 'pipeline_deadline',
                'color': EVENT_COLORS['pipeline_deadline'],
                'url': url_for('pipeline.edit_deal', id=deal.id),
            })

    if not event_types or 'pipeline_deliverable' in event_types:
        pipeline_deliverable_query = SalesPipeline.query.options(
            joinedload(SalesPipeline.company)
        ).filter(SalesPipeline.deliverable_date.isnot(None))
        if start_date:
            pipeline_deliverable_query = pipeline_deliverable_query.filter(SalesPipeline.deliverable_date >= start_date)
        if end_date:
            pipeline_deliverable_query = pipeline_deliverable_query.filter(SalesPipeline.deliverable_date <= end_date)

        for deal in pipeline_deliverable_query.all():
            company_name = deal.company.name if deal.company else 'Unknown'
            events.append({
                'id': f'pipeline-deliverable-{deal.id}',
                'title': f'Deliverable: {company_name}',
                'date': deal.deliverable_date.isoformat(),
                'type': 'pipeline_deliverable',
                'color': EVENT_COLORS['pipeline_deliverable'],
                'url': url_for('pipeline.edit_deal', id=deal.id),
            })

    if not event_types or 'pipeline_payment' in event_types:
        pipeline_payment_query = SalesPipeline.query.options(
            joinedload(SalesPipeline.company)
        ).filter(SalesPipeline.payment_date.isnot(None))
        if start_date:
            pipeline_payment_query = pipeline_payment_query.filter(SalesPipeline.payment_date >= start_date)
        if end_date:
            pipeline_payment_query = pipeline_payment_query.filter(SalesPipeline.payment_date <= end_date)

        for deal in pipeline_payment_query.all():
            company_name = deal.company.name if deal.company else 'Unknown'
            events.append({
                'id': f'pipeline-payment-{deal.id}',
                'title': f'Payment: {company_name}',
                'date': deal.payment_date.isoformat(),
                'type': 'pipeline_payment',
                'color': EVENT_COLORS['pipeline_payment'],
                'url': url_for('pipeline.edit_deal', id=deal.id),
            })

    # Collaboration events (scheduled_date, follow_up_date)
    if not event_types or 'collab' in event_types:
        collab_query = Collaboration.query.options(
            joinedload(Collaboration.contact)
        ).filter(Collaboration.scheduled_date.isnot(None))
        if start_date:
            collab_query = collab_query.filter(Collaboration.scheduled_date >= start_date)
        if end_date:
            collab_query = collab_query.filter(Collaboration.scheduled_date <= end_date)

        for collab in collab_query.all():
            contact_name = collab.contact.name if collab.contact else 'Unknown'
            events.append({
                'id': f'collab-{collab.id}',
                'title': f'Collab: {contact_name}',
                'date': collab.scheduled_date.isoformat(),
                'type': 'collab',
                'color': EVENT_COLORS['collab'],
                'url': url_for('collabs.edit_collab', id=collab.id),
            })

    # Follow-up events from various models
    if not event_types or 'follow_up' in event_types:
        # Collaboration follow-ups
        collab_followup_query = Collaboration.query.options(
            joinedload(Collaboration.contact)
        ).filter(Collaboration.follow_up_date.isnot(None))
        if start_date:
            collab_followup_query = collab_followup_query.filter(Collaboration.follow_up_date >= start_date)
        if end_date:
            collab_followup_query = collab_followup_query.filter(Collaboration.follow_up_date <= end_date)

        for collab in collab_followup_query.all():
            contact_name = collab.contact.name if collab.contact else 'Unknown'
            events.append({
                'id': f'followup-collab-{collab.id}',
                'title': f'Follow-up: {contact_name}',
                'date': collab.follow_up_date.isoformat(),
                'type': 'follow_up',
                'color': EVENT_COLORS['follow_up'],
                'url': url_for('collabs.edit_collab', id=collab.id),
            })

        # Pipeline follow-ups
        pipeline_followup_query = SalesPipeline.query.options(
            joinedload(SalesPipeline.company)
        ).filter(SalesPipeline.follow_up_date.isnot(None))
        if start_date:
            pipeline_followup_query = pipeline_followup_query.filter(SalesPipeline.follow_up_date >= start_date)
        if end_date:
            pipeline_followup_query = pipeline_followup_query.filter(SalesPipeline.follow_up_date <= end_date)

        for deal in pipeline_followup_query.all():
            company_name = deal.company.name if deal.company else 'Unknown'
            events.append({
                'id': f'followup-pipeline-{deal.id}',
                'title': f'Follow-up: {company_name}',
                'date': deal.follow_up_date.isoformat(),
                'type': 'follow_up',
                'color': EVENT_COLORS['follow_up'],
                'url': url_for('pipeline.edit_deal', id=deal.id),
            })

    # Sort events by date
    events.sort(key=lambda e: e['date'])

    return jsonify({'events': events})
