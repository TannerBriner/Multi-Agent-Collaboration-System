"""Tool schemas used to force structured output out of agents.

Each agent that must return structured data is given a single tool whose input schema
IS the output format. This is the reliable way to get valid JSON out of the API instead
of parsing prose — the model's tool-use path is trained specifically to fill a schema,
so we lean on that instead of asking it to "please respond in JSON" in a text block.

Schemas for the reviewer agent and channel drafters are added alongside those agents;
this file grows as the pipeline does.
"""

# See docs/brief_schema.md for the full field-by-field rationale.
SUBMIT_BRIEF_TOOL = {
    "name": "submit_brief",
    "description": (
        "Submit the structured campaign brief extracted from the request. Only call "
        "this when objective, audience, and key_message are all explicitly present (or "
        "safely inferable) in the request text. Do not fabricate any field."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "campaign_name": {
                "type": "string",
                "description": "Short name for the campaign, taken from the request or "
                "coined from its subject if not explicitly named.",
            },
            "objective": {
                "type": "string",
                "description": "The business outcome this campaign supports.",
            },
            "audience": {
                "type": "string",
                "description": "Who this reaches.",
            },
            "key_message": {
                "type": "string",
                "description": "The ONE thing every deliverable must communicate.",
            },
            "channels": {
                "type": "array",
                "items": {"type": "string", "enum": ["email", "social", "intranet"]},
                "minItems" : 1,
                "description": (
                    "Channels to produce. If the request does not explicitly restrict "
                    "channels, include all three. If it explicitly limits scope (e.g. "
                    "'email only'), include only what's stated."
                ),
            },
            "deadline": {
                "type": ["string", "null"],
                "description": "Deadline as stated in the request, or null if none given.",
            },
            "tone": {
                "type": "string",
                "description": "Tone for the copy, stated or conservatively inferred.",
            },
            "constraints": {
                "type": ["string", "null"],
                "description": "Legal, budget, or scope exclusions, or null if none stated.",
            },
            "missing_fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional fields the request did not explicitly state, even though "
                    "submit_brief still succeeded (e.g. deadline was inferred or absent, "
                    "tone was inferred rather than stated, channels defaulted to all "
                    "three). This is a completeness record, not a blocker."
                ),
            },
        },
        "required": [
            "campaign_name",
            "objective",
            "audience",
            "key_message",
            "channels",
            "deadline",
            "tone",
            "constraints",
            "missing_fields",
        ],
    },
}

ASK_CLARIFYING_QUESTIONS_TOOL = {
    "name": "ask_clarifying_questions",
    "description": (
        "Call this instead of submit_brief when the request is missing objective, "
        "audience, or key_message and none can be safely inferred from context. Ask "
        "2 to 4 specific questions. This stops the pipeline for this run."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 4,
                "description": (
                    "Each question should name what's missing and why it matters for "
                    "producing the content (not just 'what is the audience?')."
                ),
            },
        },
        "required": ["questions"],
    },
}

SUBMIT_REVIEW_TOOL = {
    "name": "submit_review",
    "description": (
        "Submit your brand and compliance review verdict for this single draft. Call "
        "this exactly once, after checking the draft against every rule in the brand "
        "guide you were given."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["pass", "fail"],
                "description": (
                    "'fail' if the draft violates any brand guide rule, or does not "
                    "state the brief's key_message in substance. 'pass' otherwise."
                ),
            },
            "key_message_present": {
                "type": "boolean",
                "description": (
                    "True only if the draft communicates the brief's key_message in "
                    "substance (verbatim or near-verbatim wording is fine; a different "
                    "point altogether is not)."
                ),
            },
            "violations": {
                "type": "array",
                "description": (
                    "One entry per rule broken. Empty list if verdict is 'pass'."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "rule": {
                            "type": "string",
                            "description": "Which brand guide rule this breaks.",
                        },
                        "quote": {
                            "type": "string",
                            "description": (
                                "The exact offending text, copied verbatim from the "
                                "draft — not a paraphrase or summary."
                            ),
                        },
                        "suggested_fix": {
                            "type": "string",
                            "description": "A specific, actionable fix for this violation.",
                        },
                    },
                    "required": ["rule", "quote", "suggested_fix"],
                },
            },
            "notes": {
                "type": ["string", "null"],
                "description": (
                    "Anything worth flagging that isn't a hard violation (e.g. "
                    "borderline reading level), or null."
                ),
            },
        },
        "required": ["verdict", "key_message_present", "violations", "notes"],
    },
}
