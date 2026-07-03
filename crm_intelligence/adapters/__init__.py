"""Platform adapters — normalize raw CRM exports into the canonical schema."""

from crm_intelligence.adapters.registry import adapt_file, detect_platform

__all__ = ["adapt_file", "detect_platform"]
