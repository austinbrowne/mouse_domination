"""Episode template routes: list, create, edit, delete."""
from flask import render_template, request, redirect, url_for, flash, g, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import EpisodeGuideTemplate
from constants import INTRO_STATIC_CONTENT, OUTRO_STATIC_CONTENT
from utils.validation import ValidationError
from utils.routes import FormData
from utils.logging import log_exception
from utils.podcast_access import require_podcast_access, require_podcast_admin

from . import podcast_bp


@podcast_bp.route('/<int:podcast_id>/templates/')
@login_required
@require_podcast_access
def list_templates(podcast_id):
    """List all templates for a podcast."""
    podcast = g.podcast

    templates = EpisodeGuideTemplate.query.filter_by(
        podcast_id=podcast_id
    ).order_by(
        EpisodeGuideTemplate.is_default.desc(),
        EpisodeGuideTemplate.name
    ).all()

    return render_template('podcasts/templates/list.html',
        podcast=podcast,
        templates=templates,
        user_role=g.user_podcast_role,
    )


@podcast_bp.route('/<int:podcast_id>/templates/new', methods=['GET', 'POST'])
@login_required
@require_podcast_access
def new_template(podcast_id):
    """Create a new template for a podcast."""
    podcast = g.podcast

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            template = EpisodeGuideTemplate(
                podcast_id=podcast_id,
                name=form.required('name', max_length=100),
                description=form.optional('description'),
                default_poll_1=form.optional('default_poll_1'),
                default_poll_2=form.optional('default_poll_2'),
                created_by=current_user.id,
                is_default=form.boolean('is_default'),
            )

            intro_content = request.form.getlist('intro_static_content[]')
            intro_content = [line.strip() for line in intro_content if line.strip()]
            template.intro_static_content = intro_content if intro_content else None

            outro_content = request.form.getlist('outro_static_content[]')
            outro_content = [line.strip() for line in outro_content if line.strip()]
            template.outro_static_content = outro_content if outro_content else None

            if template.is_default:
                EpisodeGuideTemplate.query.filter(
                    EpisodeGuideTemplate.podcast_id == podcast_id,
                    EpisodeGuideTemplate.is_default == True
                ).update({'is_default': False})

            db.session.add(template)
            db.session.commit()
            flash(f'Template "{template.name}" created.', 'success')
            return redirect(url_for('podcasts.edit_template', podcast_id=podcast_id, template_id=template.id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Create template', e)
            flash('Database error occurred. Please try again.', 'error')

    return render_template('podcasts/templates/form.html',
        podcast=podcast,
        template=None,
        intro_content=INTRO_STATIC_CONTENT,
        outro_content=OUTRO_STATIC_CONTENT,
        user_role=g.user_podcast_role,
    )


@podcast_bp.route('/<int:podcast_id>/templates/<int:template_id>/edit', methods=['GET', 'POST'])
@login_required
@require_podcast_access
def edit_template(podcast_id, template_id):
    """Edit a template."""
    podcast = g.podcast
    template = EpisodeGuideTemplate.query.filter_by(
        id=template_id,
        podcast_id=podcast_id
    ).first_or_404()

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            template.name = form.required('name', max_length=100)
            template.description = form.optional('description')
            template.default_poll_1 = form.optional('default_poll_1')
            template.default_poll_2 = form.optional('default_poll_2')
            template.is_default = form.boolean('is_default')

            intro_content = request.form.getlist('intro_static_content[]')
            intro_content = [line.strip() for line in intro_content if line.strip()]
            template.intro_static_content = intro_content if intro_content else None

            outro_content = request.form.getlist('outro_static_content[]')
            outro_content = [line.strip() for line in outro_content if line.strip()]
            template.outro_static_content = outro_content if outro_content else None

            if template.is_default:
                EpisodeGuideTemplate.query.filter(
                    EpisodeGuideTemplate.podcast_id == podcast_id,
                    EpisodeGuideTemplate.id != template.id,
                    EpisodeGuideTemplate.is_default == True
                ).update({'is_default': False})

            db.session.commit()
            flash('Template updated.', 'success')
            return redirect(url_for('podcasts.edit_template', podcast_id=podcast_id, template_id=template_id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Update template', e)
            flash('Database error occurred. Please try again.', 'error')

    return render_template('podcasts/templates/form.html',
        podcast=podcast,
        template=template,
        intro_content=template.intro_static_content or INTRO_STATIC_CONTENT,
        outro_content=template.outro_static_content or OUTRO_STATIC_CONTENT,
        user_role=g.user_podcast_role,
    )


@podcast_bp.route('/<int:podcast_id>/templates/<int:template_id>/delete', methods=['POST'])
@login_required
@require_podcast_admin
def delete_template(podcast_id, template_id):
    """Delete a template."""
    template = EpisodeGuideTemplate.query.filter_by(
        id=template_id,
        podcast_id=podcast_id
    ).first_or_404()

    try:
        name = template.name
        db.session.delete(template)
        db.session.commit()
        flash(f'Template "{name}" deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Delete template', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('podcasts.list_templates', podcast_id=podcast_id))
