#!/usr/bin/env python3
"""Render the newsletter template with Jinja2 and send it via Resend.

Install (managed by uv):
    uv add resend jinja2

Run:
    RESEND_API_KEY=re_xxx PRODUCT_HUNT_TOKEN=... uv run send_email.py
"""

import os
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape

from sources.product_hunt import posts_for_email, previous_day
from sources.quote import quote_for_email
from sources.top_github_repos import repos_for_email

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "template.html.jinja"

# Newsletter sections in display order. ``accent`` selects the colour palette in
# the template ("purple" or "orange"); ``subtitle`` is the small caption shown
# beside the heading. Each ``fetch`` returns a list of item dicts with at least
# ``title``, ``url``, and ``description``, plus optional ``tagline`` and ``meta``.
SOURCES = [
    {
        "name": "Top GitHub Repos",
        "subtitle": "by stars gained",
        "accent": "purple",
        "fetch": repos_for_email,
    },
    {
        "name": "Top Product Hunt Launches",
        "subtitle": "by upvotes",
        "accent": "orange",
        "fetch": posts_for_email,
    },
]

# How many items to show per section.
ITEMS_PER_SECTION = 7

# Rotated daily (deterministically, by date) as the masthead epigraph.
QUOTES = [
    ("Simplicity is a prerequisite for reliability.", "Edsger W. Dijkstra"),
    (
        "Programs must be written for people to read, and only incidentally "
        "for machines to execute.",
        "Harold Abelson",
    ),
    ("Premature optimization is the root of all evil.", "Donald Knuth"),
    (
        "Any fool can write code that a computer can understand. Good "
        "programmers write code that humans can understand.",
        "Martin Fowler",
    ),
    ("The best way to predict the future is to invent it.", "Alan Kay"),
    ("Talk is cheap. Show me the code.", "Linus Torvalds"),
    ("Make it work, make it right, make it fast.", "Kent Beck"),
    ("First, solve the problem. Then, write the code.", "John Johnson"),
    ("Controlling complexity is the essence of computer programming.", "Brian Kernighan"),
    (
        "There are only two hard things in Computer Science: cache "
        "invalidation and naming things.",
        "Phil Karlton",
    ),
]


def _fallback_quote(day) -> tuple[str, str]:
    """Pick a built-in epigraph deterministically so a given date is stable."""
    quote, author = QUOTES[day.toordinal() % len(QUOTES)]
    return quote, author


def masthead_quote(day) -> tuple[str, str]:
    """The masthead epigraph: a live quote from API Ninjas, falling back to the
    built-in list when ``API_NINJAS_KEY`` is unset or the request fails."""
    try:
        live = quote_for_email()
    except Exception as exc:  # noqa: BLE001
        print(f"Falling back to a built-in quote: {exc}")
        live = None
    if live:
        return live["quote"], live["author"]
    return _fallback_quote(day)


def render_html(sections: list, quote: str, quote_author: str, date_line: str) -> str:
    """Render the email template to an HTML string.

    ``sections`` is an ordered list of section dicts, each with ``name``,
    ``subtitle``, ``accent``, and an ``items`` list. ``quote``/``quote_author``
    populate the masthead epigraph and ``date_line`` the dated byline.
    """
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "jinja"]),
    )
    template = env.get_template(TEMPLATE_NAME)
    return template.render(
        sections=sections,
        quote=quote,
        quote_author=quote_author,
        date_line=date_line,
    )


def main() -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise SystemExit("RESEND_API_KEY is not set; cannot send the newsletter.")
    resend.api_key = api_key

    # Pin the subject date and every source to a single instant so they can't
    # disagree if the run happens to cross UK midnight.
    day = previous_day()
    subject = f"Daily News Briefing — {day:%B} {day.day}, {day.year}"
    date_line = f"{day:%A}, {day:%B} {day.day}, {day.year}"
    quote, quote_author = masthead_quote(day)

    # Build each section. Don't let one source failing (e.g. a missing token)
    # block the whole newsletter.
    sections = []
    for source in SOURCES:
        try:
            items = source["fetch"](count=ITEMS_PER_SECTION, day=day)
        except Exception as exc:  # noqa: BLE001
            print(f"Skipping {source['name']} section: {exc}")
            continue
        # Drop empty sections so we never render a heading with nothing under it.
        if items:
            sections.append({**source, "items": items})

    # If every source failed or was empty, fail loudly so the scheduled run is
    # flagged rather than silently sending nothing.
    if not sections:
        raise SystemExit("No content from any source; not sending an empty newsletter.")

    params: resend.Emails.SendParams = {
        "from": "hey@infinitywave.online",
        "to": ["allisteraall@gmail.com"],
        "subject": subject,
        "html": render_html(sections, quote, quote_author, date_line),
    }

    try:
        email = resend.Emails.send(params)
    except Exception as exc:
        raise SystemExit(f"Failed to send newsletter via Resend: {exc}") from exc
    print(email)


if __name__ == "__main__":
    main()
