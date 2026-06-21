"""backend/app/agents/visualbranding/naming.py

Shared helpers for keeping LLM-assigned category/archetype names stable
across runs.

Fixed, enumerated categories (e.g. font classification's "Serif" /
"Sans-serif" / "Monospace" / "Display") don't need this — their names are
hardcoded in the node's own prompt, so they can't drift. This matters for
*freely LLM-named* clusters instead (font/image/video archetypes): without
guidance, the LLM might call the same underlying cluster "Geometric Sans"
this run and "Clean Geometric Sans-Serif" next run, which would make every
re-run look like a brand-new archetype appeared (noisy alerts, broken
trend-tracking) even though nothing about the competitive set changed.
"""


def naming_stability_instruction(previous_names: list[str]) -> str:
    """A prompt fragment instructing the LLM to reuse an existing name for an
    equivalent cluster, only inventing a new one when a cluster is genuinely
    different from everything seen last run. Returns "" when there's no
    prior run to compare against (first-ever run)."""
    if not previous_names:
        return ""
    names = ", ".join(f'"{n}"' for n in previous_names)
    return (
        f" These names were used in the previous analysis: {names}. If a cluster you're "
        "naming now is essentially the same concept as one of these, reuse that exact name "
        "rather than inventing a new one — only pick a new name if this cluster is "
        "meaningfully different from all of them."
    )
