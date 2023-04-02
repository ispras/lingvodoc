
__author__ = 'student'


import json
import os
import re

try:
    PAGE_SIZE = os.sysconf('SC_PAGE_SIZE')
except:
    pass


from sqlalchemy import cast
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column
from sqlalchemy.sql.expression import Executable, ClauseElement, _literal_as_text, FromClause


from lingvodoc.models import DBSession, SLBigInteger


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

    # Allow EXPLAIN for INSERT / UPDATE / DELETE, turn off compiler flags that would otherwise start
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


class values(FromClause):
    """
    PostgreSQL VALUES for selecting from and for using in CTE.

    See StackOverflow answer https://stackoverflow.com/a/18900176/2016856,
    mostly copied from https://github.com/sqlalchemy/sqlalchemy/wiki/PGValues.
    """

    named_with_column = True

    def __init__(self, columns, value_list, alias = None):

        self._column_args = columns
        self.list = value_list

        self.name = alias
        self.alias_name = alias

    def _populate_column_collection(self):

        for c in self._column_args:
            c._make_proxy(self)

    @property
    def _from_objects(self):
        return [self]


@compiles(values)
def compile_values(element, compiler, asfrom = False, **kwargs):

    columns = element.columns

    if len(columns) > 1:

        v = "VALUES %s" % ", ".join(
            "(%s)"
            % ", ".join(
                compiler.render_literal_value(elem, column.type)
                for elem, column in zip(tup, columns)
            )
            for tup in element.list
        )

    else:

        column = list(columns)[0]

        v = "VALUES %s" % ", ".join(
            "(%s)"
            % compiler.render_literal_value(value, column.type)
            for value in element.list
        )

    if asfrom:

        alias = (
            element.alias_name or '_alias_')

        v = "(%s) AS %s (%s)" % (
            v,
            alias,
            (", ".join(c.name for c in element.columns)),
        )

    return v


def values_query(
    value_list,
    column_info_list,
    alias = None):

    column_list = []

    try:
        iter(column_info_list)

    except TypeError:
        column_info_list = [column_info_list]

    for index, column_info in enumerate(column_info_list):

        try:

            column_list.append(
                column(*column_info))

        except TypeError:

            column_list.append(
                column(f'_column_{index}_', column_info))

    values_clause = (

        values(
            column_list,
            value_list,
            alias or '_values_'))

    return (

        DBSession.query(
            *values_clause.columns))


def ids_to_id_query(ids, explicit_cast = False):

    id_values = (

        values(
            [column('client_id', SLBigInteger), column('object_id', SLBigInteger)],
            ids,
            'ids'))

    c_client_id = id_values.c.client_id
    c_object_id = id_values.c.object_id
    
    if explicit_cast:

        c_client_id = cast(c_client_id, SLBigInteger).label('client_id')
        c_object_id = cast(c_object_id, SLBigInteger).label('object_id')

    return (

        DBSession.query(
            c_client_id, c_object_id))

def ids_to_id_cte(ids, **kwargs):

    return ids_to_id_query(ids).cte(**kwargs)

def ids_to_id_cte_query(ids):

    return DBSession.query(ids_to_id_cte(ids))


def render_statement(statement):
    """
    Renders SQLAlchemy query as a string with any parameters substituted, including proper handling of any JSONB
    dictionary parameter literals.

    Based on, among other things, on https://stackoverflow.com/a/9898141/2016856.
    """

    dialect = (
        statement.bind.dialect if statement.bind else
        postgresql.dialect())

    compiler = statement._compiler(dialect)

    class Compiler(type(compiler)):

        def render_literal_value(self, value, type, *args, **kwargs):

            if (isinstance(value, dict) and
                isinstance(type, postgresql.JSONB)):

                return repr(json.dumps(value)) + ' :: jsonb'

            return super().render_literal_value(value, type, *args, **kwargs)

    return Compiler(dialect, statement).process(statement, literal_binds = True)


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

