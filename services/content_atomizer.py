"""Content Atomizer service for AI-powered content repurposing.

This service handles:
- Generating platform-optimized snippets from long-form content
- Supporting multiple AI providers (OpenAI, Anthropic)
- Rate limiting and error handling for AI API calls
- Template-based prompt construction
"""

import os
import time
import json
import requests
from functools import wraps
from datetime import datetime, timezone
from flask import current_app
from extensions import db
from models import ContentAtomicSnippet, ContentAtomicTemplate, EpisodeGuide


def rate_limit(min_interval=1.0):
    """
    Decorator to enforce minimum interval between API calls.

    Args:
        min_interval: Minimum seconds between calls (default 1s for AI APIs)
    """
    last_call = [0]

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            result = func(*args, **kwargs)
            last_call[0] = time.time()
            return result
        return wrapper
    return decorator


class ContentAtomizerError(Exception):
    """Base exception for Content Atomizer errors."""

    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(message)


class AIProviderError(ContentAtomizerError):
    """Error from AI provider (OpenAI, Anthropic, etc.)."""
    pass


class ConfigurationError(ContentAtomizerError):
    """Missing or invalid configuration."""
    pass


class ContentAtomizerService:
    """Service for AI-powered content atomization."""

    # Default platform configurations
    PLATFORM_CONFIGS = {
        'twitter': {
            'max_length': 280,
            'display_name': 'Twitter/X',
            'style': 'concise, punchy, engaging',
            'default_hashtags': True,
        },
        'instagram': {
            'max_length': 2200,
            'display_name': 'Instagram',
            'style': 'visual, storytelling, engaging with emojis',
            'default_hashtags': True,
        },
        'youtube': {
            'max_length': 5000,
            'display_name': 'YouTube Description',
            'style': 'descriptive, SEO-friendly, includes timestamps and links',
            'default_hashtags': False,
        },
        'linkedin': {
            'max_length': 3000,
            'display_name': 'LinkedIn',
            'style': 'professional, insightful, thought leadership',
            'default_hashtags': True,
        },
        'tiktok': {
            'max_length': 2200,
            'display_name': 'TikTok',
            'style': 'trendy, fun, uses trending sounds/hashtags references',
            'default_hashtags': True,
        },
        'threads': {
            'max_length': 500,
            'display_name': 'Threads',
            'style': 'conversational, engaging, community-focused',
            'default_hashtags': False,
        },
        'bluesky': {
            'max_length': 300,
            'display_name': 'Bluesky',
            'style': 'concise, authentic, community-oriented',
            'default_hashtags': False,
        },
    }

    # AI Provider constants
    PROVIDER_OPENAI = 'openai'
    PROVIDER_ANTHROPIC = 'anthropic'

    def __init__(self, provider=None, api_key=None, model=None):
        """
        Initialize Content Atomizer service.

        Args:
            provider: AI provider ('openai' or 'anthropic')
            api_key: API key (or fetched from environment)
            model: Model name (or uses default for provider)
        """
        self.provider = provider or os.environ.get('AI_PROVIDER', self.PROVIDER_OPENAI)
        self.api_key = api_key
        self.model = model

        # Set defaults based on provider
        if self.provider == self.PROVIDER_OPENAI:
            self.api_key = self.api_key or os.environ.get('OPENAI_API_KEY')
            self.model = self.model or os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
            self.base_url = 'https://api.openai.com/v1'
        elif self.provider == self.PROVIDER_ANTHROPIC:
            self.api_key = self.api_key or os.environ.get('ANTHROPIC_API_KEY')
            self.model = self.model or os.environ.get('ANTHROPIC_MODEL', 'claude-3-haiku-20240307')
            self.base_url = 'https://api.anthropic.com/v1'

    @property
    def is_configured(self):
        """Check if AI API is configured."""
        return bool(self.api_key)

    @classmethod
    def get_available_platforms(cls):
        """Get list of available platforms."""
        return list(cls.PLATFORM_CONFIGS.keys())

    @classmethod
    def get_platform_config(cls, platform):
        """Get configuration for a platform."""
        return cls.PLATFORM_CONFIGS.get(platform)

    def _build_prompt(self, source_content, platform, template=None, options=None):
        """
        Build the AI prompt for content generation.

        Args:
            source_content: Original long-form content
            platform: Target platform
            template: Optional ContentAtomicTemplate instance
            options: Additional options (tone, hashtags, etc.)
        """
        options = options or {}
        config = self.PLATFORM_CONFIGS.get(platform, {})
        max_length = template.max_length if template and template.max_length else config.get('max_length', 280)

        # Use template prompt if provided
        if template and template.prompt_template:
            prompt = template.prompt_template.replace('{content}', source_content)
            prompt = prompt.replace('{max_length}', str(max_length))
            prompt = prompt.replace('{platform}', config.get('display_name', platform.title()))
        else:
            # Default prompt
            style = config.get('style', 'engaging and concise')
            prompt = f"""Transform the following content into a {config.get('display_name', platform.title())} post.

Requirements:
- Style: {style}
- Maximum length: {max_length} characters
- Make it engaging and shareable
"""
            if options.get('include_hashtags', config.get('default_hashtags')):
                prompt += "- Include 2-4 relevant hashtags\n"

            if options.get('include_emoji', False):
                prompt += "- Use appropriate emojis to enhance engagement\n"

            if options.get('include_cta', False):
                prompt += "- Include a call-to-action\n"

            if options.get('tone'):
                prompt += f"- Tone: {options['tone']}\n"

            prompt += f"""
Original Content:
{source_content}

Generate only the {platform} post content. No explanations or meta-commentary."""

        return prompt

    def _build_system_prompt(self, template=None):
        """Build system prompt for AI."""
        if template and template.system_prompt:
            return template.system_prompt

        return """You are a social media content expert who transforms long-form content into engaging, platform-optimized posts. You understand each platform's unique culture, character limits, and best practices. Generate only the final post content without any explanations, commentary, or formatting like "Here's your post:" - just the post itself."""

    @rate_limit(min_interval=0.5)
    def _call_openai(self, prompt, system_prompt, temperature=0.7):
        """
        Call OpenAI API.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Creativity setting (0-1)

        Returns:
            dict with 'content', 'model', 'usage'
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': temperature,
            'max_tokens': 1000,
        }

        try:
            start_time = time.time()
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            )
            generation_time = int((time.time() - start_time) * 1000)

            if response.status_code == 429:
                raise AIProviderError("Rate limited by OpenAI. Please try again later.")
            elif response.status_code == 401:
                raise ConfigurationError("Invalid OpenAI API key.")
            elif response.status_code != 200:
                error_msg = response.json().get('error', {}).get('message', 'Unknown error')
                raise AIProviderError(f"OpenAI API error: {error_msg}")

            data = response.json()
            return {
                'content': data['choices'][0]['message']['content'].strip(),
                'model': data.get('model', self.model),
                'generation_time_ms': generation_time,
                'usage': data.get('usage', {}),
            }

        except requests.Timeout:
            raise AIProviderError("OpenAI API request timed out. Please try again.")
        except requests.ConnectionError:
            raise AIProviderError("Failed to connect to OpenAI API.")
        except requests.RequestException as e:
            raise AIProviderError(f"OpenAI API request failed: {str(e)}")

    @rate_limit(min_interval=0.5)
    def _call_anthropic(self, prompt, system_prompt, temperature=0.7):
        """
        Call Anthropic API.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Creativity setting (0-1)

        Returns:
            dict with 'content', 'model', 'usage'
        """
        headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01',
        }

        payload = {
            'model': self.model,
            'max_tokens': 1000,
            'system': system_prompt,
            'messages': [
                {'role': 'user', 'content': prompt},
            ],
            'temperature': temperature,
        }

        try:
            start_time = time.time()
            response = requests.post(
                f'{self.base_url}/messages',
                headers=headers,
                json=payload,
                timeout=30
            )
            generation_time = int((time.time() - start_time) * 1000)

            if response.status_code == 429:
                raise AIProviderError("Rate limited by Anthropic. Please try again later.")
            elif response.status_code == 401:
                raise ConfigurationError("Invalid Anthropic API key.")
            elif response.status_code != 200:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                raise AIProviderError(f"Anthropic API error: {error_msg}")

            data = response.json()
            content = data['content'][0]['text'].strip() if data.get('content') else ''

            return {
                'content': content,
                'model': data.get('model', self.model),
                'generation_time_ms': generation_time,
                'usage': data.get('usage', {}),
            }

        except requests.Timeout:
            raise AIProviderError("Anthropic API request timed out. Please try again.")
        except requests.ConnectionError:
            raise AIProviderError("Failed to connect to Anthropic API.")
        except requests.RequestException as e:
            raise AIProviderError(f"Anthropic API request failed: {str(e)}")

    def generate(self, source_content, platform, template=None, options=None, temperature=0.7):
        """
        Generate a platform-optimized snippet from source content.

        Args:
            source_content: Original long-form content
            platform: Target platform (twitter, instagram, etc.)
            template: Optional ContentAtomicTemplate instance
            options: Additional generation options
            temperature: AI creativity setting (0-1)

        Returns:
            dict with 'content', 'model', 'generation_time_ms', etc.
        """
        if not self.is_configured:
            raise ConfigurationError(
                f"AI API not configured. Set {self.provider.upper()}_API_KEY environment variable."
            )

        if platform not in self.PLATFORM_CONFIGS:
            raise ContentAtomizerError(f"Unsupported platform: {platform}", field='platform')

        if not source_content or not source_content.strip():
            raise ContentAtomizerError("Source content is required.", field='source_content')

        prompt = self._build_prompt(source_content, platform, template, options)
        system_prompt = self._build_system_prompt(template)

        if self.provider == self.PROVIDER_OPENAI:
            result = self._call_openai(prompt, system_prompt, temperature)
        elif self.provider == self.PROVIDER_ANTHROPIC:
            result = self._call_anthropic(prompt, system_prompt, temperature)
        else:
            raise ConfigurationError(f"Unsupported AI provider: {self.provider}")

        # Add metadata
        result['platform'] = platform
        result['character_count'] = len(result['content'])
        result['word_count'] = len(result['content'].split())

        # Extract hashtags if present
        hashtags = [tag for tag in result['content'].split() if tag.startswith('#')]
        if hashtags:
            result['hashtags'] = hashtags

        return result

    def generate_and_save(self, user_id, source_content, platform, template_id=None,
                          source_type='manual', source_id=None, source_title=None, options=None):
        """
        Generate a snippet and save it to the database.

        Args:
            user_id: User ID
            source_content: Original content
            platform: Target platform
            template_id: Optional template ID
            source_type: Type of source (manual, episode, etc.)
            source_id: Optional source ID (e.g., episode_guides.id)
            source_title: Optional source title for display
            options: Additional generation options

        Returns:
            ContentAtomicSnippet instance
        """
        # Load template if provided
        template = None
        if template_id:
            template = ContentAtomicTemplate.query.filter_by(
                id=template_id,
                user_id=user_id,
                is_active=True
            ).first()

        # Generate content
        result = self.generate(source_content, platform, template, options)

        # Create snippet record
        snippet = ContentAtomicSnippet(
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            source_title=source_title,
            template_id=template_id,
            platform=platform,
            source_content=source_content,
            generated_content=result['content'],
            character_count=result['character_count'],
            word_count=result['word_count'],
            hashtags=result.get('hashtags'),
            ai_model=result['model'],
            ai_temperature=options.get('temperature', 0.7) if options else 0.7,
            generation_time_ms=result.get('generation_time_ms'),
            status=ContentAtomicSnippet.STATUS_DRAFT,
        )

        db.session.add(snippet)

        # Update template usage count
        if template:
            template.times_used = (template.times_used or 0) + 1

        db.session.commit()

        return snippet

    def regenerate(self, snippet_id, user_id, options=None):
        """
        Regenerate content for an existing snippet.

        Args:
            snippet_id: Snippet ID
            user_id: User ID (for ownership verification)
            options: Additional generation options

        Returns:
            Updated ContentAtomicSnippet instance
        """
        snippet = ContentAtomicSnippet.query.filter_by(
            id=snippet_id,
            user_id=user_id
        ).first()

        if not snippet:
            raise ContentAtomizerError("Snippet not found.", field='snippet_id')

        # Load template if originally used
        template = snippet.template if snippet.template_id else None

        # Generate new content
        result = self.generate(snippet.source_content, snippet.platform, template, options)

        # Update snippet
        snippet.generated_content = result['content']
        snippet.edited_content = None  # Clear any edits
        snippet.character_count = result['character_count']
        snippet.word_count = result['word_count']
        snippet.hashtags = result.get('hashtags')
        snippet.ai_model = result['model']
        snippet.generation_time_ms = result.get('generation_time_ms')
        snippet.status = ContentAtomicSnippet.STATUS_DRAFT

        db.session.commit()

        return snippet

    @classmethod
    def get_source_content_from_episode(cls, episode_id, user_id=None):
        """
        Extract source content from an episode guide.

        Args:
            episode_id: Episode guide ID
            user_id: Optional user ID for access check

        Returns:
            dict with 'title', 'content', 'id'
        """
        episode = EpisodeGuide.query.get(episode_id)
        if not episode:
            raise ContentAtomizerError("Episode not found.", field='episode_id')

        # Build content from episode data
        content_parts = []

        if episode.title:
            content_parts.append(f"Title: {episode.title}")

        if episode.notes:
            content_parts.append(f"\n{episode.notes}")

        # Add items/topics
        if episode.items:
            topics = [item.title for item in episode.items if item.title]
            if topics:
                content_parts.append(f"\nTopics covered: {', '.join(topics)}")

        content = '\n'.join(content_parts)

        return {
            'id': episode.id,
            'title': episode.title,
            'content': content,
        }
