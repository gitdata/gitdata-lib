"""Terminal display-width-aware text fitting."""

from wcwidth import wcswidth

from gitdata.cli import terminal_text


ELLIPSIS = '...'


def display_width(value):
    """Return the number of terminal cells used by rendered text."""
    text = terminal_text(value)
    width = wcswidth(text)
    return len(text) if width < 0 else width


def _prefix(text, width):
    prefix = ''
    for character in text:
        candidate = prefix + character
        if display_width(candidate) > width:
            break
        prefix = candidate
    return prefix


def fit_text(value, width):
    """Render and truncate text to at most ``width`` terminal cells."""
    width = max(0, width)
    text = terminal_text(value)
    if display_width(text) <= width:
        return text
    if width <= len(ELLIPSIS):
        return _prefix(text, width)
    return _prefix(text, width - len(ELLIPSIS)) + ELLIPSIS


def align_text(value, width, right=False):
    """Fit rendered text and pad it to an exact terminal-cell width."""
    text = fit_text(value, width)
    padding = ' ' * max(0, width - display_width(text))
    return padding + text if right else text + padding
