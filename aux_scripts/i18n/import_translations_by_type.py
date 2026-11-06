"""
Import translations into translationatom table.

Reads a txt file named i18n_<gist_type>_<locale_shortcut>.txt where each
line has the form:
    <english phrase> : <target phrase>

gist_type and locale_shortcut are parsed from the input file name:
gist_type is capitalized (e.g. 'service' -> 'Service'),
locale_shortcut is lowercased (e.g. 'HY' -> 'hy').

For each line the script looks up a TranslationAtom row with locale_id == 2
and content == <english phrase>. If found, a new TranslationAtom with
the target locale and content == <target phrase> is created via
create_gists_with_atoms, attached to the same translation gist
(parent_client_id / parent_object_id) with the given gist_type.

With the optional 'force' argument, when no English atom matching the
source phrase exists, a new TranslationGist is created together with both
the English atom and the target-locale atom.

Usage:
    python import_translations_by_type.py <config_uri> <i18n_txt_path> [force]
    e.g.:
    python import_translations_by_type.py ../development.ini ./i18n_service_hy.txt
    python import_translations_by_type.py ../development.ini ./i18n_service_hy.txt force
"""

import os
import re
import sys

import transaction
from pyramid.paster import get_appsettings, setup_logging
from pyramid.paster import bootstrap  # noqa: F401  (kept for parity with other scripts)
from pyramid.scripts.common import parse_vars
from sqlalchemy import engine_from_config

from lingvodoc.models import DBSession, TranslationGist, TranslationAtom, Locale
from lingvodoc.utils.creation import create_gists_with_atoms


SOURCE_LOCALE_ID = 2   # English
CLIENT_ID = 1

FILENAME_RE = re.compile(r'^i18n_(?P<gist_type>[A-Za-z_]+)_(?P<shortcut>[A-Za-z]{2,3})\.txt$')


def parse_filename(path):
    """Extract (gist_type, locale_shortcut) from a file name like
    i18n_service_hy.txt -> ('Service', 'hy')."""
    name = os.path.basename(path)
    m = FILENAME_RE.match(name)
    if m is None:
        return None
    gist_type = m.group('gist_type').replace('_', ' ').capitalize()
    shortcut = m.group('shortcut').lower()
    return gist_type, shortcut


def parse_i18n_file(path):
    """Yield (lineno, source, target) tuples for each well-formed line.

    A leading space on a line is significant: it is kept in the source
    phrase and also prepended to the target phrase."""
    with open(path, encoding='utf-8') as f:
        for lineno, raw in enumerate(f, 1):
            raw = raw.rstrip('\n')
            leading = raw[:len(raw) - len(raw.lstrip(' '))]
            line = raw.strip()
            if not line:
                continue
            if ':' not in line:
                continue
            src, _, dst = line.partition(':')
            src = leading + src.strip()
            dst = leading + dst.strip()
            if not src.strip() or not dst.strip():
                continue
            yield lineno, src, dst


def main(argv=sys.argv):
    positional = [a for a in argv[1:] if a != 'force']
    force = len(positional) != len(argv[1:])

    if len(positional) < 2:
        print('usage: %s <config_uri> <i18n_txt_path> [force]'
              % os.path.basename(argv[0]))
        sys.exit(1)

    config_uri = positional[0]
    i18n_path = positional[1]

    parsed = parse_filename(i18n_path)
    if parsed is None:
        print(f'Cannot parse gist_type and locale_shortcut from {i18n_path!r}; '
              'expected i18n_<gist_type>_<locale_shortcut>.txt')
        sys.exit(1)
    gist_type, shortcut = parsed
    print(f'Parsed from filename: gist_type={gist_type!r} locale_shortcut={shortcut!r} force={force}')

    setup_logging(config_uri)
    settings = get_appsettings(config_uri, options=parse_vars(positional[2:]))
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)

    locale = DBSession.query(Locale).filter(Locale.shortcut == shortcut).first()
    if locale is None:
        print(f'No locale found with shortcut {shortcut!r}')
        sys.exit(1)
    target_locale_id = locale.id
    print(f'Target locale: shortcut={shortcut!r} id={target_locale_id}')

    created = 0
    created_forced = 0
    skipped_no_match = []
    skipped_exists = []
    errors = []

    for lineno, src, dst in parse_i18n_file(i18n_path):
        atom = (
            DBSession.query(TranslationAtom)
            .filter(
                TranslationAtom.content == src,
                TranslationAtom.locale_id == SOURCE_LOCALE_ID,
                TranslationAtom.parent_client_id == TranslationGist.client_id,
                TranslationAtom.parent_object_id == TranslationGist.object_id,
                TranslationGist.type == gist_type
            )
            .first()
        )

        if atom is None:
            if not force:
                skipped_no_match.append((lineno, src))
                continue
            try:
                create_gists_with_atoms(
                    [
                        {'locale_id': SOURCE_LOCALE_ID, 'content': src},
                        {'locale_id': target_locale_id, 'content': dst},
                    ],
                    None,
                    [CLIENT_ID, None],
                    gist_type=gist_type,
                    DBSession=DBSession,
                )
                created_forced += 1
            except Exception as e:  # noqa: BLE001
                errors.append((lineno, src, str(e)))
            continue

        gist_id = (atom.parent_client_id, atom.parent_object_id)

        existing = (
            DBSession.query(TranslationAtom)
            .filter(
                TranslationAtom.parent_client_id == atom.parent_client_id,
                TranslationAtom.parent_object_id == atom.parent_object_id,
                TranslationAtom.locale_id == target_locale_id,
                TranslationAtom.parent_client_id == TranslationGist.client_id,
                TranslationAtom.parent_object_id == TranslationGist.object_id,
                TranslationGist.type == gist_type
            )
            .first()
        )
        if existing is not None:
            skipped_exists.append((lineno, src))
            continue

        try:
            create_gists_with_atoms(
                [{'locale_id': target_locale_id, 'content': dst}],
                list(gist_id),
                [CLIENT_ID, None],
                gist_type=gist_type,
                DBSession=DBSession,
            )
            created += 1
        except Exception as e:  # noqa: BLE001
            errors.append((lineno, src, str(e)))

    transaction.commit()

    print(f'Skipped (target already exists): {len(skipped_exists)}')
    for lineno, src in skipped_exists:
        print(f'  line {lineno}: {src!r}')
    print(f'Skipped (no English match): {len(skipped_no_match)}')
    for lineno, src in skipped_no_match:
        print(f'  line {lineno}: {src!r}')
    print(f'Errors: {len(errors)}')
    for lineno, src, msg in errors:
        print(f'  line {lineno}: {src!r} -> {msg}')
    print(f'Created: {created}')
    print(f'Created (forced, new gist): {created_forced}')


if __name__ == '__main__':
    main()
