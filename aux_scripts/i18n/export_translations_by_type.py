"""
Export translationatom contents for translationgists of a given type
into a text file, sorted alphabetically.

For every TranslationGist row with type == <gist_type> the script collects
content of all non-deleted TranslationAtom rows belonging to that gist for
each requested locale, and writes them, one per line, into a file named
i18n_<gist_type_lower>_<shortcuts>.txt (or a given path).

Usage:
    python export_translations_by_type.py <config_uri> <gist_type> [output_path] [locale_shortcuts]
    e.g.:
    python export_translations_by_type.py ../development.ini Service
    python export_translations_by_type.py ../development.ini Service ./service-en.txt
    python export_translations_by_type.py ../development.ini Service ./service-en-ru.txt en:ru
    python export_translations_by_type.py ../development.ini Service ./service-hy.txt hy

locale_shortcuts is a colon-separated list of Locale.shortcut values
(e.g. "en:ru", "hy"). With one shortcut each line is just the phrase;
with several, each line is "<phrase1> : <phrase2> : ..." — phrases
are translation atoms of the same gist for the respective locales.
The default output path includes the shortcuts joined with '-'.
"""

import os
import sys
from collections import defaultdict

from pyramid.paster import get_appsettings, setup_logging
from pyramid.scripts.common import parse_vars
from sqlalchemy import engine_from_config

from lingvodoc.models import DBSession, Locale, TranslationAtom, TranslationGist


DEFAULT_LOCALE_SHORTCUT = 'en'


def main(argv=sys.argv):
    if len(argv) < 3:
        print('usage: %s <config_uri> <gist_type> [output_path] [locale_shortcuts]'
              % os.path.basename(argv[0]))
        sys.exit(1)

    config_uri = argv[1]
    gist_type = argv[2]
    shortcut_arg = argv[4] if len(argv) > 4 else DEFAULT_LOCALE_SHORTCUT
    shortcuts = [s.strip() for s in shortcut_arg.split(':') if s.strip()]
    if not shortcuts:
        print('error: empty locale shortcuts')
        sys.exit(1)

    output_path = argv[3] if len(argv) > 3 else os.path.join(
        os.path.dirname(__file__),
        'i18n_%s_%s.txt' % (gist_type.lower().replace(' ', '_'),
                            '-'.join(shortcuts)))

    setup_logging(config_uri)
    settings = get_appsettings(config_uri, options=parse_vars(argv[5:]))
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)

    shortcut_to_locale_id = dict(
        DBSession.query(Locale.shortcut, Locale.id)
        .filter(Locale.shortcut.in_(shortcuts))
        .all())

    missing = [s for s in shortcuts if s not in shortcut_to_locale_id]
    if missing:
        print('error: no Locale found for shortcut(s): %s'
              % ', '.join(repr(s) for s in missing))
        sys.exit(1)

    locale_ids = [shortcut_to_locale_id[s] for s in shortcuts]

    rows = (
        DBSession.query(
            TranslationGist.client_id,
            TranslationGist.object_id,
            TranslationAtom.locale_id,
            TranslationAtom.content)
        .join(
            TranslationAtom,
            (TranslationAtom.parent_client_id == TranslationGist.client_id) &
            (TranslationAtom.parent_object_id == TranslationGist.object_id))
        .filter(
            TranslationGist.type == gist_type,
            TranslationGist.marked_for_deletion == False,  # noqa: E712
            TranslationAtom.marked_for_deletion == False,  # noqa: E712
            TranslationAtom.locale_id.in_(locale_ids),
        )
        .all()
    )

    # gist_id -> locale_id -> set of contents
    by_gist = defaultdict(lambda: defaultdict(set))
    for gist_cid, gist_oid, loc_id, content in rows:
        if content:
            by_gist[(gist_cid, gist_oid)][loc_id].add(content)

    lines = set()
    for gist_locales in by_gist.values():
        phrase_lists = []
        for loc_id in locale_ids:
            phrases = sorted(gist_locales.get(loc_id, ()))
            if not phrases:
                phrases = ['']
            phrase_lists.append(phrases)
        # cartesian product in case a gist has several atoms per locale
        for combo in _product(phrase_lists):
            line = ' : '.join(combo).strip()
            if line:
                lines.add(line)

    with open(output_path, 'w', encoding='utf-8') as f:
        for line in sorted(lines):
            f.write(line + '\n')

    print('Gist type: %r, locales: %s'
          % (gist_type,
             ', '.join('%s(id=%d)' % (s, shortcut_to_locale_id[s])
                       for s in shortcuts)))
    print('Wrote %d lines to %s' % (len(lines), output_path))


def _product(lists):
    if not lists:
        yield ()
        return
    for item in lists[0]:
        for rest in _product(lists[1:]):
            yield (item,) + rest


if __name__ == '__main__':
    main()
