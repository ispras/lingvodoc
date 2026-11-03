"""
Import Armenian translations into translationatom table.

Reads ../lingvodoc-react/src/api/i18n_hy.txt, where each line has the form:
    <english phrase> : <armenian phrase>

For each line the script looks up a TranslationAtom row with locale_id == 2
and content == <english phrase>. If found, a new TranslationAtom with
locale_id == 6 and content == <armenian phrase> is created via
create_gists_with_atoms, attached to the same translation gist
(parent_client_id / parent_object_id) with gist_type == 'Service'.

Usage:
    python -m lingvodoc.scripts.import_hy_translations <config_uri>
    e.g.:
    python -m lingvodoc.scripts.import_hy_translations development.ini
"""

import os
import sys

import transaction
from pyramid.paster import get_appsettings, setup_logging
from pyramid.scripts.common import parse_vars
from sqlalchemy import engine_from_config

from ..models import DBSession, TranslationAtom, TranslationGist, Client
from ..utils.creation import create_gists_with_atoms


SOURCE_LOCALE_ID = 2   # English
TARGET_LOCALE_ID = 6   # Armenian
GIST_TYPE = 'Service'
DEFAULT_CLIENT_ID = 1  # admin / server client used for service gists


def parse_i18n_file(path):
    """Yield (english, armenian) tuples for each well-formed line."""
    with open(path, encoding='utf-8') as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip('\n').strip()
            if not line:
                continue
            if ':' not in line:
                continue
            en, _, hy = line.partition(':')
            en = en.strip()
            hy = hy.strip()
            if not en or not hy:
                continue
            yield lineno, en, hy


def main(argv=sys.argv):
    if len(argv) < 3:
        print('usage: %s <config_uri> <i18n_hy.txt path> [client_id] [target_locale_id]'
              % os.path.basename(argv[0]))
        sys.exit(1)

    config_uri = argv[1]
    i18n_path = argv[2]
    client_id = int(argv[3]) if len(argv) > 3 else DEFAULT_CLIENT_ID
    target_locale_id = int(argv[4]) if len(argv) > 4 else TARGET_LOCALE_ID

    setup_logging(config_uri)
    settings = get_appsettings(config_uri, options=parse_vars(argv[4:]))
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)

    created = 0
    skipped_no_match = []
    skipped_exists = []
    errors = []

    for lineno, en, hy in parse_i18n_file(i18n_path):
        atom = (
            DBSession.query(TranslationAtom)
            .filter(
                TranslationAtom.locale_id == SOURCE_LOCALE_ID,
                TranslationAtom.content == en,
            )
            .first()
        )
        if atom is None:
            skipped_no_match.append((lineno, en))
            continue

        gist_id = (atom.parent_client_id, atom.parent_object_id)

        # Skip if an Armenian atom already exists for this gist
        existing = (
            DBSession.query(TranslationAtom)
            .filter(
                TranslationAtom.parent_client_id == atom.parent_client_id,
                TranslationAtom.parent_object_id == atom.parent_object_id,
                TranslationAtom.locale_id == target_locale_id,
            )
            .first()
        )
        if existing is not None:
            skipped_exists.append((lineno, en))
            continue

        try:
            create_gists_with_atoms(
                [{'locale_id': target_locale_id, 'content': hy}],
                list(gist_id),
                [client_id, None],
                gist_type=GIST_TYPE,
                DBSession=DBSession,
            )
            created += 1
        except Exception as e:  # noqa: BLE001
            errors.append((lineno, en, str(e)))

    transaction.commit()

    print(f'Created: {created}')
    print(f'Skipped (no English match): {len(skipped_no_match)}')
    for lineno, en in skipped_no_match:
        print(f'  line {lineno}: {en!r}')
    print(f'Skipped (Armenian already exists): {len(skipped_exists)}')
    for lineno, en in skipped_exists:
        print(f'  line {lineno}: {en!r}')
    print(f'Errors: {len(errors)}')
    for lineno, en, msg in errors:
        print(f'  line {lineno}: {en!r} -> {msg}')


if __name__ == '__main__':
    main()
