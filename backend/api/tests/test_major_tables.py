
from django.test import TestCase


class MajorTableTests(TestCase):

    def test_alias_and_absorption_tables_do_not_overlap(self):
        """A name is either a renamed major (alias) or a distinct grouped major (absorption), never both."""
        from api.constants.majors import MAJOR_ABSORPTIONS, MAJOR_ALIASES
        aliases = {a for names in MAJOR_ALIASES.values() for a in names}
        children = {c for names in MAJOR_ABSORPTIONS.values() for c in names}
        self.assertEqual(aliases & children, set())

    def test_alias_maps_to_single_canonical(self):
        from api.constants.majors import MAJOR_ALIASES
        seen = {}
        for canonical, names in MAJOR_ALIASES.items():
            for name in names:
                self.assertNotIn(name, seen, f'{name!r} aliased to both {seen.get(name)!r} and {canonical!r}')
                seen[name] = canonical
