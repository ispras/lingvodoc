from pyramid.response import Response
from pyramid.view import view_config

from sqlalchemy.exc import DBAPIError

from .models import (
    DBSession,
    MetaWord,
    WordEntry,
    Dictionary,
    User,
    Client,
    Email,
    Passhash,
    Group,
    BaseGroup,
    WordTranscription,
    WordTranslation,
    WordSound,
    WordEtymologyTag,
    WordMarkup,
    MetaParadigm,
    ParadigmEntry,
    ParadigmMarkup,
    ParadigmSound,
    ParadigmTranscription,
    ParadigmTranslation,
    )

from pyramid.security import (
    Everyone,
    Allow,
    Deny
    )

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import joinedload, subqueryload, noload, join, joinedload_all

from pyramid.httpexceptions import HTTPForbidden
from pyramid.httpexceptions import HTTPFound
from pyramid.httpexceptions import HTTPNotFound, HTTPOk, HTTPBadRequest, HTTPConflict, HTTPInternalServerError
from pyramid.httpexceptions import HTTPUnauthorized
from pyramid.security import authenticated_userid
from pyramid.security import forget
from pyramid.security import remember
from pyramid.view import forbidden_view_config

#from pyramid.chameleon_zpt import render_template_to_response
from pyramid.renderers import render_to_response
from pyramid.response import FileResponse

import os
import datetime
import base64


class CommonException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def group_filter(session, base_group_name, subject):
    group_limited = session.query(BaseGroup).filter(BaseGroup.name == base_group_name).first()
    groups_fit = []
    for group in group_limited.groups:
        if group.subject == subject:
            groups_fit.append(group)
    return groups_fit


def add_child_group(session, base_group_name, subject):
    base_group = session.query(BaseGroup).filter(BaseGroup.name == base_group_name).first()
    base_group.groups.append(Group(subject=str(subject)))
    session.flush()

    return base_group.groups[-1]


def object_file_path(obj, create_dir=False):
    base_path = '/tmp'
    storage_dir = os.path.join(base_path, obj.__tablename__, str(obj.client_id), str(obj.id))
    if create_dir:
        os.makedirs(storage_dir, exist_ok=True)
    storage_path = os.path.join(storage_dir, "content.original")
    return storage_path


def create_object(content, obj):
    # here will be object storage write as an option. Fallback (default) is filesystem write
    storage_path = object_file_path(obj, True)

    f = open(storage_path, 'wb+')
    f.write(base64.urlsafe_b64decode(content))
    f.close()
    return


def produce_subtypes(obj_type, client, value):
    DBSession.flush()
    if obj_type == WordSound or obj_type == ParadigmSound:
        obj = obj_type(id=DBSession.query(obj_type).filter_by(client_id=client.id).count()+1,
                       client=client,
                       client_id=client.id,
                       mime=value['mime'],
                       name=value['name'],
                       marked_to_delete=False)
        DBSession.flush()

        # if obj_type == WordSound:
        #     markup_type = WordMarkup
        # else:
        #     markup_type = ParadigmMarkup
        # if value['markups']:
        # # TODO: there is a bug here, but i can't find where and which.
        #     for markup in value['markups']:
        #         markup_obj = markup_type(id=DBSession.query(markup_type).filter_by(client_id=client.id).count()+1,
        #                                  client=client,
        #                                  content=markup['content'],
        #                                  marked_to_delete=False)
        #         DBSession.flush()
        #         obj.markups.append(markup_obj)
        create_object(value['content'], obj)

    else:
        obj = obj_type(id=DBSession.query(obj_type).filter_by(client_id=client.id).count()+1,
                       client=client,
                       client_id=client.id,
                       content=value['content'],
                       marked_to_delete=False)
    return obj


# NOTE: TODO: very fucked up code, rewrite completely later.
def traverse_paradigm(metaparadigm, dictionary_client_id, dictionary_id, request):
    metaparadigm_ids = dict()
    metaparadigm_ids['metaword_id'] = metaparadigm.metaword_id
    metaparadigm_ids['metaword_client_id'] = metaparadigm.metaword_client_id
    metaparadigm_ids['metaparadigm_id'] = metaparadigm.id
    metaparadigm_ids['metaparadigm_client_id'] = metaparadigm.client_id
    metaparadigm_ids['url'] = request.route_url('api_metaword_get',
                                                dictionary_client_id=metaparadigm_ids['dictionary_client_id'],
                                                dictionary_id=metaparadigm_ids['dictionary_id'],
                                                metaword_client_id=metaparadigm_ids['metaword_client_id'],
                                                metaword_id=metaparadigm_ids['metaword_id'])

    for field in 'entries', 'transcriptions', 'translations', 'sounds':
        metaparadigm_ids[field] = []
        #print(vars(metaparadigm))
        if field in vars(metaparadigm):
            for obj in vars(metaparadigm)[field]:
                obj_description = dict()
                obj_description['id'] = obj.id
                obj_description['client_id'] = obj.client_id
                obj_description['creation_time'] = str(obj.creation_time)
                obj_description['author'] = str(obj.client.User.name)
                if field in ['entries', 'transcriptions', 'translations']:
                    obj_description['content'] = obj.content
                elif field in ['sounds']:
                    obj_description['url'] = request.route_url('api_metaparadigm_sound_get',
                                                               dictionary_client_id=dictionary_client_id,
                                                               dictionary_id=dictionary_id,
                                                               metaword_client_id=obj.metaword_client_id,
                                                               metaword_id=obj.metaword_id,
                                                               metaparadigm_client_id=obj.metaparadigm_client_id,
                                                               metaparadigm_id=obj.metaparadigm_id,
                                                               sound_client_id=obj.client_id,
                                                               sound_id=obj.id)

                metaparadigm_ids[field].append(obj_description)
    return metaparadigm_ids


def traverse_metaword(metaword, request):
    metaword_ids = dict()
    metaword_ids['dictionary_id'] = metaword.dictionary_id
    metaword_ids['dictionary_client_id'] = metaword.dictionary_client_id
    metaword_ids['dictionary_name'] = DBSession.query(Dictionary).filter_by(id=metaword.dictionary_id,
                                                                            client_id=metaword.dictionary_client_id).first().name
    metaword_ids['metaword_id'] = metaword.id
    metaword_ids['metaword_client_id'] = metaword.client_id
    metaword_ids['url'] = request.route_url('api_metaword_get',
                                            dictionary_client_id=metaword_ids['dictionary_client_id'],
                                            dictionary_id=metaword_ids['dictionary_id'],
                                            metaword_client_id=metaword_ids['metaword_client_id'],
                                            metaword_id=metaword_ids['metaword_id'])

    for field in 'entries', 'transcriptions', 'translations', 'sounds', 'paradigms', 'etymology_tags':
        metaword_ids[field] = []
        #print(vars(metaword))
        if field in vars(metaword):
            for obj in vars(metaword)[field]:
                obj_description = dict()
                obj_description['id'] = obj.id
                obj_description['client_id'] = obj.client_id
                if 'creation_time' in obj_description:
                    obj_description['creation_time'] = str(obj.creation_time)
                obj_description['author'] = str(obj.client.User.name)
                if field in ['entries', 'transcriptions', 'translations']:
                    obj_description['content'] = obj.content
                elif field in ['sounds']:
                    obj_description['url'] = request.route_url('api_metaword_sound_get',
                                                               dictionary_client_id=metaword_ids['dictionary_client_id'],
                                                               dictionary_id=metaword_ids['dictionary_id'],
                                                               metaword_client_id=obj.metaword_client_id,
                                                               metaword_id=obj.metaword_id,
                                                               sound_client_id=obj.client_id,
                                                               sound_id=obj.id)
                elif field in ['paradigms']:
                    obj_description['paradigms'] = []
                    for paradigm in obj.paradigms:
                        obj_description['paradigms'].append(traverse_paradigm(paradigm,
                                                                              metaword.dictionary_client_id,
                                                                              metaword.dictionary_id,
                                                                              request
                                                                              ))
                elif field in ['etymology_tags']:
                    if obj.content:
                        obj_description['content'] = DBSession.query(WordEtymologyTag).filter_by(content=obj.content).count()
                    else:
                        obj_description['content'] = 0
                    obj_description['url'] = request.route_url('api_etymology_get',
                                                               dictionary_client_id=metaword_ids['dictionary_client_id'],
                                                               dictionary_id=metaword_ids['dictionary_id'],
                                                               metaword_client_id=obj.metaword_client_id,
                                                               metaword_id=obj.metaword_id)

                metaword_ids[field].append(obj_description)
    return metaword_ids


def forbidden_view(request):
    # do not allow a user to login if they are already logged in
    if authenticated_userid(request):
        return HTTPForbidden()

    loc = request.route_url('login', _query=(('next', request.path),))
    return HTTPFound(location=loc)


@view_config(route_name='register/validate', renderer='json', request_method='POST')
def validate(request):
    try:
        param = request.matchdict.get('param')
        #print(param)
        value = request.POST.getone(param)
        if param == 'email':
            dbentry = DBSession.query(Email).filter_by(email=value).first()
            if dbentry:
                raise CommonException("The user with this email is already registered")
        elif param == 'login':
            dbentry = DBSession.query(User).filter_by(login=value).first()
            if dbentry:
                raise CommonException("The user with this login is already registered")
        else:
            raise KeyError

        request.response.status = HTTPOk.code
        return {'status': request.response.status}

    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}


@view_config(route_name='home', renderer='templates/home.pt')
def main_page(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/home.pt', variables, request=request)


@view_config(route_name='register', renderer='templates/register.pt', request_method='GET')
def register_get(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/register.pt', variables, request=request)


@view_config(route_name='register', renderer='json', request_method='POST')
def register_post(request):
    try:
        login = request.POST.getone('login')
        name = request.POST.getone('name')
        email = request.POST.getone('email')
        password = request.POST.getone('password')

        if DBSession.query(User).filter_by(login=login).first():
            raise CommonException("The user with this login is already registered")
        if DBSession.query(Email).filter_by(email=email).first():
            raise CommonException("The user with this email is already registered")
        new_user = User(login=login, name=name, signup_date=datetime.datetime.utcnow(), is_active=True)
        pwd = Passhash(password=password)
        email = Email(email=email)
        new_user.password = pwd
        new_user.email.append(email)
        DBSession.add(new_user)
        DBSession.flush()

        # adding user to needed groups
        for group in group_filter(DBSession, 'can_create_dictionaries', 'ANY'):
            new_user.groups.append(group)

        for group in group_filter(DBSession, 'can_create_languages', 'ANY'):
            new_user.groups.append(group)

        for group in group_filter(DBSession, 'can_edit_languages', 'ANY'):
            new_user.groups.append(group)

        for group in group_filter(DBSession, 'can_create_organizations', 'ANY'):
            new_user.groups.append(group)

        return login_post(request)

    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}


@view_config(route_name='login', renderer='templates/login.pt', request_method='GET')
def login_get(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/login.pt', variables, request=request)


@view_config(route_name='login', renderer='json', request_method='POST')
def login_post(request):
    next = request.params.get('next') or request.route_url('dashboard')
    login = request.POST.get('login', '')
    password = request.POST.get('password', '')

    user = DBSession.query(User).filter_by(login=login).first()
    if user and user.check_password(password):
        client = Client(user_id=user.id)
        user.clients.append(client)
        DBSession.add(client)
        DBSession.flush()
        headers = remember(request, principal=client.id)
        return HTTPFound(location=next, headers=headers)
    return HTTPUnauthorized(location=request.route_url('login'))


@view_config(route_name='logout', renderer='json')
def logout_any(request):
    next = request.params.get('next') or request.route_url('home')
    headers = forget(request)
    return HTTPFound(location=next, headers=headers)


@view_config(route_name='dashboard', renderer='templates/dashboard.pt', request_method='GET')
def dashboard(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/dashboard.pt', variables, request=request)


@view_config(route_name='create_dictionary_page', renderer='templates/create_dictionary_page.pt', request_method='GET')
def create_dictionary_get(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/create_dictionary_page.pt', variables, request=request)

@view_config(route_name='view_page', renderer='templates/view_page.pt', request_method='GET')
def view_page_get(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/view_page.pt', variables, request=request)


@view_config(route_name='create_dictionary_post', renderer='json', request_method='POST')
def create_dictionary_post(request):
    try:
        variables = {'auth': authenticated_userid(request)}
        name = request.POST.getone('dictionary_name')
        dialeqt_id = None
        try:
            dialeqt_id = request.POST.getone('dialeqt_id')
        except KeyError:
            pass

        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()

        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        if dialeqt_id:
            dictionary = DBSession.query(Dictionary).filter_by(imported_hash=dialeqt_id).first()

#        if dictionary:
#            raise CommonException("This dictionary is already present in the system. You can not import it twice for now.")

        dictionary = Dictionary(id=len(client.dictionaries)+1, client_id=request.authenticated_userid, name=name, state="WiP", imported_hash=dialeqt_id)
        DBSession.add(dictionary)
        DBSession.flush()
        subject = str(dictionary.id)+":"+str(client.id)
        user.groups.append(add_child_group(DBSession, 'can_change_dictionary_info', subject=subject))
        user.groups.append(add_child_group(DBSession, 'can_invite_collaborators', subject=subject))
        user.groups.append(add_child_group(DBSession, 'can_add_words', subject=subject))
        user.groups.append(add_child_group(DBSession, 'can_delete_words', subject=subject))
        user.groups.append(add_child_group(DBSession, 'can_set_defaults', subject=subject))
        user.groups.append(add_child_group(DBSession, 'can_publish', subject=subject))

        request.response.status = HTTPOk.code
        return {'status': request.response.status,
                'dictionary_id': dictionary.id,
                'dictionary_client_id': dictionary.client_id,
                'edit_url': request.route_url('edit_dictionary', dictionary_client_id=dictionary.client_id, dictionary_id=dictionary.id)}

    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'status': request.response.status, 'error': str(e)}

@view_config(route_name="own_dictionaries_list", renderer='json', request_method='GET')
def own_dictionaries_list(request):
    variables = {'auth': authenticated_userid(request)}
    try:
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        dictionaries_list = []
        for client in user.clients:
            for dictionary in client.dictionaries:
                dictionaries_list.append({'id': dictionary.id,
                                          'client_id': dictionary.client_id,
                                          'name': dictionary.name,
                                          'edit_url': request.route_url('edit_dictionary',
                                                                        dictionary_client_id=dictionary.client_id,
                                                                        dictionary_id=dictionary.id),
                                          'view_url': request.route_url('view_dictionary',
                                                                        dictionary_client_id=dictionary.client_id,
                                                                        dictionary_id=dictionary.id),
                                          'stats': form_dictionary_stats(dictionary.id, dictionary.client_id)})
        request.response.status = HTTPOk.code
        return {'status': request.response.status, 'dictionaries': dictionaries_list}
    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}


@view_config(route_name="create_language_page", renderer='templates/create_language.pt', request_method='GET')
def create_language_get(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/create_language.pt', variables, request=request)

@view_config(route_name="create_language", renderer='json', request_method='POST')
def create_language_post(request):
    return {'status': 200}


@view_config(route_name="edit_dictionary", renderer="templates/edit_dictionary.pt", request_method='GET')#, permission='edit')
def edit_dictionary(request):
    dictionary_client_id = request.matchdict['dictionary_client_id']
    dictionary_id = request.matchdict['dictionary_id']
    variables = {'auth': authenticated_userid(request), 'id': dictionary_id, 'client_id': dictionary_client_id}
    if DBSession.query(Dictionary).filter_by(id=dictionary_id, client_id=dictionary_client_id).first():
        return render_to_response("templates/edit_dictionary.pt", variables, request=request)
    else:
        raise HTTPNotFound




# @view_config(route_name="get_metawords_for_edit", renderer="json", request_method='GET')
# def get_metawords(request):
#     dictionary_client_id = request.matchdict['dictionary_client_id']
#     dictionary_id = request.matchdict['dictionary_id']
#     dictionary = DBSession.query(Dictionary).filter_by(id=dictionary_id, client_id=dictionary_client_id).first()
#     if dictionary:
#         metawords_list = []
#         for metaword in dictionary.metawords:
#             transcription_list = []
#             for item in metaword.transcriptions:
#                 transcription_list.append({'metaword_id': item.metaword_id,
#                                            'metaword_client_id': item.metaword_client_id,
#                                            'id': item.id,
#                                            'client_id': item.client_id,
#                                            'content': item.content,
#                                            'marked_to_delete': item.marked_to_delete
#                                            })
#             translation_list = []
#             for item in metaword.translations:
#                 translation_list.append({'metaword_id': item.metaword_id,
#                                          'metaword_client_id': item.metaword_client_id,
#                                          'id': item.id,
#                                          'client_id': item.client_id,
#                                          'content': item.content,
#                                          'marked_to_delete': item.marked_to_delete
#                                          })
#
#
#             sounds_list = []
#             for item in metaword.sounds:
#                 sounds_list.append({'metaword_id': item.metaword_id,
#                                     'metaword_client_id': item.metaword_client_id,
#                                     'id': item.id,
#                                     'client_id': item.client_id,
#                                     'content': item.id,
#                                     'marked_to_delete': item.marked_to_delete
#                 })
#
#             item = {'metaword_id': metaword.id,
#                     'metaword_client_id': metaword.client_id,
#                     'transcriptions': transcription_list,
#                     'translations': translation_list,
#                     'sounds': sounds_list
#                     }
#             metawords_list.append(item)
#         import pprint
#         pp = pprint.PrettyPrinter()
#         pp.pprint(metawords_list)
#         return metawords_list
#     else:
#         request.response.status = HTTPNotFound.code
#         return {'status': request.response.status, 'error': str("Dictionary not found")}

    # config.add_route('view_dictionary',
    #                  'dictionaries/{client_id}/{dictionary_id}/view',
    #                  factory=DummyDeny)
    # config.add_route('view_metaword',
    #                  'dictionaries/{client_id}/{dictionary_id}/metawords/{metaword_client_id}/{metaword_id}/view',
    #                  factory=DummyDeny)

@view_config(route_name="view_dictionary", renderer="templates/view_dictionary.pt", request_method="GET")
def view_dictionary(request):
    dictionary_client_id = request.matchdict['dictionary_client_id']
    dictionary_id = request.matchdict['dictionary_id']
    variables = {'auth': authenticated_userid(request), 'id': dictionary_id, 'client_id': dictionary_client_id}
    if DBSession.query(Dictionary).filter_by(id=dictionary_id, client_id=dictionary_client_id).first():
        return render_to_response("templates/view_dictionary.pt", variables, request=request)
    else:
        raise HTTPNotFound


@view_config(route_name="api_metaparadigm_post_batch", renderer="json", request_method="POST")
def api_metaparadigm_post_batch(request):
    #print(request.matchdict)
    try:
        metaword_object = DBSession.query(MetaWord).filter_by(id=request.matchdict['metaword_id'],
                                                              client_id=request.matchdict['metaword_client_id']).first()
        if not metaword_object:
            raise CommonException("No metaword object with such ids: metaword_id" +
                                  str(request.matchdict['metaword_id']) +
                                  ", metaword_client_id: " +
                                  str(request.matchdict['metaword_client_id']))

        metaparadigm = request.json_body
        metaparadigm_id = metaparadigm.get('metaparadigm_id')
        metaparadigm_client_id = metaparadigm.get('metaparadigm_client_id')
        if bool(metaparadigm_id) != bool(metaparadigm_client_id):
            raise CommonException("Bad request: missing one of metaparadigm identifiers")

        client = DBSession.query(Client).filter_by(id=authenticated_userid(request)).first()

        if not client or client.id != authenticated_userid(request):
            raise CommonException("It seems that you are trying to trick the system. Don't!")

        if not bool(metaparadigm_id) and not bool(metaparadigm_client_id):
            metaparadigm_object = MetaParadigm(id=DBSession.query(MetaParadigm).count()+1,
                                       client_id=client.id,
                                       client=client,
                                       marked_to_delete=False)
        else:
            metaparadigm_object = DBSession.query(MetaWord).filter_by(id=metaparadigm_id,
                                                                  client_id=metaparadigm_client_id).first()

        transcriptions = metaparadigm.get('transcriptions')
        translations = metaparadigm.get('translations')
        entries = metaparadigm.get('entries')
        sounds = metaparadigm.get('sounds')

        if transcriptions:
            for item in transcriptions:
                metaparadigm_object.transcriptions.append(
                    produce_subtypes(ParadigmTranscription, client, {'content': item.get('content')})
                )

        if translations:
            for item in translations:
                metaparadigm_object.translations.append(
                    produce_subtypes(ParadigmTranslation, client, {'content': item.get('content')})
                )
        if entries:
            for item in entries:
                metaparadigm_object.entries.append(
                    produce_subtypes(ParadigmEntry, client, {'content': item.get('content')})
                )
        if sounds:
            for item in sounds:
                if not item:
                    raise CommonException('No sound is attached, retry')
                metaparadigm_object.sounds.append(
                    produce_subtypes(ParadigmSound, client, {'content': item.get('content'),
                                                                  'mime': item.get('mime'),
                                                                  'name': item.get('name'),
                                                                  'markups': item.get('markups')})
                )

        metaword_object.paradigms.append(metaparadigm_object)
        DBSession.add(metaword_object)
        DBSession.flush()

        response = traverse_metaword(metaword_object, request)
        response['status'] = 200
        return response

    except CommonException as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': "Bad request: " + str(e)}


@view_config(route_name="api_metaword_post_batch", renderer="json", request_method="POST")
def api_metaword_post_batch(request):
    #print(request.matchdict)
#    dictionary_client_id = request.matchdict['client_id']
#    dictionary_id = request.matchdict['dictionary_id']
    try:
        dictionary_object = DBSession.query(Dictionary).filter_by(id=request.matchdict['dictionary_id'],
                                                                  client_id=request.matchdict['dictionary_client_id']).first()
        metaword = request.json_body
        metaword_id = metaword.get('metaword_id')
        metaword_client_id = metaword.get('metaword_client_id')
        if bool(metaword_id) != bool(metaword_client_id):
            raise CommonException("Bad request: missing one of metaword identifiers")

        client = DBSession.query(Client).filter_by(id=authenticated_userid(request)).first()
        if not client or client.id != authenticated_userid(request):
            raise CommonException("It seems that you are trying to trick the system. Don't!")
        if not bool(metaword_id) and not bool(metaword_client_id):
            # we are getting all metawords for purpose -- for correct numeration in client applications
            metaword_object = MetaWord(id=DBSession.query(MetaWord).count()+1,
                                       client_id=client.id,
                                       client=client,
                                       marked_to_delete=False)
        else:
            metaword_object = DBSession.query(MetaWord).filter_by(id=metaword_id,
                                                                  client_id=metaword_client_id).first()
        transcriptions = metaword.get('transcriptions')
        translations = metaword.get('translations')
        entries = metaword.get('entries')
        sounds = metaword.get('sounds')
        etymology_tags = metaword.get('etymology_tags')

        if transcriptions:
            for item in transcriptions:
                metaword_object.transcriptions.append(
                    produce_subtypes(WordTranscription, client, {'content': item.get('content')})
                )

        if translations:
            for item in translations:
                metaword_object.translations.append(
                    produce_subtypes(WordTranslation, client, {'content': item.get('content')})
                )
        if entries:
            for item in entries:
                metaword_object.entries.append(
                    produce_subtypes(WordEntry, client, {'content': item.get('content')})
                )
        if sounds:
            for item in sounds:
                if not item:
                    raise CommonException('No sound is attached, retry')
                metaword_object.sounds.append(
                    produce_subtypes(WordSound, client, {'content': item.get('content'),
                                                                  'mime': item.get('mime'),
                                                                  'name': item.get('name'),
                                                                  'markups': item.get('markups')})
                )
                DBSession.flush()
        if etymology_tags:
            for item in etymology_tags:
                if not item:
                    raise CommonException('No tag is supplied, retry')
                metaword_object.etymology_tags.append(
                    produce_subtypes(WordEtymologyTag, client, {'content': item.get('content')})
                )

        dictionary_object.metawords.append(metaword_object)
        DBSession.add(dictionary_object)
        DBSession.flush()

        response = traverse_metaword(metaword_object, request)
        response['status'] = 200

        return response
    except CommonException as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str("Bad request")}


@view_config(route_name='api_metaword_get', renderer='json', request_method='GET')
def api_metaword_get(request):
    word_object = DBSession.query(MetaWord).options(subqueryload('*')).filter_by(
        id=request.matchdict['metaword_id'],
        client_id=request.matchdict['metaword_client_id']).first()

    if word_object:
        return traverse_metaword(word_object, request)
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such word in the system")}

@view_config(route_name='api_metaword_get_batch', renderer='json', request_method='GET')
def api_metaword_get_batch(request):
    offset = 0
    limit = 10000
    if 'offset' in request.params:
        offset = int(request.params['offset'])
    if 'size' in request.params:
        limit = int(request.params['size'])

    dictionary = DBSession.query(MetaWord).filter_by(
        dictionary_id=request.matchdict['dictionary_id'],
        dictionary_client_id=request.matchdict['dictionary_client_id']).options(joinedload(MetaWord.transcriptions),
                                                                                joinedload(MetaWord.translations),
                                                                                joinedload(MetaWord.etymology_tags),
                                                                                joinedload(MetaWord.entries),
                                                                                joinedload(MetaWord.sounds),
                                                                                joinedload(MetaWord.paradigms)).slice(offset, offset+limit)

    word_list = []
    for word in dictionary:
        word_list.append(traverse_metaword(word, request))
    return word_list


@view_config(route_name='api_metaword_sound_get', request_method='GET')
def api_metaword_sound_get(request):

    sound_object = DBSession.query(WordSound).options(subqueryload('*')).filter_by(
        id=request.matchdict['sound_id'],
        client_id=request.matchdict['sound_client_id']).first()
    if sound_object:
        return FileResponse(object_file_path(sound_object))
    else:
        raise HTTPNotFound


@view_config(route_name='api_metaparadigm_sound_get', request_method='GET')
def api_metaparadigm_sound_get(request):
    sound_object = DBSession.query(ParadigmSound).options(subqueryload('*')).filter_by(
        id=request.matchdict['sound_id'],
        client_id=request.matchdict['sound_client_id']).first()
    if sound_object:
        return FileResponse(object_file_path(sound_object))
    else:
        raise HTTPNotFound


@view_config(route_name='api_etymology_get', renderer='json', request_method='GET')
def api_etymology_get(request):
    word_object = DBSession.query(MetaWord).options(subqueryload('*')).filter_by(
        id=request.matchdict['metaword_id'],
        client_id=request.matchdict['metaword_client_id']).first()
    if word_object:
        connected_words = []
        for tag in word_object.etymology_tags:
            print(tag)
            connected_words_objects = DBSession.query(MetaWord).options(subqueryload('*')).filter(
                MetaWord.etymology_tags.any(content=tag.content)
                )
#            connected_words = [traverse_metaword(word_object, request)]
            for word in connected_words_objects:
                connected_words.append(traverse_metaword(word, request))
        return connected_words
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such word in the system")}


@view_config(route_name='api_corpora_get', renderer='json', request_method='GET')
def api_corpora_get(request):
    response = {"corpus_id":1,"corpus_client_id":1,"texts":[{"text_id":1,"client_id":1,"text_titles":[{"lang":"ru","content":"Ансамбль"}],"text_comments":[{"lang":"ru","content":"Текст записан С.Ю. Толдовой и Д.А. Паперно в июне 2004г. от К.А. Невоструевой (д. Жувам), расшифрован Д. Залмановым и А.А. Глуховой с С.С. Сабрековой (д. Шамардан), отглоссирован О.Л. Бирюк"}],"paragraphs":[{"phrases":[{"words":[{"items":[{"type":"txt","content":"beš’ermanskoj","lang":"udm-Latn-RU-fonipa-x-emic"},{"type":"pos","lang":"ru","content":"прил"},{"type":"lingvodoc_metaword","url":"http://192.168.23.130:6543/dictionaries/1/1/metawords/1/1"}]},{"items":[{"type":"txt","content":"beš’ermanskoj2222","lang":"udm-Latn-RU-fonipa-x-emic"},{"type":"pos","lang":"ru","content":"прил"}]}],"translations":[{"lang":"ru","content":"Появилось бесермянское общество, его создал Сабреков Валерьян Фёдорович."}]}]}]}]}
    return response


def form_dictionary_stats(dictionary_id, dictionary_client_id):
    quantity = dict()
    quantity['metawords'] = DBSession.query(MetaWord) \
        .options(noload("*")) \
        .filter_by(dictionary_id=dictionary_id,
                   dictionary_client_id=dictionary_client_id) \
        .count()

    quantity['metaparadigms'] = DBSession.query(MetaParadigm) \
        .options(noload("*")) \
        .filter(MetaParadigm.MetaWord.has(dictionary_id=dictionary_id),
                MetaParadigm.MetaWord.has(dictionary_client_id=dictionary_client_id)) \
        .count()
    return quantity


@view_config(route_name='dictionary_stats', renderer='json', request_method='GET')
def dictionary_stats(request):
    return form_dictionary_stats(request.matchdict['dictionary_id'], request.matchdict['dictionary_client_id'])



#@view_config(route_name='login', renderer='')
# def login(request):
#     """
#     user authentication on-site ('user-to-project').
#     :param request:
#     :return:
#     """
#
#     return
#
#
# #@view_config(route_name='logout')
# def logout(request):
#     """
#     user logout button on-site ('api')
#     :param request:
#     :return:
#     """
#     return
#
#
# #@view_config(route_name='register')
# def register(request):
#     """
#     user registration page on-site ('user-to-project').
#     :param request:
#     :return:
#     """
#     return
#
#
# #@view_config(route_name='acquire_client_key')
# def acquire_client_key(request):
#     """
#     get key for client program ('client-to-server')
#     :param request:
#     :return:
#     """
#     return
#
#
# #@view_config(route_name='dictionaries.list', renderer='json', permission='view')
# def list_dictionaries(request):
#     """
#     list existing dictionaries ('user-to-project')
#     :param request: filter=all,approved,pending
#     :return:
#     """
#     return {'Dicts': [request.context.dictionaries.first()]}
#
#
# #@view_config(route_name='dictionary')
# def view_dictionary(request):
#     return


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

