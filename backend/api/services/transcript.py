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


SEASON_ALIASES = {
    'winter': 'Winter', 'wi': 'Winter', 'win': 'Winter',
    'spring': 'Spring', 'sp': 'Spring', 'spr': 'Spring',
    'summer': 'Summer', 'su': 'Summer', 'sum': 'Summer',
    'fall': 'Fall', 'fa': 'Fall', 'autumn': 'Fall',
}


def normalize_term(term):
    """Coerce whatever the model wrote ("fall 2023", "SU 2024") to "<Season> <Year>", or '' if unrecognized."""
    words = re.findall(r'[A-Za-z]+|\d{4}', term or '')
    season = next((SEASON_ALIASES[w.lower()] for w in words if w.lower() in SEASON_ALIASES), None)
    year = next((w for w in words if w.isdigit()), None)
    return f'{season} {year}' if season and year else ''
