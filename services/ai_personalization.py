"""AI email personalization via OpenAI GPT-4. (Source: Instantly AI — services/ai_personalization.py)

Tenacity retry on rate limits, graceful fallback to template rendering.
"""

import asyncio
import logging
from string import Template
from typing import Optional

from openai import AsyncOpenAI, RateLimitError, APITimeoutError, APIConnectionError
from tenacity import (
    retry, retry_if_exception_type, stop_after_attempt, wait_exponential,
)

from config import settings

logger = logging.getLogger(__name__)


def render_template(template: str, variables: dict) -> str:
    try:
        return template.format_map(variables)
    except KeyError:
        return template


class AIPersonalizationService:
    def __init__(self, client: Optional[AsyncOpenAI] = None) -> None:
        self._client = client
        if client is None and settings.OPENAI_API_KEY:
            self._client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=settings.OPENAI_TIMEOUT,
                max_retries=0,
            )

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=False,
    )
    async def _call_openai(self, prompt: str, context: str) -> str:
        if self._client is None:
            raise RuntimeError("OpenAI client not configured")
        response = await self._client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert B2B cold email copywriter for the Russian market. "
                        "Rewrite the provided email to be more personalized and compelling "
                        "for the specific recipient. Keep it concise and professional. "
                        "Write in Russian if the original is in Russian. "
                        "Return ONLY the rewritten text, no explanation."
                    ),
                },
                {"role": "user", "content": f"Recipient:\n{context}\n\nEmail:\n{prompt}"},
            ],
            temperature=0.7,
            max_tokens=500,
        )
        return response.choices[0].message.content or prompt

    async def personalize(
        self,
        subject_template: str,
        body_template: str,
        contact: dict,
    ) -> tuple[str, str]:
        variables = {
            "first_name": contact.get("first_name", ""),
            "last_name": contact.get("last_name", ""),
            "company": contact.get("company", ""),
            "title": contact.get("title", ""),
            "email": contact.get("email", ""),
        }
        context = "\n".join(f"{k}: {v}" for k, v in variables.items() if v)

        fallback_subject = render_template(subject_template, variables)
        fallback_body = render_template(body_template, variables)

        if self._client is None:
            return fallback_subject, fallback_body

        try:
            subject, body = await asyncio.gather(
                self._call_openai(f"Subject: {subject_template}", context),
                self._call_openai(body_template, context),
            )
            subject = subject.strip().removeprefix("Subject:").strip()
            return (subject or fallback_subject), (body or fallback_body)
        except Exception as exc:
            logger.warning("AI personalization failed: %s. Using template.", exc)
            return fallback_subject, fallback_body
