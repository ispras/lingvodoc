
__author__ = 'student'


import os

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

