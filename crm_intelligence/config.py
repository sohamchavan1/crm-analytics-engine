"""
Application configuration.

All settings are loaded from environment variables (via .env for local development).
This is the single source of truth for paths, API credentials, and runtime options.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists (local development only; production uses real env vars)
load_dotenv()


# --- Paths ---

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
STORAGE_DIR = PROJECT_ROOT / "storage"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
STORAGE_DIR.mkdir(exist_ok=True)


# --- AWS Bedrock (Claude) ---

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_BEARER_TOKEN = os.getenv("AWS_BEARER_TOKEN_BEDROCK", "")
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-opus-4-6-v1"
)


# --- Application Settings ---

# Minimum campaigns required for meaningful analysis
MIN_CAMPAIGNS_FOR_ANALYSIS = int(os.getenv("MIN_CAMPAIGNS", "5"))

# Maximum campaigns to send to LLM in classification batch
MAX_CAMPAIGNS_PER_LLM_BATCH = int(os.getenv("MAX_LLM_BATCH", "50"))

# Top/Bottom N for rankings
RANKING_TOP_N = int(os.getenv("RANKING_TOP_N", "5"))

# LLM temperature for classification (deterministic)
LLM_CLASSIFY_TEMPERATURE = 0.0

# LLM temperature for narration (slightly creative but grounded)
LLM_NARRATE_TEMPERATURE = 0.3

# Maximum retries for LLM structured output validation
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))


# --- Logging ---

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
