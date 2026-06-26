"""backend/app/agents/visualbranding/alerts.py

Shared diffing helpers that compare a node's freshly-computed analysis
against its previous run (read back via
visualbranding_repository.get_latest_analysis) and produce short,
human-readable change descriptions.

Every interpretation node calls these and returns whatever fragments come
back via VisualBrandingState["alert_fragments"] (an operator.add reducer —
see state.py / graph.py). A separate fan-in node joins every node's
fragments into one AlertAnalysis once they've all run. If nothing
meaningful changed, a node contributes no fragments and the next run's
AlertAnalysis.alerts stays None.

"Meaningful" is deliberately narrow: a previously-empty column getting its
first-ever content, or a category/archetype's company membership actually
changing — not float rounding noise in `percentage`, and not a category
disappearing-then-reappearing with identical companies (no diff there).
"""

from typing import Any, Protocol


class _NamedGroup(Protocol):
    naming: str
    companies: list[str]


def _as_company_set(group: dict | Any) -> set[str]:
    if isinstance(group, dict):
        return set(group.get("companies") or [])
    return set(getattr(group, "companies", None) or [])


def _as_name(group: dict | Any, name_field: str = "naming") -> str:
    """Most node outputs name their groups via `.naming` (DimensionCategory,
    archetypes), but ColorSpectrum (colors.py) uses `.type` instead — pass
    name_field="type" for that one."""
    if isinstance(group, dict):
        return group.get(name_field, "")
    return getattr(group, name_field, "")


def diff_named_groups(
    label: str,
    old: list[dict] | None,
    new: list[_NamedGroup],
    name_field: str = "naming",
) -> list[str]:
    """Compare two lists of {<name_field>, companies} groups (DimensionCategory
    buckets or archetype clusters — same shape). Returns one fragment per
    new/changed/disappeared group; empty list if nothing meaningful changed."""
    old = old or []
    old_by_name = {_as_name(g, name_field): _as_company_set(g) for g in old}
    new_by_name = {_as_name(g, name_field): _as_company_set(g) for g in new}

    fragments: list[str] = []
    for name, companies in new_by_name.items():
        if name not in old_by_name:
            if not old_by_name:
                continue  # first-ever run for this dimension — not a "change", just initial data
            fragments.append(f'{label}: new category "{name}" ({", ".join(sorted(companies))})')
            continue
        added = companies - old_by_name[name]
        removed = old_by_name[name] - companies
        if added:
            fragments.append(f'{label}: "{name}" gained {", ".join(sorted(added))}')
        if removed:
            fragments.append(f'{label}: "{name}" lost {", ".join(sorted(removed))}')
    for name in old_by_name:
        if name not in new_by_name:
            fragments.append(f'{label}: category "{name}" disappeared')
    return fragments


def diff_company_lists(label: str, old: list[str] | None, new: list[str]) -> str | None:
    """Compare two flat company lists (e.g. colors' warm/cold/neutral)."""
    if old is None:
        return None  # first-ever run
    old_set, new_set = set(old), set(new)
    added, removed = new_set - old_set, old_set - new_set
    if not added and not removed:
        return None
    parts = []
    if added:
        parts.append(f"added {', '.join(sorted(added))}")
    if removed:
        parts.append(f"removed {', '.join(sorted(removed))}")
    return f"{label}: " + ", ".join(parts)
