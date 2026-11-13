"""Text normalisation helpers shared by date parsing and id generation."""

from __future__ import annotations

# Folding both dotted and dotless i to plain "i" makes "KASIM", "Kasım" and "kasim"
# compare equal; Python's own str.lower() turns "İ" into "i" + combining dot, and
# "I" into "i" rather than Turkish "ı", so it cannot be used on its own.
_TURKISH_TO_ASCII = str.maketrans(
    {
        "ç": "c",
        "Ç": "c",
        "ğ": "g",
        "Ğ": "g",
        "ı": "i",
        "I": "i",
        "İ": "i",
        "ö": "o",
        "Ö": "o",
        "ş": "s",
        "Ş": "s",
        "ü": "u",
        "Ü": "u",
        "â": "a",
        "Â": "a",
        "î": "i",
        "Î": "i",
        "û": "u",
        "Û": "u",
    }
)

# Sites use hyphen, en dash, em dash and the minus sign interchangeably in ranges.
_DASHES = str.maketrans({c: "-" for c in "‐‑‒–—―−"})


def fold_turkish(text: str) -> str:
    """Return ``text`` lower-cased with Turkish letters reduced to ASCII."""
    return text.translate(_TURKISH_TO_ASCII).lower()


def normalize_dashes(text: str) -> str:
    return text.translate(_DASHES)
