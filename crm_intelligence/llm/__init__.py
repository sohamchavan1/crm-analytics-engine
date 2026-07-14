"""LLM Intelligence layer — classification and narration via Claude on Bedrock."""

from crm_intelligence.llm.classifier import classify_campaigns
from crm_intelligence.llm.merge import merge_classifications
from crm_intelligence.llm.narrator import narrate_facts

__all__ = ["classify_campaigns", "merge_classifications", "narrate_facts"]
