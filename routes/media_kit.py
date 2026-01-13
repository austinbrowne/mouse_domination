"""Media Kit routes for creator profile and sponsorship pitch generation."""
import os
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, Response
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename
from markupsafe import escape
from models import CreatorProfile, RateCard, Testimonial, Company
from extensions import db
from utils.validation import ValidationError
from utils.routes import FormData
from utils.logging import log_exception
from utils.queries import get_companies_for_dropdown
from decimal import Decimal, InvalidOperation

media_kit_bp = Blueprint('media_kit', __name__)

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_profile_photo(file):
    """Save uploaded profile photo and return the URL path.

    Returns:
        str: URL path to the saved file, or None if save failed.
    """
    if not file or not file.filename:
        return None

    if not allowed_file(file.filename):
        raise ValidationError('photo', 'Invalid file type. Allowed: PNG, JPG, GIF, WEBP')

    # Check file size by reading content
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset to beginning

    if size > MAX_FILE_SIZE:
        raise ValidationError('photo', 'File too large. Maximum size is 2MB')

    # Generate secure filename with random prefix
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{secrets.token_hex(16)}.{ext}"

    # Ensure upload directory exists
    upload_dir = os.path.join(current_app.static_folder, 'uploads', 'profiles')
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    # Return URL path (relative to static)
    return f"/static/uploads/profiles/{filename}"


def delete_old_photo(photo_url):
    """Delete old profile photo file if it's a local upload."""
    if not photo_url or not photo_url.startswith('/static/uploads/profiles/'):
        return

    try:
        filepath = os.path.join(current_app.root_path, photo_url.lstrip('/'))
        if os.path.exists(filepath):
            os.remove(filepath)
    except OSError:
        pass  # Ignore deletion errors


def get_or_create_profile():
    """Get current user's profile or return None if doesn't exist."""
    return CreatorProfile.query.filter_by(user_id=current_user.id).first()


def require_profile(f):
    """Decorator to ensure profile exists before accessing route."""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        profile = get_or_create_profile()
        if not profile:
            flash('Please create your profile first.', 'info')
            return redirect(url_for('media_kit.edit_profile'))
        return f(profile, *args, **kwargs)
    return decorated_function


@media_kit_bp.route('/')
@login_required
def edit_profile():
    """View/edit creator profile."""
    profile = get_or_create_profile()
    return render_template('media_kit/profile_form.html', profile=profile)


@media_kit_bp.route('/', methods=['POST'])
@login_required
def save_profile():
    """Save creator profile."""
    try:
        form = FormData(request.form)
        profile = get_or_create_profile()

        # Parse JSON fields from form
        social_links = {}
        platform_stats = {}
        audience_demographics = {'age': {}, 'gender': {}, 'top_locations': []}

        # Social links - parse from individual form fields
        for platform in ['youtube', 'twitter', 'instagram', 'tiktok', 'twitch', 'discord', 'linkedin']:
            handle = form.optional(f'social_{platform}')
            if handle:
                social_links[platform] = handle

        # Platform stats - parse from individual form fields
        for platform in ['youtube', 'twitter', 'instagram', 'tiktok', 'twitch']:
            subscribers = form.integer(f'stats_{platform}_subscribers')
            avg_views = form.integer(f'stats_{platform}_avg_views')
            engagement = form.optional(f'stats_{platform}_engagement')
            if subscribers or avg_views or engagement:
                platform_stats[platform] = {}
                if subscribers:
                    platform_stats[platform]['subscribers'] = subscribers
                if avg_views:
                    platform_stats[platform]['avg_views'] = avg_views
                if engagement:
                    try:
                        platform_stats[platform]['engagement_rate'] = float(engagement)
                    except ValueError:
                        pass

        # Audience demographics - parse from form fields
        for age_range in ['13-17', '18-24', '25-34', '35-44', '45-54', '55+']:
            pct = form.optional(f'age_{age_range.replace("-", "_").replace("+", "plus")}')
            if pct:
                try:
                    audience_demographics['age'][age_range] = int(pct)
                except ValueError:
                    pass

        gender_male = form.optional('gender_male')
        gender_female = form.optional('gender_female')
        gender_other = form.optional('gender_other')
        if gender_male:
            audience_demographics['gender']['male'] = int(gender_male)
        if gender_female:
            audience_demographics['gender']['female'] = int(gender_female)
        if gender_other:
            audience_demographics['gender']['other'] = int(gender_other)

        # Top locations
        locations = form.optional('top_locations')
        if locations:
            audience_demographics['top_locations'] = [loc.strip() for loc in locations.split(',') if loc.strip()]

        # Content niches
        niches_str = form.optional('content_niches')
        content_niches = [n.strip() for n in niches_str.split(',') if n.strip()] if niches_str else []

        # Handle photo upload
        photo_url = form.optional('photo_url')  # External URL fallback
        uploaded_file = request.files.get('photo_file')

        if uploaded_file and uploaded_file.filename:
            # New file uploaded - save it
            new_photo_url = save_profile_photo(uploaded_file)
            if new_photo_url:
                # Delete old photo if it was a local upload
                if profile and profile.photo_url:
                    delete_old_photo(profile.photo_url)
                photo_url = new_photo_url
        elif form.optional('clear_photo') == 'yes':
            # User wants to clear the photo
            if profile and profile.photo_url:
                delete_old_photo(profile.photo_url)
            photo_url = None

        if profile:
            # Update existing profile
            profile.display_name = form.required('display_name')
            profile.tagline = form.optional('tagline')
            profile.bio = form.optional('bio')
            profile.photo_url = photo_url
            profile.location = form.optional('location')
            profile.contact_email = form.optional('contact_email')
            profile.website_url = form.optional('website_url')
            profile.social_links = social_links if social_links else None
            profile.platform_stats = platform_stats if platform_stats else None
            profile.audience_demographics = audience_demographics if any(audience_demographics.values()) else None
            profile.content_niches = content_niches if content_niches else None
        else:
            # Create new profile
            profile = CreatorProfile(
                user_id=current_user.id,
                display_name=form.required('display_name'),
                tagline=form.optional('tagline'),
                bio=form.optional('bio'),
                photo_url=photo_url,
                location=form.optional('location'),
                contact_email=form.optional('contact_email'),
                website_url=form.optional('website_url'),
                social_links=social_links if social_links else None,
                platform_stats=platform_stats if platform_stats else None,
                audience_demographics=audience_demographics if any(audience_demographics.values()) else None,
                content_niches=content_niches if content_niches else None,
            )
            db.session.add(profile)

        db.session.commit()
        flash('Profile saved successfully.', 'success')
        return redirect(url_for('media_kit.edit_profile'))

    except ValidationError as e:
        flash(f'{e.field}: {e.message}', 'error')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Save profile', e)
        flash('Database error occurred. Please try again.', 'error')

    return render_template('media_kit/profile_form.html', profile=get_or_create_profile())


# --- Rate Card Routes ---

@media_kit_bp.route('/rates')
@login_required
@require_profile
def list_rates(profile):
    """List rate cards."""
    return render_template('media_kit/rates.html', profile=profile, rates=profile.rate_cards)


@media_kit_bp.route('/rates', methods=['POST'])
@login_required
@require_profile
def add_rate(profile):
    """Add a new rate card entry."""
    try:
        form = FormData(request.form)

        # Get max display order
        max_order = db.session.query(db.func.max(RateCard.display_order)).filter_by(profile_id=profile.id).scalar() or 0

        # Parse price values
        price_min = None
        price_max = None
        price_min_str = form.optional('price_min')
        price_max_str = form.optional('price_max')

        if price_min_str:
            try:
                price_min = Decimal(price_min_str.replace(',', '').replace('$', ''))
            except InvalidOperation:
                raise ValidationError('price_min', 'Invalid price format')

        if price_max_str:
            try:
                price_max = Decimal(price_max_str.replace(',', '').replace('$', ''))
            except InvalidOperation:
                raise ValidationError('price_max', 'Invalid price format')

        rate = RateCard(
            profile_id=profile.id,
            service_name=form.required('service_name'),
            description=form.optional('description'),
            price_min=price_min,
            price_max=price_max,
            price_note=form.optional('price_note'),
            is_negotiable=form.boolean('is_negotiable'),
            display_order=max_order + 1,
        )

        db.session.add(rate)
        db.session.commit()
        flash('Rate added successfully.', 'success')

    except ValidationError as e:
        flash(f'{e.field}: {e.message}', 'error')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Add rate', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('media_kit.list_rates'))


@media_kit_bp.route('/rates/<int:id>/delete', methods=['POST'])
@login_required
@require_profile
def delete_rate(profile, id):
    """Delete a rate card entry."""
    try:
        rate = RateCard.query.filter_by(id=id, profile_id=profile.id).first_or_404()
        db.session.delete(rate)
        db.session.commit()
        flash('Rate deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Delete rate', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('media_kit.list_rates'))


@media_kit_bp.route('/rates/reorder', methods=['POST'])
@login_required
@require_profile
def reorder_rates(profile):
    """Reorder rate cards via AJAX."""
    try:
        order = request.json.get('order', [])
        for idx, rate_id in enumerate(order):
            rate = RateCard.query.filter_by(id=rate_id, profile_id=profile.id).first()
            if rate:
                rate.display_order = idx
        db.session.commit()
        return jsonify({'success': True})
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Reorder rates', e)
        return jsonify({'success': False, 'error': 'Database error'}), 500


# --- Testimonial Routes ---

@media_kit_bp.route('/testimonials')
@login_required
@require_profile
def list_testimonials(profile):
    """List testimonials."""
    companies = get_companies_for_dropdown()
    return render_template('media_kit/testimonials.html', profile=profile,
                          testimonials=profile.testimonials, companies=companies)


@media_kit_bp.route('/testimonials', methods=['POST'])
@login_required
@require_profile
def add_testimonial(profile):
    """Add a new testimonial."""
    try:
        form = FormData(request.form)

        company_id = form.foreign_key('company_id', Company)

        testimonial = Testimonial(
            profile_id=profile.id,
            company_id=company_id,
            company_name=form.optional('company_name') if not company_id else None,
            contact_name=form.optional('contact_name'),
            contact_title=form.optional('contact_title'),
            quote=form.required('quote'),
        )

        db.session.add(testimonial)
        db.session.commit()
        flash('Testimonial added successfully.', 'success')

    except ValidationError as e:
        flash(f'{e.field}: {e.message}', 'error')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Add testimonial', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('media_kit.list_testimonials'))


@media_kit_bp.route('/testimonials/<int:id>/delete', methods=['POST'])
@login_required
@require_profile
def delete_testimonial(profile, id):
    """Delete a testimonial."""
    try:
        testimonial = Testimonial.query.filter_by(id=id, profile_id=profile.id).first_or_404()
        db.session.delete(testimonial)
        db.session.commit()
        flash('Testimonial deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Delete testimonial', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('media_kit.list_testimonials'))


# --- Preview & Export Routes ---

@media_kit_bp.route('/preview')
@login_required
@require_profile
def preview(profile):
    """Preview the media kit."""
    # Get past collaborations from companies that have had deals
    past_sponsors = Company.query.join(Company.deals).filter(
        Company.deals.any()
    ).distinct().limit(12).all()

    return render_template('media_kit/preview.html',
                          profile=profile,
                          rates=profile.rate_cards,
                          testimonials=profile.testimonials,
                          past_sponsors=past_sponsors)


@media_kit_bp.route('/export/html')
@login_required
@require_profile
def export_html(profile):
    """Export media kit as standalone HTML file."""
    past_sponsors = Company.query.join(Company.deals).filter(
        Company.deals.any()
    ).distinct().limit(12).all()

    html_content = render_template('media_kit/export_html.html',
                                   profile=profile,
                                   rates=profile.rate_cards,
                                   testimonials=profile.testimonials,
                                   past_sponsors=past_sponsors)

    return Response(
        html_content,
        mimetype='text/html',
        headers={'Content-Disposition': f'attachment; filename=media-kit-{profile.display_name.lower().replace(" ", "-")}.html'}
    )


@media_kit_bp.route('/export/pdf')
@login_required
@require_profile
def export_pdf(profile):
    """Export media kit as PDF."""
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        flash('PDF export requires weasyprint. Please install it or use HTML export.', 'error')
        return redirect(url_for('media_kit.preview'))

    past_sponsors = Company.query.join(Company.deals).filter(
        Company.deals.any()
    ).distinct().limit(12).all()

    html_content = render_template('media_kit/pdf_template.html',
                                   profile=profile,
                                   rates=profile.rate_cards,
                                   testimonials=profile.testimonials,
                                   past_sponsors=past_sponsors)

    try:
        pdf_bytes = HTML(string=html_content, base_url=request.host_url).write_pdf()

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=media-kit-{profile.display_name.lower().replace(" ", "-")}.pdf'}
        )
    except Exception as e:
        log_exception(current_app.logger, 'PDF generation', e)
        flash('Error generating PDF. Please try HTML export instead.', 'error')
        return redirect(url_for('media_kit.preview'))


# --- Public Sharing Routes ---

@media_kit_bp.route('/share', methods=['POST'])
@login_required
@require_profile
def generate_share_link(profile):
    """Generate or regenerate public share link."""
    try:
        profile.generate_public_token()
        profile.is_public = True
        db.session.commit()

        share_url = url_for('media_kit.public_view', token=profile.public_token, _external=True)
        flash(f'Share link generated: {share_url}', 'success')

    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Generate share link', e)
        flash('Error generating share link.', 'error')

    return redirect(url_for('media_kit.preview'))


@media_kit_bp.route('/share/disable', methods=['POST'])
@login_required
@require_profile
def disable_sharing(profile):
    """Disable public sharing."""
    try:
        profile.is_public = False
        db.session.commit()
        flash('Public sharing disabled.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Disable sharing', e)
        flash('Error disabling sharing.', 'error')

    return redirect(url_for('media_kit.preview'))


# Public route - no login required
@media_kit_bp.route('/public/<token>')
def public_view(token):
    """Public view of media kit (no auth required)."""
    profile = CreatorProfile.query.filter_by(public_token=token, is_public=True).first_or_404()

    past_sponsors = Company.query.join(Company.deals).filter(
        Company.deals.any()
    ).distinct().limit(12).all()

    return render_template('media_kit/public.html',
                          profile=profile,
                          rates=profile.rate_cards,
                          testimonials=profile.testimonials,
                          past_sponsors=past_sponsors)
