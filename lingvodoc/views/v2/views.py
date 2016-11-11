from lingvodoc.views.v2.utils import (
    get_user_by_client_id
)

from pyramid.response import Response
from pyramid.view import view_config
from lingvodoc.models import (
    DBSession,
    Locale,
    TranslationAtom,
    TranslationGist,
    BaseGroup,
    User,
    DictionaryPerspective,
    Field
)

from sqlalchemy import (
    func,
    or_,
    and_,
    tuple_
)
from pyramid.httpexceptions import (
    HTTPFound,
    HTTPOk
)
from pyramid.security import authenticated_userid
# from pyramid.chameleon_zpt import render_template_to_response
from pyramid.renderers import render_to_response

import sys
import multiprocessing

if sys.platform == 'darwin':
    multiprocessing.set_start_method('spawn')

import logging
log = logging.getLogger(__name__)


@view_config(route_name='testing', renderer='json')
def testing(request):
    response = list()
    # for persp in DBSession.query(DictionaryPerspective).all():
    #     if persp.additional_metadata:
    #         response.append(str(type(persp.additional_metadata)))
    return response
    # # translation_gists = DBSession.query(TranslationGist).all()
    # gist_base = DBSession.query(BaseGroup).filter_by(action="delete",
    #                                                  subject="translations").one()
    # # for tr_gist in translation_gists:
    # #     client = DBSession.query(Client).filter_by(id=tr_gist.client_id).one()
    # #     user = DBSession.query(User).filter_by(id=client.user_id).one()
    # #     new_group = Group(parent=gist_base, subject_client_id=tr_gist.client_id,
    # #                       subject_object_id=tr_gist.object_id)
    # #     user.groups.append(new_group)
    #
    # # translation_atoms = DBSession.query(TranslationAtom).all()
    # atom_base = DBSession.query(BaseGroup).filter_by(action="edit",
    #                                                  subject="translations").one()
    # # for tr_atom in translation_atoms:
    # #     client = DBSession.query(Client).filter_by(id=tr_atom.client_id).one()
    # #     user = DBSession.query(User).filter_by(id=client.user_id).one()
    # #     new_group = Group(parent=atom_base, subject_client_id=tr_atom.client_id,
    # #                       subject_object_id=tr_atom.object_id)
    # #     user.groups.append(new_group)
    # admin = DBSession.query(User).filter_by(id=1).one()
    # # gist_group = Group(parent=gist_base, subject_override=True)
    # # admin.groups.append(gist_group)
    # # atom_group = Group(parent=atom_base, subject_override=True)
    # # admin.groups.append(atom_group)

    return {}


@view_config(route_name='main', renderer='templates/main.pt', request_method='GET')
def main_get(request):
    client_id = authenticated_userid(request)
    user = get_user_by_client_id(client_id)
    variables = {'client_id': client_id, 'user': user}
    return render_to_response('templates/main.pt', variables, request=request)


@view_config(route_name='all_statuses', renderer='json', request_method='GET')
def all_statuses(request):
    from pyramid.request import Request
    import json

    response = list()
    for status in ['WiP', 'Published', 'Limited access', 'Hidden']:

        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'searchstring': status}
        headers = {'Cookie': request.headers['Cookie']}
        subreq.headers = headers
        resp = request.invoke_subrequest(subreq)
        response.append(resp.json)
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='all_locales', renderer='json', request_method='GET')
def all_locales(request):
    response = list()
    locales = DBSession.query(Locale).all()
    for locale in locales:
        locale_json = dict()
        locale_json['shortcut'] = locale.shortcut
        locale_json['intl_name'] = locale.intl_name
        locale_json['created_at'] = locale.created_at.timestamp()
        locale_json['id'] = locale.id
        response.append(locale_json)
    request.response.status = HTTPOk.code
    return response


def dict_ids(obj):
    return {"client_id": obj.client_id,
            "object_id": obj.object_id}


@view_config(route_name='corpora_fields', renderer='json', request_method='GET')
def corpora_fields(request):
    response = list()
    data_type_query = DBSession.query(Field) \
        .join(TranslationGist,
              and_(Field.translation_gist_object_id == TranslationGist.object_id,
                   Field.translation_gist_client_id == TranslationGist.client_id))\
        .join(TranslationGist.translationatom)
    sound_field = data_type_query.filter(TranslationAtom.locale_id == 2,
                                         TranslationAtom.content == 'Sound').one() # todo: a way to find this fields if wwe cannot use one
    markup_field = data_type_query.filter(TranslationAtom.locale_id == 2,
                                          TranslationAtom.content == 'Markup').one()
    response.append(dict_ids(sound_field))
    response[0]['contains'] = [dict_ids(markup_field)]
    response.append(dict_ids(markup_field))
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='all_data_types', renderer='json', request_method='GET')
def all_data_types(request):
    from pyramid.request import Request
    import json

    response = list()
    for data_type in ['Text', 'Image', 'Sound', 'Markup', 'Link', 'Grouping Tag']:

        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'searchstring': data_type}
        # headers = {'Cookie': request.headers['Cookie']}
        # subreq.headers = headers
        resp = request.invoke_subrequest(subreq)
        response.append(resp.json)
    request.response.status = HTTPOk.code
    return response


conn_err_msg = """\
Pyramid is having a problem using your SQL database.  The problem
might be caused by one of the following things:

1.  You may need to run the "initialize_lingvodoc_db" script
    to initialize your database tables.  Check your virtual
    environment's "bin" directory for this script and try to run it.

2.  Your database server may not be running.  Check that the
    database server referred to by the "sqlalchemy.url" setting in
    your "development.ini" file is running.

After you fix the problem, please restart the Pyramid application to
try it again.
"""