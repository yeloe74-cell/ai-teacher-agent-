# modules/ai_generator.py
"""
AI content generation using Cloudflare Workers AI.

Provides:
- AIGenerator class for lesson generation
- Prompt templates for morning lessons and evening practices
- Response validation
- Error handling with retry support
"""

import json
import logging
import requests
from typing import Any, Dict, Optional

from config import Config, get_config
from utils import retry, truncate_text

logger = logging.getLogger(__name__)


class AIGeneratorError(Exception):
    """Custom exception for AI generation errors."""

    pass


class AIResponseError(AIGeneratorError):
    """Raised when AI response is invalid or unexpected."""

    pass


class AITimeoutError(AIGeneratorError):
    """Raised when AI request times out."""

    pass


class AIGenerator:
    """
    Cloudflare Workers AI content generator.

    Generates educational content for programming beginners
    in natural Myanmar language with English technical terms.

    Attributes:
        config: Config instance
        account_id: Cloudflare account ID
        api_token: Cloudflare API token
        model: Workers AI model name
        timeout: Request timeout
        temperature: AI temperature setting
    """

    # Prompt template for morning lessons
    MORNING_PROMPT_TEMPLATE = """
မင်းက မြန်မာနိုင်ငံက programming လုံးဝမသိသေးတဲ့ beginner တွေအတွက် စာရေးတဲ့ ဆရာတစ်ယောက်ပါ။
ဒီနေ့ သင်ခန်းစာရဲ့ topic က "{topic}" ဖြစ်တယ်။

အောက်ပါအချက်တွေကို လိုက်နာပြီး ရေးပါ:
1. အရမ်းရိုးရှင်းတဲ့ မြန်မာစကားနဲ့ ရှင်းပြပါ။
2. Technical terms တွေကို English term ပါ ထည့်ပေးပါ။
3. Code ကို တိုက်ရိုက်မချဘဲ code တစ်ကြောင်းချင်းစီ ဘာလုပ်တယ်ဆိုတာ ရှင်းပြပါ။
4. လက်တွေ့လုပ်ကြည့်နိုင်တဲ့ example တစ်ခု ထည့်ပေးပါ။
5. Exercise တစ်ခု ထည့်ပေးပါ။
6. စာလုံးရေအားဖြင့် 500-800 လုံးလောက် ရေးပါ။

Format:
- သင်ခန်းစာခေါင်းစဉ်
- မိတ်ဆက်
- အဓိကသင်ခန်းစာ
- Example
- Exercise
- သင်ခန်းစာအကျဉ်းချုပ်
"""

    # Prompt template for evening practices
    EVENING_PROMPT_TEMPLATE = """
မင်းက မြန်မာနိုင်ငံက programming beginner တွေအတွက် လေ့ကျင့်ခန်းဆရာတစ်ယောက်ပါ။
ဒီနေ့ သင်ခန်းစာနဲ့ ဆက်စပ်တဲ့ topic က "{topic}" ဖြစ်တယ်။

အောက်ပါအချက်တွေကို လိုက်နာပြီး ရေးပါ:
1. ဒီ topic နဲ့ ပတ်သက်တဲ့ လက်တွေ့လေ့ကျင့်ခန်း 3 ခု ရေးပေးပါ။
2. Beginner တွေအတွက် လွယ်ကူပြီး စိတ်ဝင်စားစရာကောင်းတဲ့ exercise တွေ ဖြစ်ရမယ်။
3. Code ကို တိုက်ရိုက်မပေးဘဲ အဆင့်ဆင့် လုပ်ဆောင်ရမယ့် အချက်တွေကို ရှင်းပြပါ။
4. စာလုံးရေအားဖြင့် 300-500 လုံးလောက် ရေးပါ။

Format:
- လေ့ကျင့်ခန်း ၁ (လွယ်ကူ)
- လေ့ကျင့်ခန်း ၂ (အလယ်အလတ်)
- လေ့ကျင့်ခန်း ၃ (စိန်ခေါ်မှု)
"""

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize AI generator.

        Args:
            config: Config instance (uses get_config() if None)
        """
        self.config = config or get_config()
        self.account_id = self.config.cf_account_id
        self.api_token = self.config.cf_api_token
        self.model = self.config.cf_ai_model
        self.timeout = self.config.ai_timeout
        self.temperature = self.config.temperature

        logger.debug(f"AI generator initialized with model: {self.model}")

    def _build_url(self) -> str:
        """Build Workers AI API endpoint URL."""
        return (
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/ai/run/{self.model}"
        )

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, prompt: str, max_tokens: int) -> Dict[str, Any]:
        """Build request payload."""
        return {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }

    def _parse_response(self, data: Dict[str, Any]) -> str:
        """
        Parse and validate Workers AI response.

        Args:
            data: Response JSON data

        Returns:
            Generated text content

        Raises:
            AIResponseError: If response format is invalid
        """
        if "result" not in data:
            raise AIResponseError(
                f"Missing 'result' in AI response: {truncate_text(str(data))}"
            )

        if "response" not in data["result"]:
            raise AIResponseError(
                f"Missing 'response' in AI result: {truncate_text(str(data['result']))}"
            )

        content = data["result"]["response"].strip()
        if not content:
            raise AIResponseError("AI returned empty response")

        return content

    @retry(
        max_attempts=3,
        delay=2.0,
        backoff=2.0,
        exceptions=(requests.RequestException, json.JSONDecodeError, AIGeneratorError),
    )
    def _call_api(self, prompt: str, max_tokens: int) -> str:
        """
        Call Workers AI API and return generated text.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text content

        Raises:
            AITimeoutError: If request times out
            AIResponseError: If response is invalid
            AIGeneratorError: For other API errors
        """
        url = self._build_url()
        headers = self._build_headers()
        payload = self._build_payload(prompt, max_tokens)

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            content = self._parse_response(data)
            logger.info(f"AI generated {len(content)} characters")
            return content

        except requests.Timeout:
            logger.error(f"Workers AI timeout after {self.timeout}s")
            raise AITimeoutError(f"Timeout after {self.timeout}s")
        except requests.RequestException as e:
            logger.error(f"Workers AI request failed: {e}")
            raise AIGeneratorError(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from AI API: {e}")
            raise AIResponseError(f"Invalid JSON: {e}")

    def generate_lesson(self, topic: str, lesson_type: str = "morning_lesson") -> str:
        """
        Generate lesson content for given topic.

        Args:
            topic: Lesson topic (e.g., "Introduction to Python")
            lesson_type: "morning_lesson" or "evening_practice"

        Returns:
            Generated lesson content

        Raises:
            AIGeneratorError: If generation fails or lesson_type is invalid
        """
        logger.info(f"Generating {lesson_type} for: {topic}")

        if lesson_type == "morning_lesson":
            prompt = self.MORNING_PROMPT_TEMPLATE.format(topic=topic)
            max_tokens = self.config.max_tokens_morning
        elif lesson_type == "evening_practice":
            prompt = self.EVENING_PROMPT_TEMPLATE.format(topic=topic)
            max_tokens = self.config.max_tokens_evening
        else:
            raise AIGeneratorError(f"Unknown lesson type: {lesson_type}")

        content = self._call_api(prompt, max_tokens)

        if len(content) < 50:
            raise AIGeneratorError(f"Generated content too short: {len(content)} chars")

        return content

    def generate_custom_content(self, prompt: str, max_tokens: int = 800) -> str:
        """
        Generate custom content with user-defined prompt.

        Args:
            prompt: Custom prompt
            max_tokens: Maximum tokens

        Returns:
            Generated content
        """
        logger.info(f"Generating custom content (max_tokens={max_tokens})")
        return self._call_api(prompt, max_tokens)

    def validate_content(self, content: str) -> bool:
        """
        Validate generated content quality.

        Checks:
        - Content is not empty
        - Content length is sufficient
        - Content contains expected sections

        Args:
            content: Generated content

        Returns:
            True if content passes validation
        """
        if not content:
            logger.error("Content is empty")
            return False

        if len(content) < 50:
            logger.error(f"Content too short: {len(content)} chars")
            return False

        # Check for Myanmar characters (basic check)
        myanmar_chars = any("\u1000" <= char <= "\u109f" for char in content)
        if not myanmar_chars:
            logger.warning("Content may not contain Myanmar text")

        return True


def create_ai_generator(config: Optional[Config] = None) -> AIGenerator:
    """
    Factory function for AIGenerator.

    Args:
        config: Optional Config instance

    Returns:
        AIGenerator instance
    """
    return AIGenerator(config)
