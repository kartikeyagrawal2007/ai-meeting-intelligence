EXTRACTION_PROMPT = """\
Analyze this meeting transcript and extract the following with high precision.
Return ONLY valid JSON, no explanation, no markdown, no code blocks.

{{
  "action_items": [
    {{
      "action": "specific task to be done",
      "owner": "person responsible or 'unassigned'",
      "deadline": "deadline if mentioned or null",
      "source_quote": "exact words from transcript"
    }}
  ],
  "decisions": [
    {{
      "decision": "what was decided",
      "decided_by": ["speaker labels"],
      "source_quote": "exact words from transcript"
    }}
  ],
  "follow_ups": [
    {{
      "topic": "topic deferred or needing more input",
      "reason": "why it was deferred",
      "owner": "person responsible or null"
    }}
  ],
  "open_questions": [
    {{
      "question": "unresolved question",
      "asked_by": "speaker label"
    }}
  ]
}}

Rules:
- Only extract action items where someone clearly committed to doing something
- Do NOT extract vague statements like 'we should look into this'
- Decisions must be something the group agreed on, not just discussed
- Be precise — less but accurate is better than more but wrong
- If nothing fits a category, return an empty array for it

Transcript:
{transcript_text}"""
