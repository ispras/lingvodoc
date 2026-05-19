import gc
import time
from time import time as now
from datetime import datetime, timezone
import pickle
import gzip
import sys
import os
import logging
import traceback
import requests
import psutil
import transaction
import tracemalloc
import objgraph
import uuid
from sqlalchemy import bindparam, func, text, tuple_, create_engine
from sqlalchemy.dialects.postgresql import insert
from itertools import zip_longest, starmap
from lingvodoc.schema.gql_holders import ResponseError
from lingvodoc.utils import ids_to_id_query
from psycopg2.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError, ResourceClosedError
from lingvodoc.queue.celery import celery
from lingvodoc.cache.caching import initialize_cache, TaskStatus

from lingvodoc.models import (
    DBSession,
    Client as dbClient,
    User as dbUser,
    Email as dbEmail,
    ENGLISH_LOCALE,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    Field as dbField,
    Entity as dbEntity,
    LexicalEntry as dbLexicalEntry,
    Dictionary as dbDictionary,
    Language as dbLanguage,
    DictionaryPerspectiveToField as dbDictionaryPerspectiveToField,
    DictionaryPerspective as dbDictionaryPerspective,
    PublishingEntity as dbPublishingEntity,
    ParserResult as dbParserResult,
    Parser as dbParser,
    BaseGroup as dbBaseGroup,
    ObjectTOC as dbObjectTOC,
    Group as dbGroup,
    UserToGroupAssociation as dbUserToGroup
)

from pdb import set_trace as A

log = logging.getLogger(__name__)
min_date = 1735689600.0  # 2025-01-01 00:00:00
none = ''
SUCCESS = True
FAILURE = None
MEM_EDGE = 80.0
CHUNK_SIZE = 1000

# Ordered models to create entries from independent ones
db_model_data = {
    # Translations
    'TranslationGist': dbTranslationGist,
    'TranslationAtom': dbTranslationAtom,

    # Language tree
    'Language': dbLanguage,
    'Dictionary': dbDictionary,
    'DictionaryPerspective': dbDictionaryPerspective,

    # Fields
    'Field': dbField,
    'DictionaryPerspectiveToField': dbDictionaryPerspectiveToField,

    # Lexical entries
    'LexicalEntry': dbLexicalEntry,
    'Entity': dbEntity,
    'PublishingEntity': dbPublishingEntity,

    # Parser results
    'Parser': dbParser,
    'ParserResult': dbParserResult
}

tables_num = len(db_model_data)

# Base groups without any relation to subjects
user_base_groups = [*range(1, 5), 9, 18, 30, 31, 32]
# Subjects for groups with relations
tables_for_roles = ['Language', 'Dictionary', 'DictionaryPerspective', 'TranslationGist', 'TranslationAtom']
tables_for_summary = ['warns', 'message', 'triumph', 'sync_point', 'Entity']

db_model_roles = {
    'User': (dbUser, ['id']),
    'Email': (dbEmail, ['email']),
    'Client': (dbClient, ['id']),
    'ObjectTOC': (dbObjectTOC, ['client_id', 'object_id']),
    'BaseGroup': (dbBaseGroup, ['id']),
    'Group': (dbGroup, ['id']),
    'UserToGroup': (dbUserToGroup, ['user_id', 'group_id'])
}

'''
# Tuple means relative: (his_dbModel, my_suffix, his_suffix)
db_tree = {
    dbParser: [],

    dbParserResult: [
        (dbParser, 'parser_', none)
    ],

    dbPublishingEntity: [],

    dbField: [
        (dbTranslationGist, 'translation_gist_', none),
        (dbTranslationGist, 'data_type_translation_gist_', none)
    ],

    dbEntity: [
        (dbPublishingEntity, none, none),
        # fields are created or updated with perspective itself
        # no need to collect them for every entity
        # but because of collisions sometimes we have to do this
        # (dbField, 'field_', none),
        (dbEntity, 'self_', none),
        (dbLexicalEntry, 'link_', none),
        (dbParserResult, none, 'entity_')
    ],

    dbLexicalEntry: [
        (dbEntity, none, 'parent_')
    ],

    dbDictionaryPerspectiveToField: [
        (dbDictionaryPerspective, 'link_', none),
        (dbDictionaryPerspectiveToField, 'self_', none),
        (dbField, 'field_', none)
    ],

    # Entry point
    dbDictionaryPerspective: [
        (dbDictionary, 'parent_', none),
        (dbTranslationGist, 'translation_gist_', none),
        (dbTranslationGist, 'state_translation_gist_', none),
        (dbDictionaryPerspectiveToField, none, 'parent_'),
        (dbLexicalEntry, none, 'parent_')
    ],

    dbDictionary: [
        (dbLanguage, 'parent_', none),
        (dbTranslationGist, 'translation_gist_', none),
        (dbTranslationGist, 'state_translation_gist_', none)
    ],

    dbLanguage: [
        (dbLanguage, 'parent_', none),
        (dbTranslationGist, 'translation_gist_', none)
    ],

    dbTranslationGist: [
        (dbTranslationAtom, none, 'parent_')
    ],

    dbTranslationAtom: []
}
'''

def check_memory():
    process = psutil.Process(os.getpid())
    print(f"Memory RSS: {process.memory_info().rss / 1024 / 1024:.2f} MB")


def summary(result):
    return {k: result[k] for k in result if k in tables_for_summary}


def key2str(*key):
    return ','.join([str(k) for k in key])


# For debugging
def report(epoch_times, no_caption=False):
    headers = list(epoch_times.keys())
    values = list(epoch_times.values())
    next_values = list(epoch_times.values())[1:]

    def cell(value, width):
        return f"{str(value)[:width]:<{width}}"

    def is_stamp(value):
        return isinstance(value, float)

    if not no_caption:
        caption = ' || '.join(starmap(cell, headers))
        print(f"\n{caption}", flush=True)

    for (_, w), v1, v2 in zip_longest(headers, values, next_values):
        v = datetime.fromtimestamp(v1) if is_stamp(v1) else v1
        sign = (
            '\n' if v2 is None else
            ' || ' if not is_stamp(v2) else
            ' == ' if v1 == v2 else ' << ' if v1 < v2 else ' >> ')
        print(cell(v, w), end=sign, flush=True)


def CheckPermissions(info, subject_id, action='edit'):
    # For now everyone with allowed_sync == True and any permission
    # for the perspective on remote host can add this perspective locally

    client_id = info.context.client_id
    user_id = dbClient.get_user_by_client_id(client_id).id

    return (
        user_id == 1 or
        action == 'create' or
        info.context.acl_check_if(action, 'perspective', subject_id))


def CheckPerspective(perspective_id):
    db_perspective = (
        DBSession
            .query(
                dbDictionaryPerspective)
            .filter_by(
                client_id=perspective_id[0],
                object_id=perspective_id[1],
                marked_for_deletion=False)
            .first())

    return (
        db_perspective is not None)


def as_dict(obj, exclude=None):
    try:
        obj_as_dict = obj._asdict()
    except AttributeError:
        obj_as_dict = {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}

    for key in (exclude or []):
        del obj_as_dict[key]

    return obj_as_dict


def as_dicts(obj, exclude=None):
    # If object is cte
    if type(obj) is not list:
        obj = DBSession.query(obj).all()

    return [as_dict(x, exclude) for x in obj]


def ListRoles(user_id, subject_ids, debug_flag=False):

    # Getting tree of entries for current user_id or subject_id
    try:
        if user_id is not None:
            filter_by_args = [dbGroup.base_group_id.in_(user_base_groups),
                              dbGroup.id == dbUserToGroup.group_id,
                              dbUserToGroup.user_id == user_id]

        elif subject_ids is not None:

            if len(subject_ids) == 0:
                return None

            filter_by_args = [tuple_(
                                dbGroup.subject_client_id,
                                dbGroup.subject_object_id
                              ).in_(ids_to_id_query(subject_ids))]
        else:
            raise NotImplementedError()

        Group = (
            DBSession
                .query(dbGroup)
                .filter(*filter_by_args)
                .distinct()
                .cte())

        if user_id:
            filter_user_to_group = filter_by_args
        else:
            filter_user_to_group = [dbUserToGroup.group_id == Group.c.id]

        UserToGroup = (
            DBSession
                .query(dbUserToGroup)
                .filter(*filter_user_to_group)
                .distinct()
                .cte())

        BaseGroup = (
            DBSession
                .query(dbBaseGroup)
                .filter(dbBaseGroup.id == Group.c.base_group_id)
                .distinct()
                .all())

        ObjectTOC = (
            DBSession
                .query(dbObjectTOC)
                .filter(dbObjectTOC.client_id == Group.c.subject_client_id,
                        dbObjectTOC.object_id == Group.c.subject_object_id)
                .distinct()
                .all()) if subject_ids else []

        User = (
            DBSession
                .query(dbUser)
                .filter(dbUser.id == UserToGroup.c.user_id)
                .distinct()
                .all()) if subject_ids else []

        Email = (
            DBSession
                .query(dbEmail)
                .filter(dbEmail.user_id == UserToGroup.c.user_id)
                .distinct()
                .all()) if subject_ids else []

        Client = (
            DBSession
                .query(dbClient)
                .filter(dbClient.id == Group.c.subject_client_id)
                .distinct()
                .all()) if subject_ids else []

        return {
            'User': as_dicts(User),
            'Email': as_dicts(Email, ['id']),
            'Client': as_dicts(Client),
            'ObjectTOC': as_dicts(ObjectTOC),
            'BaseGroup': as_dicts(BaseGroup),
            'Group': as_dicts(Group),
            'UserToGroup': as_dicts(UserToGroup)
        }

    # Debugging
    except Exception as e:
        if debug_flag:
            A()
        raise


def MergeRoles(roles_data, debug_flag=False):

    if roles_data is None:
        log.warning("\nNo any update for roles")
        return

    try:
        # Add new entries to database
        for table in db_model_roles:
            model, index = db_model_roles[table]
            for row in roles_data[table]:
                stmt = (
                    insert(model)
                        .values(**row)
                        .on_conflict_do_nothing(index_elements=index))
                DBSession.execute(stmt)
            DBSession.flush()
        transaction.commit()

        log.warning("\nAdded roles!")

    # Debugging
    except Exception as e:
        DBSession.rollback()
        transaction.abort()
        if debug_flag:
            A()
        raise

'''
# Cache of parameterized (q_changed, q_relatives) per (model, suff, action)
# combo — used by the legacy recursive get_db_objects path inside
# ListChanges. The expression tree (BindParameter, anonymous labels, etc.)
# is built ONCE per cache entry; only the param VALUES change per call via
# Query.params(). Eliminates the per-call query-construction churn that
# was responsible for the residual leak after the no-CTE refactor (the
# CTE-event-registry leak was the dominant pre-existing issue and is
# addressed separately by the no-CTE form below).
_fk_query_cache = {}

def _get_or_build_fk_query(model, suff, action):
    """Return (q_changed, q_relatives) for this (model, suff, action) combo.

    q_changed: filtered by FK + sync_point (param :_xal_sync_point)
    q_relatives: filtered by FK only

    Both expect params: _xal_cid, _xal_oid (and _xal_sync_point for q_changed).
    """
    key = (model.__name__, suff, action)
    if key in _fk_query_cache:
        return _fk_query_cache[key]

    cid_col = getattr(model, f'{suff}client_id')
    oid_col = getattr(model, f'{suff}object_id')

    base_filters = [
        cid_col == bindparam('_xal_cid'),
        oid_col == bindparam('_xal_oid'),
    ]
    if action == 'create':
        md_col = getattr(model, 'marked_for_deletion', None)
        if md_col is not None:
            base_filters.append(md_col == False)

    q_relatives = DBSession.query(model).filter(*base_filters)
    q_changed = q_relatives.filter(
        bindparam('_xal_sync_point') < func.date_part('EPOCH', model.updated_at))

    _fk_query_cache[key] = (q_changed, q_relatives)
    return q_changed, q_relatives
'''

def _walk_perspective_bulk(perspective_id, sync_point, action, local_result,
                           client_ids, subject_ids):
    """Bulk-query equivalent of the process_db_objects Python recursion.

    Replaces ~N per-FK-node queries (where N scales with entity count) with
    a fixed handful (~12-15) of bulk queries, including ~3 recursive CTEs
    for the parts that need recursive traversal (Language ancestors,
    DictionaryPerspectiveToField self-references, Entity self-+ link-
    references). The Entity recursive CTE additionally populates a temp
    table that subsequent stages (PublishingEntity, ParserResult) JOIN
    against, avoiding a Python<->SQL round-trip of all entity IDs.

    Mutates local_result, client_ids, subject_ids to mirror the side
    effects the original recursion would have produced.
    """
    # Convenience: a row passes the action filter if (action != 'create')
    # OR the row isn't marked deleted.
    md_str = "and marked_for_deletion = false" if action == 'create' else ""

    # Track every (cid, oid) we still need to fetch by table — accumulates
    # across stages.
    le_ids = set()           # LexicalEntry IDs (perspective + Entity link_)
    ent_ids = set()          # Entity IDs (for PE/PR lookup)
    parser_ids = set()       # Parser IDs
    field_ids = set()        # Field IDs
    gist_ids = set()         # TranslationGist IDs (collected from many sources)

    def _row_to_dict(r):
        """Convert ORM instance OR SQLA RowProxy to plain column-name -> value dict.

        ORM goes through TypeDecorator.process_result_value (EpochType
        converts datetime -> epoch float). RowProxy from raw text()
        bypasses that, returning datetime. To match the baseline output
        we manually apply the EpochType conversion for `created_at` /
        `updated_at` when we see a datetime on a RowProxy row.

        as_dict() in this file tries `r._asdict()` first, then falls
        back to `r.__dict__` filter. RowProxy in SQLA 1.2 has neither
        — `__dict__` access is interpreted as a column lookup. So
        for RowProxy we use `dict(r.items())` directly.
        """
        if hasattr(r, '_sa_instance_state'):
            # ORM instance — has the SQLA state attribute. EpochType
            # already applied; nothing to do.
            return {k: v for k, v in r.__dict__.items() if not k.startswith('_')}
        # RowProxy path. Apply EpochType-equivalent conversion for the
        # known epoch-encoded timestamp columns.
        d = dict(r.items())
        for k in ('created_at', 'updated_at'):
            v = d.get(k)
            if hasattr(v, 'timestamp'):  # datetime-like
                d[k] = v.replace(tzinfo=timezone.utc).timestamp()
        return d

    def _add(table, rows, also_subject=False):
        d = local_result.setdefault(table, {})
        for r in rows:
            client_ids.add(r.client_id)
            d[key2str(r.client_id, r.object_id)] = _row_to_dict(r)
            if also_subject:
                subject_ids.add((r.client_id, r.object_id))

    def _filter_changed(rows):
        """Filter rows by sync_point < extract(epoch from updated_at).

        updated_at may be a datetime or already a float epoch depending
        on the model's column type. Handle both.
        """
        sp = local_result['sync_point']
        out = []
        for r in rows:
            u = r.updated_at
            if u is None:
                continue
            if hasattr(u, 'timestamp'):
                ut = u.timestamp()
            else:
                ut = float(u)
            if ut > sp:
                out.append(r)
        return out

    def _id_pairs_in(model, attr_cid, attr_oid, ids):
        """Build a tuple_-IN filter for (cid, oid) pairs.

        Use ids_to_id_query() (SQL VALUES subquery) instead of a literal
        tuple list — postgres' parser hits stack-depth limits on
        IN ((1,2),(3,4),...) with thousands of tuples; VALUES handles it
        as a relation and scales cleanly.
        """
        ids_list = list(ids)
        if not ids_list:
            return False  # never match — caller should short-circuit
        return tuple_(getattr(model, attr_cid), getattr(model, attr_oid)).in_(
            ids_to_id_query(ids_list))

    # --- Stage 1: Perspective ---
    pcid, poid = perspective_id
    persp_filt = [
        dbDictionaryPerspective.client_id == pcid,
        dbDictionaryPerspective.object_id == poid,
    ]
    if action == 'create':
        persp_filt.append(dbDictionaryPerspective.marked_for_deletion == False)
    persp_rows = DBSession.query(dbDictionaryPerspective).filter(*persp_filt).all()
    if not persp_rows:
        return  # nothing to do
    _add('DictionaryPerspective', _filter_changed(persp_rows), also_subject=True)
    persp = persp_rows[0]
    for cid, oid in [
        (persp.translation_gist_client_id, persp.translation_gist_object_id),
        (persp.state_translation_gist_client_id, persp.state_translation_gist_object_id),
    ]:
        if cid is not None and oid is not None:
            gist_ids.add((cid, oid))

    # --- Stage 2: Dictionary ---
    dict_filt = [
        dbDictionary.client_id == persp.parent_client_id,
        dbDictionary.object_id == persp.parent_object_id,
    ]
    if action == 'create':
        dict_filt.append(dbDictionary.marked_for_deletion == False)
    dict_rows = DBSession.query(dbDictionary).filter(*dict_filt).all()
    _add('Dictionary', _filter_changed(dict_rows), also_subject=True)
    if dict_rows:
        d = dict_rows[0]
        for cid, oid in [
            (d.translation_gist_client_id, d.translation_gist_object_id),
            (d.state_translation_gist_client_id, d.state_translation_gist_object_id),
        ]:
            if cid is not None and oid is not None:
                gist_ids.add((cid, oid))
        lang_root = (d.parent_client_id, d.parent_object_id)
    else:
        lang_root = None

    # --- Stage 3: Language ancestors via recursive CTE ---
    if lang_root is not None and lang_root[0] is not None:
        lang_sql = text(f"""
            with recursive lang_walk as (
                select * from language
                 where client_id = :start_cid and object_id = :start_oid
                   {md_str}
                union
                select L.* from language L, lang_walk
                 where L.client_id = lang_walk.parent_client_id
                   and L.object_id = lang_walk.parent_object_id
                   {md_str.replace('marked_for_deletion', 'L.marked_for_deletion')}
            )
            select client_id, object_id from lang_walk
        """)
        lang_id_rows = DBSession.execute(
            lang_sql, {'start_cid': lang_root[0], 'start_oid': lang_root[1]}
        ).fetchall()
        lang_id_pairs = [(r.client_id, r.object_id) for r in lang_id_rows]
        if lang_id_pairs:
            lang_filt = [_id_pairs_in(dbLanguage, 'client_id', 'object_id', lang_id_pairs)]
            if action == 'create':
                lang_filt.append(dbLanguage.marked_for_deletion == False)
            lang_rows = DBSession.query(dbLanguage).filter(*lang_filt).all()
            _add('Language', _filter_changed(lang_rows), also_subject=True)
            for L in lang_rows:
                if L.translation_gist_client_id is not None:
                    gist_ids.add((L.translation_gist_client_id, L.translation_gist_object_id))

    # --- Stage 5: DictionaryPerspectiveToField (with self_ recursion) ---
    dpf_sql = text(f"""
        with recursive dpf_walk as (
            select * from dictionaryperspectivetofield
             where parent_client_id = :pcid and parent_object_id = :poid
               {md_str}
            union
            select D.* from dictionaryperspectivetofield D, dpf_walk
             where D.client_id = dpf_walk.self_client_id
               and D.object_id = dpf_walk.self_object_id
               {md_str.replace('marked_for_deletion', 'D.marked_for_deletion')}
        )
        select client_id, object_id from dpf_walk
    """)
    dpf_id_rows = DBSession.execute(dpf_sql, {'pcid': pcid, 'poid': poid}).fetchall()
    dpf_id_pairs = [(r.client_id, r.object_id) for r in dpf_id_rows]
    if dpf_id_pairs:
        dpf_filt = [_id_pairs_in(dbDictionaryPerspectiveToField, 'client_id', 'object_id', dpf_id_pairs)]
        if action == 'create':
            dpf_filt.append(dbDictionaryPerspectiveToField.marked_for_deletion == False)
        dpf_rows = DBSession.query(dbDictionaryPerspectiveToField).filter(*dpf_filt).all()
        _add('DictionaryPerspectiveToField', _filter_changed(dpf_rows))
        for D in dpf_rows:
            if D.field_client_id is not None:
                field_ids.add((D.field_client_id, D.field_object_id))

    # --- Stage 6: Field ---
    if field_ids:
        f_filt = [_id_pairs_in(dbField, 'client_id', 'object_id', list(field_ids))]
        if action == 'create':
            f_filt.append(dbField.marked_for_deletion == False)
        field_rows = DBSession.query(dbField).filter(*f_filt).all()
        _add('Field', _filter_changed(field_rows))
        for F in field_rows:
            for cid, oid in [
                (F.translation_gist_client_id, F.translation_gist_object_id),
                (F.data_type_translation_gist_client_id, F.data_type_translation_gist_object_id),
            ]:
                if cid is not None and oid is not None:
                    gist_ids.add((cid, oid))

    # --- Stage 7: LexicalEntry for the perspective ---
    le_filt = [
        dbLexicalEntry.parent_client_id == pcid,
        dbLexicalEntry.parent_object_id == poid,
    ]
    if action == 'create':
        le_filt.append(dbLexicalEntry.marked_for_deletion == False)
    le_rows = DBSession.query(dbLexicalEntry).filter(*le_filt).all()
    _add('LexicalEntry', _filter_changed(le_rows))
    for LE in le_rows:
        le_ids.add((LE.client_id, LE.object_id))

    # --- Stage 8: Entity (recursive: self_, link_) ---
    # Use a temp table to avoid round-tripping 69K IDs Python<->SQL.
    # The recursive CTE populates the temp table directly; then the
    # ORM query JOINs against it to hydrate full Entity rows.
    # PublishingEntity stage below also JOINs against the same temp table.
    ent_ids_table = None
    if le_ids:
        ent_ids_table = 'xal_ent_ids_' + uuid.uuid4().hex
        le_values = ', '.join(f"({c}::bigint, {o}::bigint)" for c, o in le_ids)
        # Postgres requires the recursive part of a recursive CTE to be a
        # single SELECT (or UNION of selects, but not mixed with the
        # non-recursive anchor). Combine self_ + link_ traversal into
        # one recursive arm with OR.
        # Anchor arm: optional "AND e.marked_for_deletion = false"
        e_md_anchor = (
            "and e.marked_for_deletion = false" if action == 'create' else "")
        # Recursive arm: optional "e.marked_for_deletion = false AND " prefix
        e_md_recur = (
            "e.marked_for_deletion = false and " if action == 'create' else "")
        # Store FULL entity rows in the temp table (not just IDs). Then we
        # can read them back with raw SELECT — skipping the JOIN AND skipping
        # ORM hydration. RowProxy._asdict() produces the same dict shape
        # as ORM as_dict() for standard column types.
        ent_sql = text(f"""
            create temporary table {ent_ids_table}
                on commit drop as
            with recursive
              le_seed (cid, oid) as (values {le_values}),
              ent_walk as (
                select e.* from entity e, le_seed
                 where e.parent_client_id = le_seed.cid
                   and e.parent_object_id = le_seed.oid
                   {e_md_anchor}
                union
                select e.* from entity e, ent_walk
                 where {e_md_recur}(
                         (e.client_id = ent_walk.self_client_id
                          and e.object_id = ent_walk.self_object_id)
                      or (e.parent_client_id = ent_walk.link_client_id
                          and e.parent_object_id = ent_walk.link_object_id)
                       )
              )
            select * from ent_walk
        """)
        DBSession.execute(ent_sql)

        # Pull only the link_'d LE IDs we don't yet have (small set):
        linked_le_rows = DBSession.execute(text(
            f"select distinct link_client_id, link_object_id "
            f"  from {ent_ids_table} "
            f" where link_client_id is not null")).fetchall()
        for r in linked_le_rows:
            le_ids.add((r.link_client_id, r.link_object_id))

        # Read all entity rows directly from the temp table as RowProxy —
        # no JOIN, no ORM hydration. _asdict() via as_dict() yields the
        # same dict shape downstream consumers expect.
        ent_rows = DBSession.execute(
            text(f"select * from {ent_ids_table}")).fetchall()
        _add('Entity', _filter_changed(ent_rows))
        for E in ent_rows:
            ent_ids.add((E.client_id, E.object_id))

    # --- Stage 9: Re-fetch all LEs (now including link_'d ones) ---
    if le_ids:
        le_full_filt = [_id_pairs_in(dbLexicalEntry, 'client_id', 'object_id', list(le_ids))]
        if action == 'create':
            le_full_filt.append(dbLexicalEntry.marked_for_deletion == False)
        le_rows_full = DBSession.query(dbLexicalEntry).filter(*le_full_filt).all()
        # Append-only update — already-added entries get overwritten with same data
        _add('LexicalEntry', _filter_changed(le_rows_full))

    # --- Stage 10: PublishingEntity (1:1 by id with Entity) ---
    # Raw SELECT joined against the entity-ids temp table — RowProxy
    # path, same shape as the Entity stage above.
    if ent_ids and ent_ids_table is not None:
        pe_rows = DBSession.execute(text(f"""
            select pe.* from publishingentity pe, {ent_ids_table} t
             where pe.client_id = t.client_id
               and pe.object_id = t.object_id
        """)).fetchall()
        _add('PublishingEntity', _filter_changed(pe_rows))

    # --- Stage 11: ParserResult under entities (via entity_ FK) ---
    # Raw SELECT joined against the entity-ids temp table.
    if ent_ids and ent_ids_table is not None:
        pr_md = "and pr.marked_for_deletion = false" if action == 'create' else ""
        pr_rows = DBSession.execute(text(f"""
            select pr.* from parserresult pr, {ent_ids_table} t
             where pr.entity_client_id = t.client_id
               and pr.entity_object_id = t.object_id
               {pr_md}
        """)).fetchall()
        _add('ParserResult', _filter_changed(pr_rows))
        for PR in pr_rows:
            if PR.parser_client_id is not None:
                parser_ids.add((PR.parser_client_id, PR.parser_object_id))

    # --- Stage 12: Parser ---
    if parser_ids:
        pa_filt = [_id_pairs_in(dbParser, 'client_id', 'object_id', list(parser_ids))]
        # Parser has no marked_for_deletion (or does it?) — apply if available
        if hasattr(dbParser, 'marked_for_deletion') and action == 'create':
            pa_filt.append(dbParser.marked_for_deletion == False)
        pa_rows = DBSession.query(dbParser).filter(*pa_filt).all()
        _add('Parser', _filter_changed(pa_rows))

    # --- Stage 13: TranslationGist (all collected) ---
    if gist_ids:
        tg_filt = [_id_pairs_in(dbTranslationGist, 'client_id', 'object_id', list(gist_ids))]
        if action == 'create':
            tg_filt.append(dbTranslationGist.marked_for_deletion == False)
        tg_rows = DBSession.query(dbTranslationGist).filter(*tg_filt).all()
        _add('TranslationGist', _filter_changed(tg_rows), also_subject=True)

    # --- Stage 14: TranslationAtom (children of those gists) ---
    if gist_ids:
        ta_filt = [
            tuple_(dbTranslationAtom.parent_client_id, dbTranslationAtom.parent_object_id)
                .in_(ids_to_id_query(list(gist_ids)))]
        if action == 'create':
            ta_filt.append(dbTranslationAtom.marked_for_deletion == False)
        ta_rows = DBSession.query(dbTranslationAtom).filter(*ta_filt).all()
        _add('TranslationAtom', _filter_changed(ta_rows), also_subject=True)


def ListChanges(info, perspective_id, remote, sync_between, action, debug_flag=False):

    # Memory tracing
    if debug_flag and False:
        tracemalloc.start(25)
        snap1 = tracemalloc.take_snapshot()
        objgraph.show_growth()

    request = info.context.request

    # The next variables are added manually but unavailable by graphql
    variables = request.json_body.get('variables', {})
    sync_point = variables.get('sync_point')
    locale_id = (
        int(request.cookies.get('locale_id') or ENGLISH_LOCALE))
    foreign_side = sync_point is not None

    settings = request.registry.settings
    local = settings['proxy']['local']

    # Get not local suffix from sync_between
    sync_for = sync_between[not sync_between.index(local)]

    local_result = {'warns': []}
    subject_ids = set()
    id_pool = set()
    client_ids = set()
    count = 0
    repeats = 0
    expunge_count = 0

    def store_data(side, data):

        pickle_path = 'no_store'

        # Don't store result locally
        # if query went from remote server
        if foreign_side:
            return pickle_path

        try:
            storage = settings['storage']
            storage_dir = os.path.join(storage['path'], f'{side}_sync')
            pickle_path = os.path.join(storage_dir, key2str(*perspective_id))
            os.makedirs(storage_dir, exist_ok=True)

            with gzip.open(pickle_path, 'wb') as f:
                pickle.dump({'stamp': now(), **data}, f)

        except Exception as e:
            raise ResponseError(f"Cannot write pickle file {pickle_path or ''}: {e}")

        return pickle_path

    def get_sync_point():

        perspective_metadata = ((
            DBSession
                .query(
                    dbDictionaryPerspective.additional_metadata)
                .filter_by(
                    client_id = perspective_id[0],
                    object_id = perspective_id[1])
                .first()
        ) or (None,))[0] or {}

        return perspective_metadata.get(f'{sync_for}_synced_at', min_date)

    def client_list():

        client_user_ids = (
            DBSession
                .query(
                    dbClient.id,
                    dbClient.user_id)
                .filter(
                    dbClient.id.in_(client_ids))
                .all())

        user_ids = set(user_id for _, user_id in client_user_ids)

        user_objs = (
            DBSession
                .query(
                    dbUser)
                .filter(
                    dbUser.id.in_(user_ids))
                .all())

        user_dict = {obj.id: as_dict(obj) for obj in user_objs}

        return client_user_ids, user_dict

    # Running cross request and storing data locally
    def cross_request():

        remote_result = {'warns': []}

        try:
            # Changing req_path and req_data to query from remote server
            if remote_server := settings['proxy'].get(f'{remote}_server'):
                client_path = remote_server + 'api' + request.path
            else:
                raise NotImplementedError

            # Get and set session
            adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
            session = requests.Session()
            session.headers.update({'Connection': 'Keep-Alive'})
            session.mount('http://', adapter)

            variables = {
                **request.json_body.get('variables', {}),
                'sync_point': get_sync_point()
            }

            req_args = {
                'json': {
                    **request.json_body,
                    'variables': variables
                },
                'cookies': request.cookies
            }

            # Query
            remote_resp = session.post(client_path, **req_args)
            resp_status = remote_resp.status_code
            remote_result.update((remote_resp.json()
                                 .get('data') or {})
                                 .get('list_changes'))

            if resp_status == 200 and remote_result.get('triumph'):
                pickle_path = store_data(remote, remote_result)

                if debug_flag:
                    log.warning(f'Foreign stored: {pickle_path} <- {remote}')
            else:
                raise ResponseError(f'Failed remote request: {resp_status=} from {remote=}')

            return summary(remote_result)

        except Exception as e:
            log.warning(str(e))

            remote_result['warns'].append(str(e))
            store_data(remote, remote_result)

            return summary(remote_result)

        finally:
            session.close()

    '''
    def get_db_objects(model, coid, suff):

        try:
            # Large perspective can totally fill memory
            # Compressed dictionary or hard-drive storing
            # need to get a plain dictionary back before
            # json-serialization. So it is not a solution
            if psutil.virtual_memory().percent > MEM_EDGE:
                message = "We have no enough RAM to synchronize this perspective"
                local_result['message'] = message
                raise RuntimeError(message)

            nonlocal count
            nonlocal repeats
            nonlocal expunge_count
            expunge_count += 1
            table = model.__name__

            if table not in local_result:
                local_result[table] = {}

            # Controlling already processed elements
            pool_item = key2str(*coid, table, suff)
            if pool_item in id_pool:
                repeats += 1
                return []
            id_pool.add(pool_item)

            # xal-leak fix: was previously building a CTE on (model, dbFilter)
            # then running two queries against the CTE — one filtered by
            # sync_point (changed_objects), one unfiltered (relatives). The
            # CTE construct was created fresh per recursion node and never
            # GC-released because each .cte() registers DDL events in
            # sqlalchemy.event.registry._key_to_collection, which holds
            # strong refs.  First fix: drop the CTE (62% RSS reduction).
            # Second fix (this code): cache the parameterized Query objects
            # per (model, suff, action) combo so the SQL expression tree
            # (BindParameter, _CompileLabel, etc.) is built once and reused
            # across recursion nodes — only the param VALUES change per call.

            q_changed, q_relatives = _get_or_build_fk_query(model, suff, action)

            changed_objects = (
                q_changed
                    .params(
                        _xal_cid=coid[0],
                        _xal_oid=coid[1],
                        _xal_sync_point=local_result['sync_point'])
                    .all())

            relatives = (
                q_relatives
                    .params(_xal_cid=coid[0], _xal_oid=coid[1])
                    .all())

            for obj in changed_objects:
                client_ids.add(obj.client_id)
                obj_coid = key2str(obj.client_id, obj.object_id)
                local_result[table][obj_coid] = as_dict(obj)

                if table in tables_for_roles:
                    subject_ids.add((obj.client_id, obj.object_id))

                if debug_flag:
                    report({
                        ('Sync point', 20): local_result['sync_point'],
                        ('Updated at', 20): obj.updated_at,
                        ('Composite id', 20): f"{obj_coid},{table}",
                        ('Deleted', 12): getattr(obj, 'marked_for_deletion', 'n/a'),
                        ('Content', 20): getattr(obj, 'content', 'n/a')
                    }, no_caption=bool(count))

                count += 1

                if expunge_count % CHUNK_SIZE == 0:
                    DBSession.expunge_all()
                    log.warning('Cleared session')

            return relatives

        except Exception as e:
            traceback_string = ''.join(traceback.format_exception(*sys.exc_info()))
            log.warning('get_db_objects: exception')
            log.warning(traceback_string)

            local_result['warns'].append(str(e))
            return FAILURE

        finally:
            #del relatives
            #DBSession.expunge_all()
            #gc.collect()
            pass

    def process_db_objects(*args):

        model, _, _ = args

        try:
            if (objects := get_db_objects(*args)) == FAILURE:
                raise RuntimeError

            relatives = db_tree[model]

            def get_id(obj, suff):
                return [
                    getattr(obj, f"{suff}client_id"),
                    getattr(obj, f"{suff}object_id")]

            for obj in objects:
                for model, our_suff, his_suff in relatives:
                    if process_db_objects(model, get_id(obj, our_suff), his_suff) == FAILURE:
                        raise RuntimeError

            return SUCCESS

        except Exception as e:
            log.warning(str(e))
            return FAILURE
    '''

    try:

        # Get client_id from security data
        if not request.authenticated_userid:
            raise ResponseError('no client_id is in request')

        # Cross-server query
        if local != remote:
            return cross_request()

        if debug_flag:
            log.warning('\nPreparing sync...')

        # For remote query get 'sync_point' from request json
        # for local query get it from database
        local_result['sync_point'] = sync_point or get_sync_point()

        # Bulk-walk replaces the per-FK-node Python recursion the function
        # was originally built around (see process_db_objects above, kept
        # in place as the authoritative reference for what this function
        # computes). The bulk walk produces a bit-for-bit identical
        # local_result with much lower memory and time cost, by issuing a
        # fixed handful of bulk queries (~12-15) and 3 recursive CTEs
        # rather than N queries per recursion node.
        _walk_perspective_bulk(perspective_id, sync_point, action,
                               local_result, client_ids, subject_ids)

        local_result['triumph'] = True

        if local == 'isp' and foreign_side:
            local_result['clients'] = client_list()

        if foreign_side:
            # Update result with roles for subjects
            local_result['roles'] = ListRoles(None, subject_ids, debug_flag)

        # Pickling by perspective id
        pickle_path = store_data(local, local_result)

        if debug_flag:
            log.warning(f'\nSkipped repeats: {repeats}')
            log.warning(f'Local stored: {local} -> {pickle_path}')

        return local_result if foreign_side else summary(local_result)

    except Exception as e:
        traceback_string = ''.join(traceback.format_exception(*sys.exc_info()))
        log.warning('ListChanges: exception')
        log.warning(traceback_string)

        local_result['triumph'] = False
        local_result['warns'].append(str(e))
        store_data(local, local_result)

        return local_result if foreign_side else summary(local_result)

    finally:
        log.warning('Run garbage collector')
        del local_result
        DBSession.expunge_all()
        gc.collect()
        if debug_flag and False:
            check_memory()
            snap2 = tracemalloc.take_snapshot()
            for stat in snap2.compare_to(snap1, 'lineno')[:30]:
                print(stat)
            objgraph.show_growth()
            A()


def MergeChanges(
        info,
        perspective_id,
        sync_between,
        action='edit',
        perspective_name="<unnamed perspective>",
        **args):

    if not CheckPermissions(info, perspective_id, action):
        return {
            'triumph': False,
            'message': "You have no permissions to do sync"
        }

    client_id = info.context.client_id
    user_id = dbClient.get_user_by_client_id(client_id).id
    task_status = TaskStatus(
        user_id, "Synchronization", perspective_name, tables_num + 2)

    # 'info' is not serializable, so we have to get
    # single values as arguments for async function
    request = info.context.request
    settings = request.registry.settings
    local = settings['proxy']['local']
    remote = sync_between[not sync_between.index(local)]

    async_func_args = {
        'local': local,
        'remote': remote,
        'storage_path': settings['storage']['path'],
        'sqlalchemy_url': settings['sqlalchemy.url'],
        'cache_kwargs': settings['cache_kwargs'],
        'task_key': task_status.key
    }

    MergeChangesAsync.delay(perspective_id, **async_func_args, **args)
    # We return success result, but async
    # function may end not successfully
    return {'triumph': True, 'message': ""}


@celery.task
def MergeChangesAsync(
        perspective_id,
        local,
        remote,
        storage_path,
        sqlalchemy_url,
        cache_kwargs,
        task_key,
        debug_flag=False):

    # Ok, and now we go on with task execution.
    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind=engine)
    initialize_cache(cache_kwargs)
    task_status = TaskStatus.get_from_cache(task_key)

    task_status.set(1, 20, 'Getting stored data...')

    def set_synced_at(synced_at):
        db_perspective = (
            DBSession
                .query(
                    dbDictionaryPerspective)
                .filter_by(
                    client_id = perspective_id[0],
                    object_id = perspective_id[1])
                .one())

        perspective_metadata = db_perspective.additional_metadata or {}
        db_perspective.additional_metadata = {
            **perspective_metadata,
            f'{remote}_synced_at': synced_at}

    local_pickle_path = os.path.join(
        storage_path,
        f'{local}_sync',
        key2str(*perspective_id)
    )
    foreign_pickle_path = os.path.join(
        storage_path,
        f'{remote}_sync',
        key2str(*perspective_id)
    )

    try:
        pickle_path = local_pickle_path
        local_changes = {}
        foreign_changes = {}

        # Reading pickle files
        try:
            with gzip.open(pickle_path, 'rb') as f:
                local_changes = pickle.load(f)

            pickle_path = foreign_pickle_path

            with gzip.open(pickle_path, 'rb') as f:
                foreign_changes = pickle.load(f)

        except Exception as e:
            raise ResponseError(f"Cannot read file '{pickle_path}': {e}")

        if not local_changes.get('triumph') or not foreign_changes.get('triumph'):
            message = (
                ((m1 := local_changes.get('message', "")) and f"LOCAL: {m1}; ") +
                ((m2 := foreign_changes.get('message', "")) and f"REMOTE: {m2}"))
            raise ResponseError(message or 'Changes data is not correct')

        current_synced_at = local_changes['sync_point']
        next_synced_at = current_synced_at

        task_status.set(1, 70, 'Adding new clients and users...')

        try:
            # Adding users and clients met in perspective into remote database
            if local != 'isp':
                client_user_ids, user_dict = foreign_changes['clients']

                for client_id, user_id in client_user_ids:

                    if not DBSession.query(dbUser).filter_by(id=user_id).first():
                        user = dbUser(**user_dict[str(user_id)])
                        DBSession.add(user)

                    if not DBSession.query(dbClient).filter_by(id=client_id).first():
                        client = dbClient(id=client_id, user_id=user_id)
                        DBSession.add(client)

                DBSession.flush()

        except (UniqueViolation, IntegrityError, ResourceClosedError):
            DBSession.rollback()
            transaction.abort()

        except Exception as e:
            if debug_flag:
                A()
            raise

        task_status.set(1, 90, 'Getting maximal update time for local changes...')

        # Iterate by local changes to get maximal updating point
        # this time will be new sync_point (not real time)
        for table in db_model_data:
            for local_dict in local_changes.get(table, {}).values():
                local_update = local_dict.get('updated_at')
                next_synced_at = max(next_synced_at, local_update)

        if debug_flag:
            log.warning('\nApplying sync...')

        count = 0

        for i, (table, model) in enumerate(db_model_data.items()):
            table_data = foreign_changes.get(table, {})

            if debug_flag and False:
                print(f"Memory usage: {psutil.virtual_memory().percent}%")
                time.sleep(1)

            # Sorting within groups by recursion field to make None values before any other
            if table in ['Entity', 'DictionaryPerspectiveToField']:
                table_data = dict(sorted(
                    table_data.items(), key=lambda item: bool(item[1]['self_client_id'])))
            elif table in ['Language']:
                table_data = dict(reversed(table_data.items()))

            table_data_size = len(table_data)

            for j, (obj_coid, foreign_dict) in enumerate(table_data.items()):

                if j % 100 == 0:
                    task_status.set(
                        i + 2, int(j / table_data_size * 100), f'Writing {table}...')

                local_dict = local_changes.get(table, {}).get(obj_coid, {})
                local_update = local_dict.get('updated_at', min_date)
                foreign_update = foreign_dict.get('updated_at')
                foreign_content = foreign_dict.get('content', '')
                foreign_deleted = foreign_dict.get('marked_for_deletion')

                client_id, object_id = obj_coid.split(',')

                try:
                    db_object = (
                        DBSession
                            .query(model)
                            .filter_by(
                                client_id=client_id,
                                object_id=object_id)
                            .first())

                    action = None

                    # We don't add deleted element
                    if (db_object is None and
                          not foreign_deleted):
                        # Add new object
                        db_object = model(**foreign_dict)
                        DBSession.add(db_object)

                        action = 'added'

                    elif foreign_update > local_update:
                        # Delete client_id and object_id
                        # from dict to avoid collision
                        foreign_dict.pop('client_id', None)
                        foreign_dict.pop('object_id', None)

                        for k, v in foreign_dict.items():
                            setattr(db_object, k, v)

                        action = 'updated'

                    DBSession.flush()
                    transaction.commit()

                # Some entities correspond to corrupted fields, we'll skip them
                except (UniqueViolation, IntegrityError, ResourceClosedError):
                    DBSession.rollback()
                    transaction.abort()
                    log.warning("Rolled back session")

                except Exception as e:
                    if debug_flag:
                        A()
                    raise

                next_synced_at = max(next_synced_at, foreign_update)

                if debug_flag and action and False:
                    report({
                        ('Sync time', 20): current_synced_at,
                        ('Foreign update', 20): foreign_update,
                        ('Local update', 20): local_update,
                        ('Action', 8): action,
                        ('Composite id', 20): f"{obj_coid},{table}",
                        ('Foreign content', 20): foreign_content
                    }, no_caption=bool(count))

                count += 1

                if count % CHUNK_SIZE == 0:
                    DBSession.expunge_all()
                    log.warning('Cleared session')

        task_status.set(tables_num + 2, 10, f'Final steps')

        if next_synced_at > current_synced_at:
            set_synced_at(next_synced_at)
            DBSession.flush()

        task_status.set(tables_num + 2, 50, f'Final steps')

        # Add roles for current perspective
        MergeRoles(foreign_changes['roles'], debug_flag)

        os.remove(local_pickle_path)
        os.remove(foreign_pickle_path)

        task_status.set(tables_num + 2, 100, f'Synchronization complete')

        if debug_flag:
            log.warning('\nComplete!')

        #return {'triumph': True, 'message': ""}

    except Exception as e:
        message = f"Something went wrong with merging of changes: {str(e)}"
        traceback_string = ''.join(traceback.format_exception(*sys.exc_info()))
        log.warning(message)
        log.warning(traceback_string)
        task_status.set(None, -1, 'Finished (ERROR), exception:\n' + traceback_string)
        '''
        return {
            'triumph': False,
            'message': message
        }
        '''

    finally:
        log.warning('Run garbage collector')
        del local_changes, foreign_changes
        gc.collect()
        if debug_flag:
            check_memory()
            #A()
