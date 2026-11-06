"""
Export English (locale_id == 2) translationatom contents for translationgists
of a given type into a text file, sorted alphabetically.

For every TranslationGist row with type == <gist_type> the script collects
content of all non-deleted TranslationAtom rows with locale_id == 2 belonging
to that gist, sorts them alphabetically (deduplicated) and writes them, one
per line, into a file named i18n_<gist_type_lower>.txt (or a given path).

Usage:
    python export_translations_by_type.py <config_uri> <gist_type> [output_path]
    e.g.:
    python export_translations_by_type.py ../development.ini Service
    python export_translations_by_type.py ../development.ini Service ./service-en.txt
"""

import os
import sys

from pyramid.paster import get_appsettings, setup_logging
from pyramid.scripts.common import parse_vars
from sqlalchemy import engine_from_config

from lingvodoc.models import DBSession, TranslationAtom, TranslationGist


DEFAULT_LOCALE_ID = 2


def main(argv=sys.argv):
    if len(argv) < 3:
        print('usage: %s <config_uri> <gist_type> [output_path] [locale_id]'
              % os.path.basename(argv[0]))
        sys.exit(1)

    config_uri = argv[1]
    gist_type = argv[2]
    output_path = argv[3] if len(argv) > 3 else os.path.join(
        os.path.dirname(__file__),
        'i18n_%s.txt' % gist_type.lower().replace(' ', '_'))
    locale_id = int(argv[4]) if len(argv) > 4 else DEFAULT_LOCALE_ID

    setup_logging(config_uri)
    settings = get_appsettings(config_uri, options=parse_vars(argv[5:]))
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)

    rows = (
        DBSession.query(TranslationAtom.content)
        .join(
            TranslationGist,
            (TranslationGist.client_id == TranslationAtom.parent_client_id) &
            (TranslationGist.object_id == TranslationAtom.parent_object_id))
        .filter(
            TranslationGist.type == gist_type,
            TranslationGist.marked_for_deletion == False,  # noqa: E712
            TranslationAtom.marked_for_deletion == False,  # noqa: E712
            TranslationAtom.locale_id == locale_id,
        )
        .all()
    )

    contents = sorted({row[0] for row in rows if row[0]})

    with open(output_path, 'w', encoding='utf-8') as f:
        for content in contents:
            f.write(content + '\n')

    print(f'Gist type: {gist_type!r}, locale_id: {locale_id}')
    print(f'Wrote {len(contents)} lines to {output_path}')


if __name__ == '__main__':
    main()
