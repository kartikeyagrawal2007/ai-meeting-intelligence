def render_recap(intelligence: dict, meeting_title: str = "Meeting") -> str:
    lines = [f"# Meeting Recap: {meeting_title}\n"]

    action_items = intelligence.get("action_items", [])
    if action_items:
        lines.append("## Action Items")
        for item in action_items:
            deadline = f" — due {item['deadline']}" if item.get("deadline") else ""
            owner = item.get("owner", "Unassigned")
            lines.append(f"- [ ] **{owner}**: {item['action']}{deadline}")
            if item.get("source_quote"):
                lines.append(f"  > *\"{item['source_quote']}\"*")
    else:
        lines.append("## Action Items\n- None identified")

    decisions = intelligence.get("decisions", [])
    if decisions:
        lines.append("\n## Decisions Made")
        for d in decisions:
            lines.append(f"- {d['decision']}")
            if d.get("source_quote"):
                lines.append(f"  > *\"{d['source_quote']}\"*")
    else:
        lines.append("\n## Decisions Made\n- None identified")

    follow_ups = intelligence.get("follow_ups", [])
    if follow_ups:
        lines.append("\n## Follow-ups")
        for f in follow_ups:
            owner = f" *(owner: {f['owner']})*" if f.get("owner") else ""
            lines.append(f"- {f['topic']}{owner}")
            if f.get("reason"):
                lines.append(f"  Reason: {f['reason']}")
    else:
        lines.append("\n## Follow-ups\n- None identified")

    open_questions = intelligence.get("open_questions", [])
    if open_questions:
        lines.append("\n## Open Questions")
        for q in open_questions:
            lines.append(f"- {q['question']} *(asked by {q['asked_by']})*")
    else:
        lines.append("\n## Open Questions\n- None identified")

    return "\n".join(lines)
