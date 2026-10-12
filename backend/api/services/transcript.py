"""Map the institution name printed on a transcript to a community college we have articulation data for."""

import re
import unicodedata

from api.services.articulation import list_colleges

_IGNORED_WORDS = {'college', 'community', 'junior', 'of', 'the', 'district', 'official', 'transcript'}


def _tokens(name):
    ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    words = {'mount' if w == 'mt' else w for w in re.findall(r'[a-z]+', ascii_name)}
    return words - _IGNORED_WORDS


def match_college(institution):
    """Exact token match first, then a single college whose name is contained in the header text; else None."""
    wanted = _tokens(institution or '')
    if not wanted:
        return None
    colleges = [(c, _tokens(c['name'])) for c in list_colleges()]
    exact = [c for c, tokens in colleges if tokens == wanted]
    if len(exact) == 1:
        return exact[0]
    contained = [c for c, tokens in colleges if tokens <= wanted]
    if len(contained) == 1:
        return contained[0]
    return None
