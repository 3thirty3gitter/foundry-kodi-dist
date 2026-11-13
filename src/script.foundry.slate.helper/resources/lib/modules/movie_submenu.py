"""Explicit Movies submenu identity; no provider or URL inference."""
import re

LABELS = (
    'Trending', 'Trending Recent', 'Popular', 'Popular Today', 'Premieres',
    'Latest Releases', 'Most Watched', 'Most Favorited', 'Top 10 Box Office',
    'Blockbusters', 'In Theaters', 'Up Coming', 'Oscar Winners',
    'Genres',
    'Providers',
    'Languages',
    'Years',
    'Decades',
    'Certifications',
    'Because You Watched...',
    'Watched',
    'Recently Watched',
    'In Progress',
)


def canonical_label(*values):
    """Accept only a complete approved label or terminal breadcrumb segment."""
    approved = {label.casefold(): label for label in LABELS}
    for value in values:
        if not isinstance(value, str):
            continue
        terminal = re.split(r'\s+(?:/|>)\s+', value.strip())[-1].strip()
        matched = approved.get(terminal.casefold())
        if matched:
            return matched
    return ''


def movie_context(section, items, content, candidate, verified=False):
    """Publish only proven Movies context; preserve an empty retained page."""
    label = canonical_label(candidate)
    if section != 'Movies' or not label:
        return ''
    if items:
        if not all(isinstance(item, dict) and item.get('type') == 'movie' for item in items):
            return ''
    elif content != 'movies' and not verified:
        return ''
    return label
