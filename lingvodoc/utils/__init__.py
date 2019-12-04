
__author__ = 'student'


import os
import re

try:
    PAGE_SIZE = os.sysconf('SC_PAGE_SIZE')
except:
    pass


from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import Executable, ClauseElement, _literal_as_text


class explain(Executable, ClauseElement):
    """
    PostgreSQL EXPLAIN [ANALYZE] for queries, example:

        query = DBSession.query(...)

        log.debug(''.join(
            '\n' + row[0] for row in
            session.execute(explain(query)).fetchall()))

    See also in lingvodoc/scripts/save_dictionary.py.

    Mostly copied from
    https://github.com/sqlalchemy/sqlalchemy/wiki/Explain.
    """

    def __init__(
        self,
        statement,
        analyze = False):

        self.statement = _literal_as_text(statement)
        self.analyze = analyze

        # Apparently helps with INSERT statements.

        self.inline = getattr(
            statement, 'inline', None)


@compiles(explain, 'postgresql')
def pg_explain(element, compiler, **kwargs):
    """
    Compilation of EXPLAIN [ANALYZE] query for PostgreSQL backend.
    """

    text = "EXPLAIN "

    if element.analyze:
        text += "ANALYZE "

    text += compiler.process(element.statement, **kwargs)

    # Allow EXPLAIN for INSERT / UPDATE / DELETE, turn off  compiler flags that would otherwise start
    # treating this like INSERT / UPDATE / DELETE (gets confused with RETURNING or autocloses cursor
    # which we don't want).

    compiler.isinsert = False
    compiler.isupdate = False
    compiler.isdelete = False

    return text


@compiles(explain)
def default_explain(element, compiler, **kwargs):
    """
    Default compilation handler, e.g. for str(explain(query)).
    """

    return pg_explain(element, compiler, **kwargs)


def explain_analyze(statement):
    """
    Helper wrapper for EXPLAIN ANALYZE.
    """

    return explain(statement, analyze = True)


def get_resident_memory():
    """
    Returns curren resident memory size of the process.

    See
    https://stackoverflow.com/questions/938733/total-memory-used-by-python-process,
    http://fa.bianp.net/blog/2013/different-ways-to-get-memory-consumption-or-lessons-learned-from-memory_profiler/,
    https://github.com/giampaolo/psutil/blob/386a9288fc854626c96eb32d1a5bdd3f7f260b12/psutil/_pslinux.py#L1733.
    """

    with open('/proc/self/statm', 'rb') as statm_file:
        return int(statm_file.readline().split()[1]) * PAGE_SIZE


#: Standard list of languages for grouping, see lingvodoc-react,
#   src/pages/Home/components/LangsNav/index.js, languageIdList.
#
# NOTE: if the languageIdList in lingvodoc-react changes, this list must also be updated accordingly.
# 
standard_language_id_list = [
  (1574, 116655), # Altai
  (33, 88), # Altai language
  (252, 40), # Altai-Kizhi dialect
  (1076, 4), # Altaic family
  (1574, 269058), # Azeric
  (1068, 5), # Baltic-Finnish
  (500, 121), # Bashkir
  (1076, 22), # Buryat language
  (33, 90), # Chalkan dialect
  (216, 8), # Chulym
  (1574, 272286), # Chuvash
  (295, 8), # Chuvash language
  (1100, 4), # Crimean Tatar
  (1105, 28), # Dolgan language
  (508, 49), # Enets
  (508, 39), # Erzya
  (633, 23), # Evenki
  (1552, 1252), # Finnish
  (508, 46), # Hungarian
  (1733, 13468), # Izhor
  (1501, 42640), # Japonic languages
  (1501, 42646), # Japonic proper
  (1311, 23), # Japono-Koreanic subfamily
  (1076, 10), # Kalmyk language
  (1552, 652), # Kamas
  (508, 37), # Karelian
  (500, 124), # Kazakh
  (500, 123), # Khakas
  (1574, 269111), # Khamnigan Evenki
  (508, 44), # Khanty
  (508, 42), # Komi
  (1076, 119), # Korean
  (1574, 99299), # Kur-Urmi Evenki
  (1574, 274491), # Manchu branch
  (508, 45), # Mansi
  (508, 41), # Mari
  (508, 40), # Moksha
  (1076, 7), # Mongolic languages
  (633, 17), # Nanii
  (1209, 24), # Negidal
  (1209, 20), # Negidal language
  (508, 48), # Nenets
  (508, 50), # Nganasan
  (1088, 612), # Noghai
  (1311, 41), # Northern Mongolic
  (1574, 203685), # Oghuz
  (1479, 599), # Oroch language
  (996, 1069), # Orok
  (1401, 11742), # Qara-Nogay
  (1574, 272495), # Qarachaj-Balkar language
  (998, 5), # Qumyq language
  (1574, 116715), # Qypčaq branch
  (508, 38), # Saami
  (508, 47), # Samoyed
  (1372, 10768), # Seber-Tatar
  (508, 51), # Selkup
  (1557, 6), # Shor
  (1574, 268977), # Solon language
  (500, 122), # Tatar
  (65, 2), # Telengit dialect
  (1251, 6), # Tofa
  (1574, 116679), # Tuba language
  (633, 16), # Tungus-Manchu languages
  (1002, 12), # Tungusic
  (1068, 9), # Turkic languages
  (1574, 269088), # Turkish
  (1574, 203688), # Turkmenic
  (1550, 3373), # Tuva
  (508, 43), # Udmurt
  (643, 4), # Udyhe language
  (33, 89), # Ujguri language
  (633, 22), # Ulcha
  (508, 36), # Uralic
  (840, 6), # Uzbek
  (1632, 6), # Veps
  (1372, 11240), # Volga Tatar
  (2108, 13), # Votic
  (1574, 274494), # Xibe
  (678, 9), # Yakut
]

standard_language_id_set = set(standard_language_id_list)


def sanitize_worksheet_name(
    name,
    max_width = 31):
    """
    Sanitizes XLSX worksheet name.

    See https://support.office.com/en-us/article/Rename-a-worksheet-3F1F7148-EE83-404D-8EF0-9FF99FBAD1F9.
    """

    if name.startswith('\''):
        name = name[1:]

    name = re.sub(
        r'\0|\*|/|:|\?|\[|\\|\]', '', name)

    name = name[:max_width]

    if name.endswith('\''):
        name = name[:-1]

    if name == 'History':
        name = 'History_'

    return name

