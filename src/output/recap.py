def render_recap(intelligence: dict, meeting_title: str = "Meeting") -> str:
    lines = [f"# Meeting Recap: {meeting_title}\n"]

    # -----------------------------
    # Executive Summary
    # -----------------------------
    summary = intelligence.get("high_level_summary", "")
    if summary:
        lines.append("## Executive Summary")
        lines.append(f"{summary}\n")

    # -----------------------------
    # Action Items
    # -----------------------------
    action_items = intelligence.get("action_items", [])

    if action_items:
        lines.append("## Action Items")
        for item in action_items:
            deadline = f" — due {item['deadline']}" if item.get("deadline") else ""
            owner = item.get("owner", "Unassigned")
            confidence = item.get("confidence", None)

            if confidence is not None:
                if confidence >= 0.9:
                    badge = "🟢"
                elif confidence >= 0.7:
                    badge = "🟡"
                else:
                    badge = "🔴"
                conf_str = f" {badge} `{int(confidence * 100)}% confident`"
            else:
                conf_str = ""

            lines.append(f"- [ ] **{owner}**: {item['action']}{deadline}{conf_str}")

            if item.get("source_quote"):
                lines.append(f"  > *\"{item['source_quote']}\"*")
    else:
        lines.append("## Action Items\n- None identified")

    # -----------------------------
    # Decisions Made
    # -----------------------------
    decisions = intelligence.get("decisions", [])

    if decisions:
        lines.append("\n## Decisions Made")
        for d in decisions:
            confidence = d.get("confidence", None)

            if confidence is not None:
                if confidence >= 0.9:
                    badge = "🟢"
                elif confidence >= 0.7:
                    badge = "🟡"
                else:
                    badge = "🔴"
                conf_str = f" {badge} `{int(confidence * 100)}%`"
            else:
                conf_str = ""

            lines.append(f"- {d['decision']}{conf_str}")

            if d.get("source_quote"):
                lines.append(f"  > *\"{d['source_quote']}\"*")
    else:
        lines.append("\n## Decisions Made\n- None identified")

    # -----------------------------
    # Follow-ups
    # -----------------------------
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

    # -----------------------------
    # Open Questions
    # -----------------------------
    open_questions = intelligence.get("open_questions", [])

    if open_questions:
        lines.append("\n## Open Questions")
        for q in open_questions:
            lines.append(f"- {q['question']} *(asked by {q['asked_by']})*")
    else:
        lines.append("\n## Open Questions\n- None identified")

    # -----------------------------
    # Uncertain / needs review
    # -----------------------------
    uncertain_actions = intelligence.get("uncertain_action_items", [])
    uncertain_decisions = intelligence.get("uncertain_decisions", [])

    if uncertain_actions or uncertain_decisions:
        lines.append("\n## ⚠️ Needs Human Review")
        lines.append("*Low confidence — verify these manually*\n")

        for item in uncertain_actions:
            confidence = item.get("confidence", 0)
            owner = item.get("owner", "Unassigned")
            deadline = f" — due {item['deadline']}" if item.get("deadline") else ""
            lines.append(
                f"- [ ] **{owner}**: {item['action']}{deadline} "
                f"🔴 `{int(confidence * 100)}% confident`"
            )
            if item.get("source_quote"):
                lines.append(f"  > *\"{item['source_quote']}\"*")

        for item in uncertain_decisions:
            confidence = item.get("confidence", 0)
            lines.append(
                f"- {item['decision']} "
                f"🔴 `{int(confidence * 100)}%`"
            )
            if item.get("source_quote"):
                lines.append(f"  > *\"{item['source_quote']}\"*")

    return "\n".join(lines)