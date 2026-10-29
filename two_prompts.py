
ZERO_SHOT_PROMPT = """
CLASSIFY each support ticket into exactly one of these allowed categories:
billing, delivery, technical, fraud.

Return a JSON-only reply in exactly this form:
{"category": "...", "reason": "..."}

The category must be one of the four allowed categories.
The reason must briefly explain the classification.
Do not include Markdown, code fences, or text outside the JSON object.
"""

FEW_SHOT_PROMPT = """
CLASSIFY each support ticket into exactly one of these allowed categories:
billing, delivery, technical, fraud.

Return a JSON-only reply in exactly this form:
{"category": "...", "reason": "..."}

The category must be one of the four allowed categories.
The reason must briefly explain the classification.
Do not include Markdown, code fences, or text outside the JSON object.

EXAMPLES:
Ticket: "I was charged twice for my order."
{"category": "billing", "reason": "The customer reports a duplicate charge."}

Ticket: "My order has not arrived."
{"category": "delivery", "reason": "The customer reports a delayed delivery."}

Ticket: "The app crashes when I open it."
{"category": "technical", "reason": "The customer reports an application crash."}

Ticket: "I see an unauthorized transaction on my account."
{"category": "fraud", "reason": "The customer reports an unauthorized transaction."}
"""