"""French elisions and hyphenated words spaced apart by token joining are rejoined; real spacing stays."""

import pytest

from app.services.asr.types import ASRResult, ASRSegment
from app.utils.token_spacing import join_split_tokens


@pytest.mark.parametrize(
    ("spaced", "joined"),
    [
        ("c 'est bon", "c'est bon"),
        ("qu 'il mesure", "qu'il mesure"),
        ("jusque -là.", "jusque-là."),
        ("aujourd 'hui", "aujourd'hui"),
        ("est -ce que", "est-ce que"),
        ("a -t -il dit", "a-t-il dit"),
        ("c 'est -à -dire", "c'est-à-dire"),
        ("L ’IA, j 'utilisais,", "L’IA, j'utilisais,"),
        ("génère -moi le pré -traitement", "génère-moi le pré-traitement"),
        ("bon - alors on y va", "bon - alors on y va"),  # a spoken dash keeps its spaces
        ("il fait moins -5 degrés", "il fait moins -5 degrés"),  # a sign is no word piece
        ("rock 'n' roll", "rock 'n' roll"),  # a quoted word keeps its space
        ("il a dit 'oui', puis", "il a dit 'oui', puis"),
    ],
)
def test_split_tokens_rejoin_and_real_spacing_stays(spaced, joined):
    assert join_split_tokens(spaced) == joined


def test_every_provider_result_holds_joined_text():
    result = ASRResult(segments=[ASRSegment(text="qui t 'envoie jusque -là", start=0.0, end=1.0)], language="fr")
    assert result.segments[0].text == "qui t'envoie jusque-là"
