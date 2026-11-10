"""
Import translations into translationatom table.

Reads a txt file named i18n_<gist_type>_<locale_shortcut>.txt or
i18n_<gist_type>_<source_locale>_<target_locale>.txt where each
line has the form:
    <source phrase> : <target phrase>

gist_type and locale_shortcut(s) are parsed from the input file name:
gist_type is capitalized (e.g. 'service' -> 'Service') and must be one word,
locale shortcuts are lowercased (e.g. 'HY' -> 'hy').

When two locale shortcuts are provided (separated by _), the first is used
as SOURCE_LOCALE and the second as TARGET_LOCALE. When one is provided,
SOURCE_LOCALE defaults to English (locale_id == 2) and the provided shortcut
is TARGET_LOCALE.

For each line the script looks up a TranslationAtom row with the source locale
and content == <source phrase>. If found, a new TranslationAtom with
the target locale and content == <target phrase> is created via
create_gists_with_atoms, attached to the same translation gist
(parent_client_id / parent_object_id) with the given gist_type.

With the optional 'force' argument:
- when no source atom matching the source phrase exists, a new TranslationGist
  is created together with both the source and target-locale atoms;
- when a target-locale translation already exists, it is updated with the new
  content instead of being skipped.

Usage:
    python import_translations_by_type.py <config_uri> <i18n_txt_path> [force]
    e.g.:
    python import_translations_by_type.py ../development.ini ./i18n_service_hy.txt
    python import_translations_by_type.py ../development.ini ./i18n_service_en_hy.txt
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

FILENAME_RE = re.compile(r'^i18n_(?P<gist_type>[A-Za-z]+)_(?P<locales>[A-Za-z]{2,3}(?:_[A-Za-z]{2,3})?)\.txt$')


def parse_filename(path):
    """Extract (gist_type, source_locale, target_locale) from a file name.

    i18n_service_hy.txt -> ('Service', 'en', 'hy')
    i18n_service_en_hy.txt -> ('Service', 'en', 'hy')
    """
    name = os.path.basename(path)
    m = FILENAME_RE.match(name)
    if m is None:
        return None
    gist_type = m.group('gist_type').capitalize()
    locales = m.group('locales').split('_')

    if len(locales) == 1:
        source_locale = 'en'
        target_locale = locales[0].lower()
    else:
        source_locale = locales[0].lower()
        target_locale = locales[1].lower()

    return gist_type, source_locale, target_locale


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
        print(f'Cannot parse gist_type and locales from {i18n_path!r}; '
              'expected i18n_<gist_type>_<locale>.txt or i18n_<gist_type>_<source_locale>_<target_locale>.txt')
        sys.exit(1)
    gist_type, source_locale, target_locale = parsed
    print(f'Parsed from filename: gist_type={gist_type!r} source_locale={source_locale!r} target_locale={target_locale!r} force={force}')

    setup_logging(config_uri)
    settings = get_appsettings(config_uri, options=parse_vars(positional[2:]))
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)

    source_loc = DBSession.query(Locale).filter(Locale.shortcut == source_locale).first()
    if source_loc is None:
        print(f'No locale found with shortcut {source_locale!r}')
        sys.exit(1)
    source_locale_id = source_loc.id
    print(f'Source locale: shortcut={source_locale!r} id={source_locale_id}')

    target_loc = DBSession.query(Locale).filter(Locale.shortcut == target_locale).first()
    if target_loc is None:
        print(f'No locale found with shortcut {target_locale!r}')
        sys.exit(1)
    target_locale_id = target_loc.id
    print(f'Target locale: shortcut={target_locale!r} id={target_locale_id}')

    created = 0
    created_forced = 0
    updated = 0
    skipped_no_match = []
    skipped_exists = []
    errors = []

    for lineno, src, dst in parse_i18n_file(i18n_path):
        atoms = (
            DBSession.query(TranslationAtom)
            .filter(
                TranslationAtom.content == src,
                TranslationAtom.locale_id == source_locale_id,
                TranslationAtom.parent_client_id == TranslationGist.client_id,
                TranslationAtom.parent_object_id == TranslationGist.object_id,
                TranslationGist.type == gist_type
            )
            .all()
        )

        if not atoms:
            if not force:
                skipped_no_match.append((lineno, src))
                continue
            try:
                create_gists_with_atoms(
                    [
                        {'locale_id': source_locale_id, 'content': src},
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

        for atom in atoms:
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
                if force:
                    try:
                        existing.content = dst
                        updated += 1
                    except Exception as e:  # noqa: BLE001
                        errors.append((lineno, src, str(e)))
                else:
                    skipped_exists.append((lineno, src))
            else:
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
    print(f'Skipped (no source phrase match): {len(skipped_no_match)}')
    for lineno, src in skipped_no_match:
        print(f'  line {lineno}: {src!r}')
    print(f'Errors: {len(errors)}')
    for lineno, src, msg in errors:
        print(f'  line {lineno}: {src!r} -> {msg}')
    print(f'Created: {created}')
    print(f'Created (forced, new gist): {created_forced}')
    print(f'Updated: {updated}')


if __name__ == '__main__':
    main()
