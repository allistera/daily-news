#!/usr/bin/env python3
"""Render the newsletter template with Jinja2 and send it via Resend.

Install (managed by uv):
    uv add resend jinja2

Run:
    RESEND_API_KEY=re_xxx uv run send_email.py
"""

import os
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).parent
TEMPLATE_NAME = "template.html.jinja"


def render_html(context: dict) -> str:
    """Render the email template to an HTML string."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "jinja"]),
    )
    template = env.get_template(TEMPLATE_NAME)
    return template.render(**context)


def main() -> None:
    resend.api_key = os.environ["RESEND_API_KEY"]

    # Sample data — replace with your real newsletter content.
    context = {
        "newsletter": {
            "title": "Daily News Briefing",
            "date": "June 25, 2026",
        },
        "profile": {
            "name": "Allister",
        },
        "articles": [
            {
                "sourceName": "The Verge",
                "relevanceScore": 9.2,
                "link": "https://example.com/article-1",
                "title": "A breakthrough in AI-powered news curation",
                "summary": "Researchers unveiled a system that ranks stories by "
                "personal relevance, cutting reading time in half.",
                "relevanceExplanation": "Directly relevant to the Daily News "
                "personalization engine you're building.",
            },
            {
                "sourceName": "BBC News",
                "relevanceScore": 6.1,
                "link": "https://example.com/article-2",
                "title": "Email deliverability trends for 2026",
                "summary": "A look at how DMARC enforcement is reshaping "
                "transactional email for senders large and small.",
                "relevanceExplanation": "Useful context for sending newsletters "
                "reliably via Resend.",
            },
        ],
    }

    html = render_html(context)

    params: resend.Emails.SendParams = {
        "from": "hey@infinitywave.online",
        "to": ["allistera@gmail.com"],
        "subject": context["newsletter"]["title"],
        "html": html,
    }

    email = resend.Emails.send(params)
    print(email)


if __name__ == "__main__":
    main()
