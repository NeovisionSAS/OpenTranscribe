"""Rejoin the word pieces a cloud ASR provider spaces apart.

Speech-to-text engines emit French elisions and hyphenated compounds as separate tokens
(``c`` + ``'est``, ``jusque`` + ``-là``) and most providers build segment text by joining
tokens with a space, so stored text read « c 'est » / « jusque -là » (54 + 7 such gaps in one
20-minute French file through pyannote.ai). The UI, search and exports all read segment text.

The rule: no space before a token opening on an apostrophe (``'`` or ``’``) or a hyphen that is
followed by a letter. A spaced dash (« bon - alors »), a hyphen before a digit (« -5 ») and a
quoted word whose closing mark matches its opening one (« 'n' ») keep their space.
"""

import re

_SPLIT = re.compile(r"(?<=\w) +(?=(['’]|-)([^\W\d_]\S*))")
_TRAILING = ".,;:!?…»\")"


def _join(match: re.Match[str]) -> str:
    mark, rest = match.group(1), match.group(2)
    quoted = mark != "-" and rest.rstrip(_TRAILING).endswith(mark)
    return match.group(0) if quoted else ""


def join_split_tokens(text: str) -> str:
    """``text`` with each elision / hyphen piece joined back to the word before it."""
    return _SPLIT.sub(_join, text)
