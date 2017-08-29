from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    DictionaryPerspective,
    Group,
    LexicalEntry,
    User,
    Entity,
    TranslationAtom,
    Field,
    PublishingEntity,
    Dictionary,
    DictionaryPerspectiveToField
)

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPOk
)
from pyramid.view import view_config

from sqlalchemy import (
    func,
    or_,
    and_,
    tuple_
)
from sqlalchemy.orm import joinedload, subqueryload
from pyramid.request import Request


@view_config(route_name='basic_search', renderer='json', request_method='GET')
def basic_search(request):
    can_add_tags = request.params.get('can_add_tags')
    searchstring = request.params.get('searchstring')
    perspective_client_id = request.params.get('perspective_client_id')
    perspective_object_id = request.params.get('perspective_object_id')
    field_client_id = request.params.get('field_client_id')
    field_object_id = request.params.get('field_object_id')
    search_in_published = request.params.get('published') or None
    if searchstring:
        if len(searchstring) >= 1:
            field = None
            if field_client_id and field_object_id:
                field = DBSession.query(Field).filter_by(client_id=field_client_id, object_id=field_object_id).first()

            searchstring = request.params.get('searchstring')
            group = DBSession.query(Group).filter(Group.subject_override == True).join(BaseGroup)\
                    .filter(BaseGroup.subject=='lexical_entries_and_entities', BaseGroup.action=='view')\
                    .join(User, Group.users).join(Client)\
                    .filter(Client.id == request.authenticated_userid).first()
            # print(group)
            # if not group:
            #     group = 1
            published_cursor = None
            if group: # todo: change!!!!!
                results_cursor = DBSession.query(Entity).filter(Entity.content.like('%'+searchstring+'%'), Entity.marked_for_deletion == False)
                # results_cursor = list()
                if perspective_client_id and perspective_object_id:
                    results_cursor = results_cursor.join(LexicalEntry)\
                        .join(DictionaryPerspective)\
                        .filter(DictionaryPerspective.client_id == perspective_client_id,
                                DictionaryPerspective.object_id == perspective_object_id)
            else:
                results_cursor = DBSession.query(Entity)\
                    .join(Entity.parent)\
                    .join(DictionaryPerspective)

                if not perspective_client_id or not perspective_object_id:
                    published_cursor = results_cursor
                # results_cursor = list()
                ignore_groups = False

                subreq = Request.blank('/translation_service_search')
                subreq.method = 'POST'
                subreq.headers = request.headers
                subreq.json = {'searchstring': 'Published'}
                headers = dict()
                if request.headers.get('Cookie'):
                    headers = {'Cookie': request.headers['Cookie']}
                subreq.headers = headers
                resp = request.invoke_subrequest(subreq)

                if 'error' not in resp.json:
                    state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json['client_id']
                else:
                    raise KeyError("Something wrong with the base", resp.json['error'])

                if perspective_client_id and perspective_object_id:
                    results_cursor = results_cursor.filter(DictionaryPerspective.client_id == perspective_client_id,
                                DictionaryPerspective.object_id == perspective_object_id)
                    persp = DBSession.query(DictionaryPerspective).filter_by(client_id=perspective_client_id, object_id=perspective_object_id).first()
                    if persp and persp.state_translation_gist_client_id == state_translation_gist_client_id and persp.state_translation_gist_object_id == state_translation_gist_object_id:
                        ignore_groups = True
                else:
                    published_cursor = results_cursor

                if not ignore_groups:
                    results_cursor = results_cursor.join(Group, and_(DictionaryPerspective.client_id == Group.subject_client_id, DictionaryPerspective.object_id == Group.subject_object_id ))\
                        .join(BaseGroup)\
                        .join(User, Group.users)\
                        .join(Client)\
                        .filter(Client.id == request.authenticated_userid, Entity.content.like('%'+searchstring+'%'), Entity.marked_for_deletion == False)
                else:
                    results_cursor = results_cursor.filter(Entity.content.like('%'+searchstring+'%'), Entity.marked_for_deletion == False)
                if published_cursor:

                    published_cursor = published_cursor \
                        .join(DictionaryPerspective.parent).filter(
                        Dictionary.state_translation_gist_object_id == state_translation_gist_object_id,
                        Dictionary.state_translation_gist_client_id == state_translation_gist_client_id,
                        DictionaryPerspective.state_translation_gist_object_id == state_translation_gist_object_id,
                        DictionaryPerspective.state_translation_gist_client_id == state_translation_gist_client_id,
                     Entity.content.like('%'+searchstring+'%'))
            results = []
            entries = list()
            if can_add_tags:
                if can_add_tags.lower() == 'false':
                    can_add_tags = False
                elif can_add_tags.lower() == 'true':
                    can_add_tags = True
                else:
                    can_add_tags = None

            if can_add_tags:
                results_cursor = results_cursor \
                    .filter(BaseGroup.subject == 'lexical_entries_and_entities',
                            or_(BaseGroup.action == 'create', BaseGroup.action =='view'))\
                    .group_by(Entity).having(func.count('*') == 2)
                # results_cursor = list()
            else:
                results_cursor = results_cursor.filter(BaseGroup.subject=='lexical_entries_and_entities', BaseGroup.action=='view')

            # print(results_cursor)
            if field:
                results_cursor = results_cursor.join(DictionaryPerspective.dictionaryperspectivetofield).filter(
                    DictionaryPerspectiveToField.field == field)
                if published_cursor:
                    published_cursor = published_cursor.join(DictionaryPerspective.dictionaryperspectivetofield).filter(
                        DictionaryPerspectiveToField.field == field)
            for item in results_cursor:
                if item.parent not in entries:
                    entries.append(item.parent)
            if published_cursor:
                for item in published_cursor:
                    if item.parent not in entries:
                        entries.append(item.parent)
            for entry in entries:
                if not entry.marked_for_deletion:
                    # print(entry.__class__)
                    if (entry.parent_client_id, entry.parent_object_id) in DictionaryPerspective.get_deleted():
                        continue
                    if (entry.parent_client_id, entry.parent_object_id) in DictionaryPerspective.get_hidden():
                        continue
                    # if (entry.parent_client_id, entry.parent_object_id) in DictionaryPerspective.get_etymology():
                    #     continue
                    url = request.route_url('perspective',
                                            dictionary_client_id=entry.parent.parent.client_id,
                                            dictionary_object_id=entry.parent.parent.object_id,
                                            perspective_client_id=entry.parent_client_id,
                                            perspective_object_id=entry.parent_object_id)
                    subreq = Request.blank(url)
                    subreq.method = 'GET'
                    headers = {'Cookie': request.headers['Cookie']}
                    subreq.headers = headers
                    resp = request.invoke_subrequest(subreq)
                    result = resp.json
                    result['lexical_entry'] = entry.track(search_in_published, request.cookies['locale_id'])
                    dict_tr = entry.parent.parent.get_translation(request.cookies['locale_id'])
                    result['parent_translation'] = dict_tr
                    results.append(result)
            request.response.status = HTTPOk.code
            return results
    request.response.status = HTTPBadRequest.code
    return {'error': 'search is too short'}

from sqlalchemy.sql import select
# TODO: completely broken!
@view_config(route_name='advanced_search', renderer='json', request_method='POST')
def advanced_search(request):
    from sqlalchemy import bindparam
    req = request.json
    searchstrings = req.get('searchstrings') or []
    perspectives = req.get('perspectives', list())

    if perspectives:
        perspectives = [(o['client_id'], o['object_id']) for o in perspectives]
    else:
        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'searchstring': 'Published'}
        headers = {'Cookie': request.headers['Cookie']}
        subreq.headers = headers
        resp = request.invoke_subrequest(subreq)
        if 'error' not in resp.json:
            state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json[
                'client_id']
            published_gist = (state_translation_gist_client_id, state_translation_gist_object_id)
        else:
            raise KeyError("Something wrong with the base", resp.json['error'])
        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'searchstring': 'Limited access'}
        headers = {'Cookie': request.headers['Cookie']}
        subreq.headers = headers
        resp = request.invoke_subrequest(subreq)
        if 'error' not in resp.json:
            state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json[
                'client_id']
            limited_gist = (state_translation_gist_client_id, state_translation_gist_object_id)
        else:
            raise KeyError("Something wrong with the base", resp.json['error'])

        perspectives = [(o.client_id, o.object_id) for o in DBSession.query(DictionaryPerspective).filter(
            DictionaryPerspective.marked_for_deletion == False,
            or_(and_(DictionaryPerspective.state_translation_gist_client_id == published_gist[0],
                     DictionaryPerspective.state_translation_gist_object_id == published_gist[1]),
                and_(DictionaryPerspective.state_translation_gist_client_id == limited_gist[0],
                     DictionaryPerspective.state_translation_gist_object_id == limited_gist[1]))).all()]

    adopted = req.get('adopted')
    adopted_type = req.get('adopted_type')
    with_etimology = req.get('with_etimology')

    def make_query(searchstring, perspectives):

        results_cursor = DBSession.query(LexicalEntry).join(Entity.parent) \
            .join(Entity.field).join(TranslationAtom,
                                     and_(Field.translation_gist_client_id == TranslationAtom.parent_client_id,
                                          Field.translation_gist_object_id == TranslationAtom.parent_object_id,
                                          Field.marked_for_deletion == False)) \
            .distinct(Entity.parent_client_id, Entity.parent_object_id)
        if perspectives:
            results_cursor = results_cursor.filter(
                tuple_(LexicalEntry.parent_client_id, LexicalEntry.parent_object_id).in_(perspectives))
        if not searchstring['searchstring']:
            raise HTTPBadRequest
        search_parts = searchstring['searchstring'].split()
        search_expression = Entity.content.like('%' + search_parts[0] + '%')
        to_do_or = searchstring.get('search_by_or', True)

        for part in search_parts[1:]:
            search_expression = or_(search_expression, Entity.content.like('%' + part + '%'))
        if 'entity_type' in searchstring and searchstring['entity_type']:
            search_expression = and_(search_expression, TranslationAtom.content == searchstring['entity_type'],
                                     TranslationAtom.locale_id==2)
        results_cursor = results_cursor.filter(search_expression)
        return results_cursor, to_do_or

    if not searchstrings:
        request.response.status = HTTPBadRequest.code
        return {'error': 'The query string couldn\'t be empty'}

    try:
        results_cursor, to_do_or = make_query(searchstrings[0], perspectives)
    except HTTPBadRequest:
        request.response.status = HTTPBadRequest.code
        return {'error': 'The query string couldn\'t be empty'}
    pre_results = set(results_cursor.all())
    if adopted:
        results_cursor = DBSession.query(LexicalEntry).join(Entity.parent).filter(Entity.content.like('%заим.%'))
        if adopted_type:
            results_cursor = results_cursor.join(Entity.field) \
                .join(TranslationAtom,
                      and_(Field.translation_gist_client_id == TranslationAtom.parent_client_id,
                           Field.translation_gist_object_id == TranslationAtom.parent_object_id,
                           Field.marked_for_deletion == False)) \
                .filter(TranslationAtom.content == adopted_type,
                        TranslationAtom.locale_id == 2)
        pre_results = pre_results & set(results_cursor.all())
    if with_etimology:
        results_cursor = DBSession.query(LexicalEntry).join(Entity.parent).join(Entity.field) \
            .join(TranslationAtom,
                  and_(Field.data_type_translation_gist_client_id == TranslationAtom.parent_client_id,
                       Field.data_type_translation_gist_object_id == TranslationAtom.parent_object_id,
                       Field.marked_for_deletion == False)) \
            .filter(TranslationAtom.content == 'Grouping Tag',
                    TranslationAtom.locale_id == 2)
        pre_results = pre_results & set(results_cursor.all())
    for search_string in searchstrings[1:]:
        results_cursor, to_do_or_new = make_query(search_string, perspectives)
        if to_do_or:
            pre_results = pre_results | set(results_cursor.all())
        else:
            pre_results = pre_results & set(results_cursor.all())
        to_do_or = to_do_or_new


    # s = select([LexicalEntry.__table__])\
    #     .select_from(LexicalEntry.__table__.join(Entity.__table__,
    #                  and_(
    #                      LexicalEntry.__table__.c.client_id == Entity.__table__.c.parent_client_id,
    #                      LexicalEntry.__table__.c.object_id == Entity.__table__.c.parent_object_id))
    #                  .join(PublishingEntity.__table__,
    #                  and_(
    #                      Entity.__table__.c.client_id == PublishingEntity.__table__.c.client_id,
    #                      Entity.__table__.c.object_id == PublishingEntity.__table__.c.object_id))) \
    #     .where(and_(LexicalEntry.__table__.c.client_id == bindparam('client_id'),
    #                 LexicalEntry.__table__.c.object_id == bindparam('object_id')))
    #
    # DBSession.query(LexicalEntry).filter(or_())
    #
    # results = [{"client_id":o[0], "object_id":o[1]} for o in list(results)]
    # res = DBSession.execute(s, results)
    #
    # # results_cursor = DBSession.query(LexicalEntry) \
    # #     .options(joinedload('entity').subqueryload('publishingentity')) \
    # #     .filter(tuple_(LexicalEntry.client_id, LexicalEntry.object_id).in_(results))
    results = list()

    lexes_composite_list = [(lex.created_at,
                             lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
                             lex.marked_for_deletion, lex.additional_metadata,
                             lex.additional_metadata.get('came_from')
                             if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
                            for lex in pre_results]

    results = LexicalEntry.track_multiple(lexes_composite_list, int(request.cookies.get('locale_id') or 2), publish=True, accept=True)

    # for entry in pre_results:
    #     results.append(entry.track(False, int(request.cookies.get('locale_id') or 2)))
        # tmp_result = dict()
        # # tmp_result['lexical_entry'] = item.track(True)
        # tmp_result['lex_client_id'] = item.client_id
        # tmp_result['lex_object_id'] = item.object_id
        # tmp_result['client_id'] = item.parent_client_id
        # tmp_result['object_id'] = item.parent_object_id
        # perspective_tr = item.parent.get_translation(2)
        # tmp_result['translation'] = perspective_tr
        # tmp_result['is_template'] = item.parent.is_template
        # tmp_result['status'] = item.parent.state
        # tmp_result['marked_for_deletion'] = item.parent.marked_for_deletion
        # tmp_result['parent_client_id'] = item.parent.parent_client_id
        # tmp_result['parent_object_id'] = item.parent.parent_object_id
        # dict_tr = item.parent.parent.get_translation(2)
        # tmp_result['parent_translation'] = dict_tr
        # results.append(tmp_result)
    request.response.status = HTTPOk.code
    return results


# TODO: completely broken!
@view_config(route_name='entity_metadata_search', renderer='json', request_method='GET')
def entity_metadata_search(request):  # TODO: test
    # TODO: add same check for permission as in basic_search
    searchstring = request.params.get('searchstring')
    if type(searchstring) != str:
        searchstring = str(searchstring)
    searchtype = request.params.get('searchtype')
    perspective_client_id = request.params.get('perspective_client_id')
    perspective_object_id = request.params.get('perspective_object_id')
    # results_cursor = DBSession.query(LevelOneEntity)\
    #     .filter(LevelOneEntity.entity_type.like('%'+searchtype+'%'),
    #             LevelOneEntity.additional_metadata.like('%'+searchstring+'%'))
    results_cursor = list()
    if perspective_client_id and perspective_object_id:
        results_cursor = results_cursor.join(LexicalEntry).join(DictionaryPerspective).filter(DictionaryPerspective.client_id == perspective_client_id,
                                               DictionaryPerspective.object_id == perspective_object_id)
    results = []
    entries = set()
    for item in results_cursor:
        entries.add(item)
    for entry in entries:
        if not entry.marked_for_deletion:
            result = dict()
            result['client_id'] = entry.client_id
            result['object_id'] = entry.object_id
            result['additional_metadata'] = entry.additional_metadata
            results.append(result)
    return results
