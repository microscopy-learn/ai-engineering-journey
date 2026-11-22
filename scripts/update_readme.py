"""Rebuild the generated sections of README.md from the weekly logs in logs/.

Each log file logs/week-NN.md starts with a small front-matter block:

    ---
    week: 3
    phase: 1
    start: 2026-12-06
    hours: 13
    theme: NumPy and pandas
    built: First EDA notebook on Canadian open data
    paper: Attention Is All You Need | https://arxiv.org/abs/1706.03762
    ---

Only `week` and `phase` are required. Run locally with: python scripts/update_readme.py
GitHub Actions runs it automatically whenever a file in logs/ changes.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
README = ROOT / "README.md"
TOTAL_WEEKS = 52

# Phase number -> (name, first week, last week, project), matching the 12-month roadmap.
PHASES = {
    0: ("Setup and orientation", 1, 2, "Project template, this log, profile"),
    1: ("Python, maths and data foundations", 3, 10, "Public-data analysis"),
    2: ("Classical machine learning", 11, 18, "Taxonomy auto-tagger (API + Docker)"),
    3: ("Deep learning and transformers", 19, 28, "GPT from scratch"),
    4: ("LLM apps, RAG and GraphRAG", 29, 36, "Flagship 1: knowledge assistant"),
    5: ("Agents, tool use, MCP and evals", 37, 44, "Flagship 2: data-steward agent"),
    6: ("Production, LLMOps and fine-tuning", 45, 50, "Hardened deployment + text-to-SPARQL model"),
    7: ("Portfolio and job readiness", 51, 52, "Case studies, open-source PR"),
}


def parse_front_matter(text: str) -> dict:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not match:
        return {}
    data = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, value = line.split(":", 1)
            data[key.strip().lower()] = value.strip().strip('"').strip("'")
    return data


def number(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def load_logs() -> list[dict]:
    entries = []
    for path in sorted(LOGS.glob("week-*.md")):
        meta = parse_front_matter(path.read_text(encoding="utf-8"))
        week, phase = number(meta.get("week")), number(meta.get("phase"))
        if week is None or phase is None:
            print(f"Skipping {path.name}: needs 'week' and 'phase' in front matter")
            continue
        meta.update(week=int(week), phase=int(phase), file=f"logs/{path.name}")
        meta["hours_num"] = number(meta.get("hours"))
        entries.append(meta)
    return sorted(entries, key=lambda e: e["week"])


def bar(done: int, total: int, width: int = 20) -> str:
    filled = round(width * done / total) if total else 0
    return "█" * filled + "░" * (width - filled)


def render_progress(entries: list[dict]) -> str:
    latest = entries[-1] if entries else None
    current_phase = latest["phase"] if latest else 0
    current_week = latest["week"] if latest else 0
    hours = sum(e["hours_num"] or 0 for e in entries)
    lines = []
    if latest:
        name = PHASES.get(current_phase, ("?",))[0]
        lines += [
            f"**Now:** week {current_week} of {TOTAL_WEEKS} · Phase {current_phase}: {name}"
            + (f" · this week: {latest['theme']}" if latest.get("theme") else ""),
            "",
            f"`{bar(current_week, TOTAL_WEEKS)}` {round(100 * current_week / TOTAL_WEEKS)}%"
            f" · {len(entries)} week{'s' if len(entries) != 1 else ''} logged"
            + (f" · {hours:g} hours so far" if hours else ""),
            "",
        ]
    lines += [
        "| Phase | Weeks | Focus | Project | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for num, (name, first, last, project) in PHASES.items():
        if not latest or num > current_phase:
            status = "⬜"
        elif num < current_phase:
            status = "✅ Done"
        else:
            span = last - first + 1
            into = min(max(current_week - first + 1, 1), span)
            status = f"⏳ Week {into} of {span}"
        weeks = f"{first}–{last}" if first != last else str(first)
        lines.append(f"| {num} | {weeks} | {name} | {project} | {status} |")
    return "\n".join(lines)


def render_log(entries: list[dict]) -> str:
    lines = [
        "| Week | Start | Phase | Theme | Built | Hours | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for e in reversed(entries):
        hours = f"{e['hours_num']:g}" if e["hours_num"] is not None else "–"
        lines.append(
            f"| {e['week']} | {e.get('start', '–') or '–'} | {e['phase']} | {e.get('theme', '') or '–'} "
            f"| {e.get('built', '') or '–'} | {hours} | [week {e['week']:02d}]({e['file']}) |"
        )
    return "\n".join(lines)


def render_papers(entries: list[dict]) -> str:
    rows = []
    for e in entries:
        paper = e.get("paper")
        if not paper:
            continue
        title, _, url = (part.strip() for part in paper.partition("|"))
        cell = f"[{title}]({url})" if url else title
        rows.append(f"| {e['week']} | {cell} | [notes]({e['file']}) |")
    if not rows:
        return "_None yet. Add a `paper:` line to a weekly log and it appears here._"
    return "\n".join(["| Week | Paper | Summary |", "| --- | --- | --- |", *rows])


def replace_block(text: str, name: str, body: str) -> str:
    pattern = re.compile(rf"(<!-- {name}:START -->).*?(<!-- {name}:END -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"README is missing the {name} markers")
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(2)}", text)


def main() -> None:
    entries = load_logs()
    text = README.read_text(encoding="utf-8")
    updated = replace_block(text, "PROGRESS", render_progress(entries))
    updated = replace_block(updated, "LOG", render_log(entries))
    updated = replace_block(updated, "PAPERS", render_papers(entries))
    if updated != text:
        README.write_text(updated, encoding="utf-8")
        print(f"README updated from {len(entries)} weekly logs")
    else:
        print("README already up to date")


if __name__ == "__main__":
    main()
