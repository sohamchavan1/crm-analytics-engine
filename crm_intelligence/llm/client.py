"""
Bedrock client wrapper — handles Claude API calls via Amazon Bedrock.

Encapsulates:
- AWS authentication and session management
- Request formatting for Bedrock's converse API
- Structured JSON extraction from responses
- Retry logic with exponential backoff
- Token usage tracking

This is the ONLY file that talks to AWS. Everything else uses it through
classify_campaigns() and narrate_facts().
"""

import json
import logging
import time
from typing import Any, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from crm_intelligence.config import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    BEDROCK_MODEL_ID,
    LLM_MAX_RETRIES,
)

logger = logging.getLogger(__name__)


class BedrockClientError(Exception):
    """Raised when Bedrock API call fails after all retries."""

    def __init__(self, message: str, last_error: Optional[Exception] = None):
        super().__init__(message)
        self.last_error = last_error


class TokenUsage:
    """Tracks token consumption across LLM calls."""

    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0

    def add(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.calls += 1

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __str__(self) -> str:
        return (
            f"TokenUsage(calls={self.calls}, "
            f"input={self.input_tokens:,}, output={self.output_tokens:,}, "
            f"total={self.total_tokens:,})"
        )


# Module-level usage tracker (accumulates across the run)
usage = TokenUsage()


def _get_client():
    """
    Create a Bedrock Runtime client with configured credentials.

    Supports three auth methods (checked in order):
    1. Bedrock API key (bearer token) - set AWS_BEARER_TOKEN_BEDROCK in .env
       This loads into the environment via python-dotenv, and boto3 picks it up
       automatically for Bedrock API key auth.
    2. Explicit IAM keys - AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY in .env
    3. Default boto3 credential chain (aws configure, instance role, etc.)
    """
    kwargs = {
        "region_name": AWS_REGION,
        "config": Config(
            read_timeout=600,  # 10 min — Opus narration can take 2-5 min
            connect_timeout=30,
            retries={"max_attempts": 0},  # We handle retries ourselves
        ),
    }

    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY

    # If AWS_BEARER_TOKEN_BEDROCK is set in .env, python-dotenv already loaded
    # it into os.environ, so boto3 picks it up via its credential chain.
    return boto3.client("bedrock-runtime", **kwargs)


def call_claude(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str:
    """
    Call Claude via Bedrock's converse API.

    Args:
        system_prompt: System-level instructions (role, format requirements).
        user_message: The actual data/question to process.
        temperature: 0.0 for classification, 0.3 for narration.
        max_tokens: Maximum response tokens.

    Returns:
        The raw text response from Claude.

    Raises:
        BedrockClientError: If all retries are exhausted.
    """
    client = _get_client()
    last_error = None

    for attempt in range(1, LLM_MAX_RETRIES + 2):
        try:
            logger.info(
                f"Bedrock call attempt {attempt}/{LLM_MAX_RETRIES + 1} "
                f"(model={BEDROCK_MODEL_ID}, temp={temperature})"
            )

            response = client.converse(
                modelId=BEDROCK_MODEL_ID,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": user_message}],
                    }
                ],
                system=[{"text": system_prompt}],
                inferenceConfig={
                    "temperature": temperature,
                    "maxTokens": max_tokens,
                },
            )

            # Extract response text
            output = response["output"]["message"]["content"][0]["text"]

            # Track token usage
            token_usage = response.get("usage", {})
            input_tokens = token_usage.get("inputTokens", 0)
            output_tokens = token_usage.get("outputTokens", 0)
            usage.add(input_tokens, output_tokens)

            logger.info(
                f"Bedrock call successful: {input_tokens} input + "
                f"{output_tokens} output tokens"
            )

            return output

        except ClientError as e:
            last_error = e
            error_code = e.response.get("Error", {}).get("Code", "Unknown")

            # Throttling - retry with backoff
            if error_code in ("ThrottlingException", "TooManyRequestsException"):
                wait = 2**attempt
                logger.warning(f"Rate limited, waiting {wait}s before retry...")
                time.sleep(wait)
                continue

            # Model errors that won't resolve with retry
            if error_code in (
                "ValidationException",
                "AccessDeniedException",
                "ResourceNotFoundException",
            ):
                raise BedrockClientError(
                    f"Bedrock API error (non-retryable): {error_code} - {e}",
                    last_error=e,
                )

            # Other errors - retry
            wait = 2**attempt
            logger.warning(f"Bedrock error ({error_code}), retrying in {wait}s: {e}")
            time.sleep(wait)

        except Exception as e:
            last_error = e
            wait = 2**attempt
            logger.warning(f"Unexpected error, retrying in {wait}s: {e}")
            time.sleep(wait)

    raise BedrockClientError(
        f"All {LLM_MAX_RETRIES + 1} attempts failed. Last error: {last_error}",
        last_error=last_error,
    )


def call_claude_json(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """
    Call Claude and parse the response as JSON.

    The system prompt should instruct Claude to respond with valid JSON only.
    This function extracts JSON from the response (handles markdown code fences).

    Args:
        system_prompt: Must include JSON output format instructions.
        user_message: Data to process.
        temperature: LLM temperature.
        max_tokens: Maximum response tokens.

    Returns:
        Parsed JSON as a Python dict.

    Raises:
        BedrockClientError: If API call fails.
        ValueError: If response is not valid JSON after extraction attempts.
    """
    raw = call_claude(system_prompt, user_message, temperature, max_tokens)

    # Try to extract JSON from the response
    # Claude sometimes wraps JSON in markdown code fences
    json_str = _extract_json(raw)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.debug(f"Raw response (first 500 chars): {raw[:500]}")
        raise ValueError(
            f"LLM response is not valid JSON. "
            f"Parse error: {e}\n"
            f"Response starts with: {raw[:200]}..."
        )


def _extract_json(text: str) -> str:
    """
    Extract JSON from a response that might be wrapped in markdown code fences.

    Handles:
    - Plain JSON (starts with { or [)
    - ```json\n{...}\n```
    - ```\n{...}\n```
    """
    text = text.strip()

    # Already valid JSON start
    if text.startswith("{") or text.startswith("["):
        return text

    # Try to extract from code fence
    if "```" in text:
        # Find content between first ``` and last ```
        parts = text.split("```")
        if len(parts) >= 3:
            content = parts[1]
            # Remove language identifier (e.g., "json\n")
            if content.startswith("json"):
                content = content[4:]
            return content.strip()

    # Last resort: find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    # Array case
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    # Give up — return as-is and let json.loads fail with a clear error
    return text
