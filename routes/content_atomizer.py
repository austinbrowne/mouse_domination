"""Creator Hub: Content Atomizer Routes

Routes for AI-powered content repurposing - transforming long-form content
into platform-optimized snippets for Twitter, Instagram, LinkedIn, etc.
"""
from datetime import datetime, timezone
from flask_login import login_required, current_user
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, abort, jsonify
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from models import ContentAtomicSnippet, ContentAtomicTemplate, EpisodeGuide, SocialConnection
from extensions import db
from constants import DEFAULT_PAGE_SIZE
from services.content_atomizer import (
    ContentAtomizerService,
    ContentAtomizerError,
    AIProviderError,
    ConfigurationError,
)
from utils.validation import ValidationError
from utils.routes import FormData
from utils.logging import log_exception

atomizer_bp = Blueprint('atomizer', __name__)


# ============== Snippet Routes ==============

@atomizer_bp.route('/')
@login_required
def list_snippets():
    """List all generated snippets with filtering."""
    platform = request.args.get('platform')
    status = request.args.get('status')
    source_type = request.args.get('source_type')
    page = request.args.get('page', 1, type=int)

    # Base query filtered by user
    query = ContentAtomicSnippet.query.filter_by(user_id=current_user.id)

    # Apply filters
    if platform and platform in ContentAtomizerService.get_available_platforms():
        query = query.filter_by(platform=platform)
    if status and status in [s[0] for s in ContentAtomicSnippet.STATUSES]:
        query = query.filter_by(status=status)
    if source_type and source_type in [s[0] for s in ContentAtomicSnippet.SOURCE_TYPES]:
        query = query.filter_by(source_type=source_type)

    # Paginate
    pagination = query.order_by(ContentAtomicSnippet.created_at.desc()).paginate(
        page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False
    )

    # Stats
    stats = db.session.query(
        func.count(ContentAtomicSnippet.id).label('total'),
        func.sum(func.cast(ContentAtomicSnippet.status == 'draft', db.Integer)).label('drafts'),
        func.sum(func.cast(ContentAtomicSnippet.status == 'approved', db.Integer)).label('approved'),
        func.sum(func.cast(ContentAtomicSnippet.status == 'published', db.Integer)).label('published'),
    ).filter(ContentAtomicSnippet.user_id == current_user.id).first()

    # Check if AI is configured
    service = ContentAtomizerService()
    ai_configured = service.is_configured

    return render_template('atomizer/list.html',
        snippets=pagination.items,
        pagination=pagination,
        platforms=ContentAtomizerService.PLATFORM_CONFIGS,
        statuses=ContentAtomicSnippet.STATUSES,
        source_types=ContentAtomicSnippet.SOURCE_TYPES,
        current_platform=platform,
        current_status=status,
        current_source_type=source_type,
        stats={
            'total': stats.total or 0,
            'drafts': stats.drafts or 0,
            'approved': stats.approved or 0,
            'published': stats.published or 0,
        },
        ai_configured=ai_configured,
    )


@atomizer_bp.route('/generate', methods=['GET', 'POST'])
@login_required
def generate_snippet():
    """Generate a new snippet from content."""
    service = ContentAtomizerService()

    if not service.is_configured:
        flash('AI API is not configured. Please set up your API key in environment variables.', 'warning')

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            source_type = form.choice('source_type',
                [s[0] for s in ContentAtomicSnippet.SOURCE_TYPES],
                default='manual')

            platform = form.choice('platform',
                ContentAtomizerService.get_available_platforms(),
                default='twitter')

            # Get source content based on type
            source_content = None
            source_id = None
            source_title = None

            if source_type == 'episode':
                episode_id = form.integer('episode_id')
                if not episode_id:
                    raise ValidationError('Episode', 'Please select an episode.')

                episode_data = service.get_source_content_from_episode(episode_id)
                source_content = episode_data['content']
                source_id = episode_data['id']
                source_title = episode_data['title']
            else:
                source_content = form.required('source_content')
                if not source_content:
                    raise ValidationError('Content', 'Please enter content to transform.')
                source_title = form.optional('source_title')

            # Get optional settings
            template_id = form.integer('template_id')
            options = {
                'include_hashtags': form.boolean('include_hashtags'),
                'include_emoji': form.boolean('include_emoji'),
                'include_cta': form.boolean('include_cta'),
                'tone': form.optional('tone'),
            }

            # Generate snippet
            snippet = service.generate_and_save(
                user_id=current_user.id,
                source_content=source_content,
                platform=platform,
                template_id=template_id,
                source_type=source_type,
                source_id=source_id,
                source_title=source_title,
                options=options,
            )

            flash(f'Snippet generated for {snippet.platform_display}!', 'success')
            return redirect(url_for('atomizer.edit_snippet', id=snippet.id))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except ConfigurationError as e:
            flash(f'Configuration error: {e.message}', 'error')
        except AIProviderError as e:
            flash(f'AI error: {e.message}', 'error')
        except ContentAtomizerError as e:
            flash(f'Error: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Generate snippet', e)
            flash('Database error occurred. Please try again.', 'error')

    # Get episodes for dropdown
    episodes = EpisodeGuide.query.filter(
        EpisodeGuide.podcast.has(
            EpisodeGuide.podcast.property.mapper.class_.members.any(user_id=current_user.id)
        )
    ).order_by(EpisodeGuide.created_at.desc()).limit(50).all()

    # Get user's templates
    templates = ContentAtomicTemplate.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(ContentAtomicTemplate.name).all()

    return render_template('atomizer/generate.html',
        episodes=episodes,
        templates=templates,
        platforms=ContentAtomizerService.PLATFORM_CONFIGS,
        source_types=ContentAtomicSnippet.SOURCE_TYPES,
        tones=ContentAtomicTemplate.TONES,
        ai_configured=service.is_configured,
    )


@atomizer_bp.route('/<int:id>')
@login_required
def view_snippet(id):
    """View a single snippet."""
    snippet = ContentAtomicSnippet.query.options(
        joinedload(ContentAtomicSnippet.template)
    ).get_or_404(id)

    if snippet.user_id != current_user.id:
        abort(403)

    # Check if user has Twitter connected (for posting)
    twitter_connection = None
    if snippet.platform == 'twitter':
        twitter_connection = SocialConnection.query.filter_by(
            user_id=current_user.id,
            platform='twitter',
            is_active=True
        ).first()

    return render_template('atomizer/view.html',
        snippet=snippet,
        platforms=ContentAtomizerService.PLATFORM_CONFIGS,
        twitter_connection=twitter_connection,
    )


@atomizer_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_snippet(id):
    """Edit a generated snippet."""
    snippet = ContentAtomicSnippet.query.get_or_404(id)
    if snippet.user_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            # Update editable fields
            edited_content = form.optional('edited_content')
            if edited_content and edited_content != snippet.generated_content:
                snippet.edited_content = edited_content
                snippet.character_count = len(edited_content)
                snippet.word_count = len(edited_content.split())
            elif not edited_content:
                # Clear edits, revert to generated
                snippet.edited_content = None
                snippet.character_count = len(snippet.generated_content)
                snippet.word_count = len(snippet.generated_content.split())

            snippet.status = form.choice('status',
                [s[0] for s in ContentAtomicSnippet.STATUSES],
                default=snippet.status)

            # Optional fields
            if form.optional('published_url'):
                snippet.published_url = form.optional('published_url')

            rating = form.integer('rating')
            if rating and 1 <= rating <= 5:
                snippet.rating = rating

            snippet.feedback_notes = form.optional('feedback_notes')

            db.session.commit()
            flash('Snippet updated successfully.', 'success')
            return redirect(url_for('atomizer.list_snippets'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Edit snippet', e)
            flash('Database error occurred. Please try again.', 'error')

    platform_config = ContentAtomizerService.get_platform_config(snippet.platform)

    # Check if user has Twitter connected (for posting)
    twitter_connection = None
    if snippet.platform == 'twitter':
        twitter_connection = SocialConnection.query.filter_by(
            user_id=current_user.id,
            platform='twitter',
            is_active=True
        ).first()

    return render_template('atomizer/edit.html',
        snippet=snippet,
        statuses=ContentAtomicSnippet.STATUSES,
        platform_config=platform_config,
        twitter_connection=twitter_connection,
    )


@atomizer_bp.route('/<int:id>/regenerate', methods=['POST'])
@login_required
def regenerate_snippet(id):
    """Regenerate content for an existing snippet."""
    snippet = ContentAtomicSnippet.query.get_or_404(id)
    if snippet.user_id != current_user.id:
        abort(403)

    try:
        service = ContentAtomizerService()
        snippet = service.regenerate(id, current_user.id)
        flash('Snippet regenerated successfully!', 'success')
    except ConfigurationError as e:
        flash(f'Configuration error: {e.message}', 'error')
    except AIProviderError as e:
        flash(f'AI error: {e.message}', 'error')
    except ContentAtomizerError as e:
        flash(f'Error: {e.message}', 'error')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Regenerate snippet', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('atomizer.edit_snippet', id=id))


@atomizer_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_snippet(id):
    """Delete a snippet."""
    try:
        snippet = ContentAtomicSnippet.query.get_or_404(id)
        if snippet.user_id != current_user.id:
            abort(403)

        db.session.delete(snippet)
        db.session.commit()
        flash('Snippet deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Delete snippet', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('atomizer.list_snippets'))


@atomizer_bp.route('/<int:id>/approve', methods=['POST'])
@login_required
def approve_snippet(id):
    """Quick action to approve a snippet."""
    try:
        snippet = ContentAtomicSnippet.query.get_or_404(id)
        if snippet.user_id != current_user.id:
            abort(403)

        snippet.status = ContentAtomicSnippet.STATUS_APPROVED
        db.session.commit()
        flash('Snippet approved.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Approve snippet', e)
        flash('Database error occurred.', 'error')

    return redirect(url_for('atomizer.list_snippets'))


@atomizer_bp.route('/<int:id>/copy', methods=['POST'])
@login_required
def copy_snippet(id):
    """Return snippet content as JSON for clipboard copy."""
    snippet = ContentAtomicSnippet.query.get_or_404(id)
    if snippet.user_id != current_user.id:
        abort(403)

    return jsonify({
        'success': True,
        'content': snippet.final_content,
        'character_count': len(snippet.final_content),
    })


# ============== Template Routes ==============

@atomizer_bp.route('/templates')
@login_required
def list_templates():
    """List user's AI prompt templates."""
    platform = request.args.get('platform')
    page = request.args.get('page', 1, type=int)

    query = ContentAtomicTemplate.query.filter_by(user_id=current_user.id)

    if platform and platform in ContentAtomizerService.get_available_platforms():
        query = query.filter_by(platform=platform)

    pagination = query.order_by(
        ContentAtomicTemplate.is_default.desc(),
        ContentAtomicTemplate.name
    ).paginate(page=page, per_page=DEFAULT_PAGE_SIZE, error_out=False)

    return render_template('atomizer/templates/list.html',
        templates=pagination.items,
        pagination=pagination,
        platforms=ContentAtomizerService.PLATFORM_CONFIGS,
        current_platform=platform,
    )


@atomizer_bp.route('/templates/new', methods=['GET', 'POST'])
@login_required
def new_template():
    """Create a new AI prompt template."""
    if request.method == 'POST':
        try:
            form = FormData(request.form)

            name = form.required('name')
            if not name:
                raise ValidationError('Name', 'Template name is required.')

            platform = form.choice('platform',
                ContentAtomizerService.get_available_platforms(),
                default='twitter')

            prompt_template = form.required('prompt_template')
            if not prompt_template:
                raise ValidationError('Prompt', 'Prompt template is required.')

            # Get platform's default max length
            platform_config = ContentAtomizerService.get_platform_config(platform)
            default_max = platform_config.get('max_length', 280) if platform_config else 280

            template = ContentAtomicTemplate(
                user_id=current_user.id,
                name=name,
                platform=platform,
                description=form.optional('description'),
                prompt_template=prompt_template,
                system_prompt=form.optional('system_prompt'),
                tone=form.optional('tone'),
                max_length=form.integer('max_length') or default_max,
                include_hashtags=form.boolean('include_hashtags'),
                include_emoji=form.boolean('include_emoji'),
                include_cta=form.boolean('include_cta'),
                is_default=form.boolean('is_default'),
            )

            # If setting as default, unset other defaults for this platform
            if template.is_default:
                ContentAtomicTemplate.query.filter_by(
                    user_id=current_user.id,
                    platform=platform,
                    is_default=True
                ).update({'is_default': False})

            db.session.add(template)
            db.session.commit()
            flash('Template created successfully.', 'success')
            return redirect(url_for('atomizer.list_templates'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Create template', e)
            flash('Database error occurred. Please try again.', 'error')

    return render_template('atomizer/templates/form.html',
        template=None,
        platforms=ContentAtomizerService.PLATFORM_CONFIGS,
        tones=ContentAtomicTemplate.TONES,
    )


@atomizer_bp.route('/templates/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(id):
    """Edit an existing template."""
    template = ContentAtomicTemplate.query.get_or_404(id)
    if template.user_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        try:
            form = FormData(request.form)

            name = form.required('name')
            if not name:
                raise ValidationError('Name', 'Template name is required.')

            prompt_template = form.required('prompt_template')
            if not prompt_template:
                raise ValidationError('Prompt', 'Prompt template is required.')

            template.name = name
            template.platform = form.choice('platform',
                ContentAtomizerService.get_available_platforms(),
                default=template.platform)
            template.description = form.optional('description')
            template.prompt_template = prompt_template
            template.system_prompt = form.optional('system_prompt')
            template.tone = form.optional('tone')
            template.max_length = form.integer('max_length') or template.max_length
            template.include_hashtags = form.boolean('include_hashtags')
            template.include_emoji = form.boolean('include_emoji')
            template.include_cta = form.boolean('include_cta')

            new_is_default = form.boolean('is_default')
            if new_is_default and not template.is_default:
                # Unset other defaults for this platform
                ContentAtomicTemplate.query.filter(
                    ContentAtomicTemplate.user_id == current_user.id,
                    ContentAtomicTemplate.platform == template.platform,
                    ContentAtomicTemplate.id != template.id,
                    ContentAtomicTemplate.is_default == True
                ).update({'is_default': False})
            template.is_default = new_is_default

            db.session.commit()
            flash('Template updated successfully.', 'success')
            return redirect(url_for('atomizer.list_templates'))

        except ValidationError as e:
            flash(f'{e.field}: {e.message}', 'error')
        except SQLAlchemyError as e:
            db.session.rollback()
            log_exception(current_app.logger, 'Edit template', e)
            flash('Database error occurred. Please try again.', 'error')

    return render_template('atomizer/templates/form.html',
        template=template,
        platforms=ContentAtomizerService.PLATFORM_CONFIGS,
        tones=ContentAtomicTemplate.TONES,
    )


@atomizer_bp.route('/templates/<int:id>/delete', methods=['POST'])
@login_required
def delete_template(id):
    """Delete a template."""
    try:
        template = ContentAtomicTemplate.query.get_or_404(id)
        if template.user_id != current_user.id:
            abort(403)

        db.session.delete(template)
        db.session.commit()
        flash('Template deleted.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        log_exception(current_app.logger, 'Delete template', e)
        flash('Database error occurred. Please try again.', 'error')

    return redirect(url_for('atomizer.list_templates'))


# ============== API Routes ==============

@atomizer_bp.route('/api/generate', methods=['POST'])
@login_required
def api_generate():
    """API endpoint for generating snippets (for AJAX calls)."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        source_content = data.get('source_content')
        platform = data.get('platform', 'twitter')
        template_id = data.get('template_id')

        if not source_content:
            return jsonify({'success': False, 'error': 'Source content is required'}), 400

        if platform not in ContentAtomizerService.get_available_platforms():
            return jsonify({'success': False, 'error': f'Invalid platform: {platform}'}), 400

        service = ContentAtomizerService()

        options = {
            'include_hashtags': data.get('include_hashtags', False),
            'include_emoji': data.get('include_emoji', False),
            'include_cta': data.get('include_cta', False),
            'tone': data.get('tone'),
        }

        result = service.generate(source_content, platform, options=options)

        return jsonify({
            'success': True,
            'content': result['content'],
            'character_count': result['character_count'],
            'word_count': result['word_count'],
            'hashtags': result.get('hashtags', []),
            'model': result['model'],
        })

    except ConfigurationError as e:
        return jsonify({'success': False, 'error': f'Configuration error: {e.message}'}), 500
    except AIProviderError as e:
        return jsonify({'success': False, 'error': f'AI error: {e.message}'}), 500
    except ContentAtomizerError as e:
        return jsonify({'success': False, 'error': e.message}), 400
    except Exception as e:
        log_exception(current_app.logger, 'API generate', e)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@atomizer_bp.route('/api/platforms')
@login_required
def api_platforms():
    """Get available platforms and their configurations."""
    platforms = []
    for key, config in ContentAtomizerService.PLATFORM_CONFIGS.items():
        platforms.append({
            'id': key,
            'name': config['display_name'],
            'max_length': config['max_length'],
            'style': config['style'],
        })
    return jsonify({'success': True, 'platforms': platforms})
