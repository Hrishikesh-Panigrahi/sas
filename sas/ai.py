"""Thin wrapper around the Claude API for structured (JSON) answers.

Claude is used when AI_TOKEN is set; otherwise `enabled()` is False and callers
use the built-in analyst instead. Every call returns parsed JSON matching the
given schema, or raises AIError with a message safe to show to users.
"""
import json
import logging

from django.conf import settings

log = logging.getLogger(__name__)


class AIError(Exception):
    pass


def enabled():
    return bool(settings.AI_TOKEN)


def ask_json(system, prompt, schema, effort='medium', max_tokens=16000):
    """Ask Claude for a JSON object matching `schema` (a JSON Schema dict)."""
    if not enabled():
        raise AIError('Claude is not configured. Add AI_TOKEN to sas/.env to turn it on.')

    import anthropic

    client = anthropic.Anthropic(api_key=settings.AI_TOKEN, timeout=60.0, max_retries=2)
    try:
        response = client.beta.messages.create(
            model=settings.AI_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{'role': 'user', 'content': prompt}],
            output_config={'effort': effort,
                           'format': {'type': 'json_schema', 'schema': schema}},
            # If the model declines, retry on Anthropic's recommended fallback model.
            betas=['server-side-fallback-2026-07-01'],
            fallbacks='default',
        )
    except anthropic.AuthenticationError:
        raise AIError('The AI token was rejected. Check AI_TOKEN in sas/.env.')
    except anthropic.RateLimitError:
        raise AIError('The AI service is busy right now. Try again in a minute.')
    except anthropic.APIStatusError as e:
        log.warning('Claude API error %s: %s', e.status_code, e.message)
        raise AIError('The AI service returned an error (%s). Try again later.' % e.status_code)
    except anthropic.APIConnectionError:
        raise AIError("Couldn't reach the AI service. Check the internet connection.")

    if response.stop_reason == 'refusal':
        raise AIError('The AI declined to answer this request.')
    if response.stop_reason == 'max_tokens':
        raise AIError('The AI answer was cut off. Try again.')
    text = next((b.text for b in response.content if b.type == 'text'), '')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning('Claude returned invalid JSON (request %s)', response._request_id)
        raise AIError('The AI returned an unreadable answer. Try again.')
