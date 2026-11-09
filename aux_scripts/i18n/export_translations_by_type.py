"""
Export translationatom contents for translationgists of a given type
into a text file, sorted alphabetically.

For every TranslationGist row with type == <gist_type> the script collects
content of all non-deleted TranslationAtom rows belonging to that gist for
each requested locale, and writes them, one per line, into the given file.

Usage:
    python export_translations_by_type.py <config_uri> <output_path> [xlsx]

Output path must be named like:
    i18n_<gist_type>_<locale_shortcut1>[_<locale_shortcut2>_...].txt

gist_type and locale shortcuts are parsed from that filename. With one
shortcut each line is just the phrase; with several, each line is
"<phrase1> : <phrase2> : ..." — translation atoms of the same gist for
the respective locales.

If the optional third argument is 'xlsx', results are written as an .xlsx
workbook instead of plain text. The sheet is named after gist_type and has
columns: gist_id, one column per locale shortcut, and a boolean column
'Подтверждено' initialized to FALSE.
"""

import os
import re
import sys
from collections import defaultdict

from pyramid.paster import get_appsettings, setup_logging
from pyramid.scripts.common import parse_vars
from sqlalchemy import engine_from_config

from lingvodoc.models import DBSession, Locale, TranslationAtom, TranslationGist


OUTPUT_NAME_RE = re.compile(r'^i18n_(?P<gist>[A-Za-z]+)_(?P<locales>[A-Za-z_]+)\.txt$')


def _parse_output_name(output_path):
    name = os.path.basename(output_path)
    match = OUTPUT_NAME_RE.match(name)
    if not match:
        return None, None
    gist = match.group('gist').strip().capitalize()
    locale_parts = [p.strip().lower()
                    for p in match.group('locales').split('_')
                    if p.strip()]
    return gist or None, locale_parts or None


def main(argv=sys.argv):
    if len(argv) < 3:
        print('usage: %s <config_uri> <output_path>'
              % os.path.basename(argv[0]))
        sys.exit(1)

    config_uri = argv[1]
    output_path = argv[2]

    gist_type, shortcuts = _parse_output_name(output_path)
    if not gist_type or not shortcuts:
        print('error: output_path must be named '
              'i18n_<gist_type>_<locale1>[_<locale2>...].txt')
        sys.exit(1)

    use_xlsx = len(argv) > 3 and argv[3].lower() == 'xlsx'
    if use_xlsx:
        root, ext = os.path.splitext(output_path)
        if ext.lower() == '.txt':
            output_path = root + '.xlsx'

    setup_logging(config_uri)
    settings = get_appsettings(config_uri, options=parse_vars(argv[4:]))
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
    rows_out = []
    for gist_id, gist_locales in by_gist.items():
        phrase_lists = []
        for loc_id in locale_ids:
            phrases = sorted(gist_locales.get(loc_id, ()))
            if not phrases:
                phrases = ['']
            phrase_lists.append(phrases)
        # cartesian product in case a gist has several atoms per locale
        for combo in _product(phrase_lists):
            rows_out.append((gist_id, list(combo)))

    if use_xlsx:
        try:
            from openpyxl import Workbook
        except ImportError:
            print('error: openpyxl is required for xlsx output')
            sys.exit(1)

        wb = Workbook()
        ws = wb.active
        ws.title = gist_type
        headers = ['gist_id'] + shortcuts + ['Подтверждено']
        ws.append(headers)
        for gist_id, combo in rows_out:
            ws.append(['%s,%s' % gist_id] + combo + [False])
        wb.save(output_path)
    else:
        lines = set()
        for gist_id, combo in rows_out:
            line = '%s : %s' % (gist_id, ' : '.join(combo))
            if line.strip():
                lines.add(line)
        with open(output_path, 'w', encoding='utf-8') as f:
            for line in sorted(lines):
                f.write(line + '\n')

    print('Gist type: %r, locales: %s'
          % (gist_type,
             ', '.join('%s(id=%d)' % (s, shortcut_to_locale_id[s])
                       for s in shortcuts)))
    print('Wrote %d rows to %s' % (len(rows_out), output_path))


def _product(lists):
    if not lists:
        yield ()
        return
    for item in lists[0]:
        for rest in _product(lists[1:]):
            yield (item,) + rest


if __name__ == '__main__':
    main()
