"""Shared Anthropic client setup.

Every agent in this pipeline is a plain client.messages.create() call with its own
system prompt — there's no framework. This module just centralizes the client
construction and the model default so that's not repeated five times.
"""

import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Haiku default: this project is about the multi-agent orchestration pattern, not
# squeezing quality out of a large model. Override with ANTHROPIC_MODEL if needed.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def get_client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return Anthropic(api_key=api_key)


def get_model() -> str:
    return os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)
