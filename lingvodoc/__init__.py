from pyramid.config import Configurator
from sqlalchemy import engine_from_config
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

from .models import (
    DBSession,
    Base,
    )

from .acl import (
    groupfinder
)

from .acl import DummyDeny

from configparser import ConfigParser

def configure_routes(config):
    """
    This function registers views from .views for pyramid event loop. Actually all listed items here is our
    'site-map' for:
    1) web-views (html+javascript) - will be marked as 'web-view'
    2) REST API - will be marked as 'API'
    3) internal calls for frontend (in most cases it's API but not always). If it's not API part, will be marked
       separately. Will be marked as 'internal'
    """

    # web-view #GET
    config.add_route(name='home', pattern='/')

    # web-view #GET && POST
    # registration page
    config.add_route(name='signup', pattern='/signup')

    # internal #POST
    # validation for registration parameters: unique email, unique login
    config.add_route(name='signup/validate', pattern='/signup/validate/{param}')

    # web-view #GET
    # login page
    config.add_route(name='login', pattern='/login')

    # API #POST
    # this is the same operation as login - but params are sent via json
    config.add_route(name='signin', pattern='/signin')  # 100% ready
    config.add_route(name='cheatlogin', pattern='/cheatlogin')

    # web-view #POST
    config.add_route(name='logout', pattern='/logout')

    # web-view #GET
    config.add_route(name='dashboard', pattern='/dashboard')

    # web-view #GET
    config.add_route(name='profile', pattern='/profile')

    # web-view #GET
    config.add_route(name='languages', pattern='/languages/map')

    # API #GET && PUT && DELETE
    # Gets/puts info about language
    config.add_route(name='language', pattern='/language/{client_id}/{object_id}',
                     factory='lingvodoc.models.LanguageAcl')  # 100% ready

    # API #POST
    # Create language
    config.add_route(name='create_language', pattern='/language',
                     factory='lingvodoc.models.LanguageAcl')  # 100% ready

    # API #GET
    # view languages list
    config.add_route(name='get_languages', pattern='/languages')

    # API #GET
    # Dictionaries list. The following filters should be supported:
    # 1. Filter by:
    #    a) User created
    #    b) User participated
    #    c) Organization participated
    #    d) By language group (all the languages that point to the given one). Need to build a lang tree here.
    #    e) Maps location (coordinates) +- radius in kilometers
    config.add_route('dictionaries', 'dictionaries')  # 100% ready

    # API #GET
    # Perspective list
    # 1. Filter by:
    #    a) template
    #    b) state
    config.add_route('all_perspectives', '/perspectives')
    config.add_route('users', '/users')

    # web-view
    config.add_route(name='new_dictionary', pattern='/create_dictionary')

    # web-view
    config.add_route(name='edit_dictionary_properties', pattern='/dictionary/{client_id}/{object_id}/edit')

    # API #POST
    # Creating dictionary
    config.add_route(name='create_dictionary', pattern='/dictionary',
                     factory='lingvodoc.models.DictionaryAcl')  # 100% ready

    # API #GET && PUT && DELETE
    # Gets/puts info about dictionary (name/additional authors/etc)
    config.add_route(name='dictionary', pattern='/dictionary/{client_id}/{object_id}',
                     factory='lingvodoc.models.DictionaryAcl')  # 100% ready


    # web-view
    config.add_route(name='organizations', pattern='/organizations')


    # API #GET
    config.add_route(name='organization_list', pattern='/organization_list')


    # API #POST
    # Creating organization
    config.add_route(name='create_organization', pattern='/organization',
                     factory='lingvodoc.models.OrganizationAcl')  # 100% ready

    # API #GET && PUT && DELETE
    # Gets/puts info about organization
    config.add_route(name='organization', pattern='/organization/{organization_id}',
                     factory='lingvodoc.models.OrganizationAcl')

    # API #GET && POST && DELETE
    # Gets, creates and deletes roles related to dictionary (for now: who can create and modify perspectives)
    # Request format: {[user id: <user_id>, role_name: <role_name>]}. Get request is empty and returns list of roles.
    config.add_route(name='dictionary_roles',
                     pattern='/dictionary/{client_id}/{object_id}/roles',
                     factory='lingvodoc.models.DictionaryRolesAcl')  # 100% ready

    # API #GET && PUT
    # Change visibility state for dictionary. States are: 'frozen', 'WiP', 'published', 'merging'
    config.add_route(name='dictionary_status',
                     pattern='/dictionary/{client_id}/{object_id}/state',
                     factory='lingvodoc.models.DictionaryAcl')  # 100% ready

    # API #GET && PUT && DELETE
    # Gets/puts info about perspective.
    # Future note: PUT & DELETE should work on-server only.
    config.add_route(name='perspective',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}/'
                             'perspective/{perspective_client_id}/{perspective_id}',
                     factory='lingvodoc.models.PerspectiveAcl')  # 100% ready

    # API #POST
    # Creating perspective
    config.add_route(name='create_perspective',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}/'
                             'perspective',
                     factory='lingvodoc.models.PerspectiveCreateAcl')  # 100% ready

    # API #GET
    # list perspectives
    config.add_route(name='perspectives',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}/'
                             'perspectives')

    # API #GET && POST && DELETE
    # Gets, creates and deletes roles related to dictionary (for now: who can create entities, view entities, create
    # publisher-entities)
    # Request format: {[user id: <user_id>, role_name: <role_name>]}. Get request is empty and returns list of
    # roles and users that they are assigned.
    config.add_route(name='perspective_roles',
                     pattern='/dictionary/{client_id}/{object_id}/'
                             'perspective/{perspective_client_id}/{perspective_id}/roles',
                     factory='lingvodoc.models.PerspectiveRolesAcl')  # 100% ready

    # API #GET && PUT
    # Get or change visibility state for perspective. States are: 'frozen', 'WiP', 'published'
    config.add_route(name='perspective_status',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                     '/perspective/{perspective_client_id}/{perspective_id}/status',
                     factory='lingvodoc.models.PerspectiveAcl')  # 100% ready

    # API #GET && POST && DELETE
    # Configuring columns in perspective table.
    # Example response:
    #   { 'fields: [ {'entity_type': 'protoform', 'data_type': 'text', 'status': 'enabled'},
    #                {'entity_type': 'transcription', 'data_type': 'text', 'status': 'enabled'},
    #                {'entity_type': 'translation', 'data_type': 'text', 'status': 'enabled'},
    #                {'entity_type': 'sound', 'data_type': 'sound', 'status': 'enabled', 'contains':
    #                  [{'entity_type': 'praat', 'data_type': 'markup', 'status': 'enabled'}]
    #                },
    #                {'entity_type': 'paradigm_protoform', 'data_type': 'text', 'status': 'enabled', 'group': 'paradigm'},
    #                {'entity_type': 'paradigm_transcription', 'data_type': 'text', 'status': 'enabled', 'group': 'paradigm'},
    #                {'entity_type': 'paradigm_translation', 'data_type': 'text', 'status': 'enabled', 'group': 'paradigm'},
    #                {'entity_type': 'paradigm_sound', 'data_type': 'sound', 'status': 'enabled', 'contains':
    #                  [{'entity_type': 'paradigm_praat', 'data_type': 'markup', 'status': 'enabled'}]
    #                },
    #                {'entity_type': 'etymology', 'data_type': 'grouping_tag', 'status': 'enabled'}
    #              ]
    #   }
    # Request format is the same:
    #  {fields: [{entity_type: <entity_type>, data_type:<text|img|sound|markup|grouping_tag>,
    #             status: <enabled|disabled>}, contains: [{}], group: <grouping_button_localization_str>]
    config.add_route(name='perspective_fields',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                             '/perspective/{perspective_client_id}/{perspective_id}/fields',
                     factory='lingvodoc.models.PerspectiveAcl')  # 100% ready

    # API #POST
    # should be done with standard form enctype="multipart/form-data"
    config.add_route(name="upload_user_blob",
                     pattern="/blob")

    # seems to be redundant
    # API #GET
    # no params, returns file
    #config.add_route(name="get_user_blob",
    #                 pattern="/blobs/{client_id}/{object_id}")
    # API #GET
    # no params, lists only own blobs
    config.add_route(name="list_user_blobs",
                     pattern="/blobs/")

# TODO: LOCALES!
    # API #GET && DELETE
    # [{'entity_type': '<entity_type>', 'parent_object_id': <parent_object_id>, 'parent_client_id': <parent_client_id>,
    # 'content': <'content'>, 'locale_id': <locale_id>}]
    config.add_route(name='get_level_one_entity', pattern='/leveloneentity/{client_id}/{object_id}',
                     factory='lingvodoc.models.PerspectiveEntityOneAcl')  # ready 100%
    config.add_route(name='get_level_one_entity_indict', pattern='/dictionary/'
                                                                 '{dictionary_client_id}/{dictionary_object_id}'
                                                                 '/perspective/'
                                                                 '{perspective_client_id}/{perspective_id}/'
                                                                 'lexical_entry/'
                                                                 '{lexical_entry_client_id}/{lexical_entry_object_id}/'
                                                                 'leveloneentity/'
                                                                 '{client_id}/{object_id}',
                     factory='lingvodoc.models.PerspectiveEntityOneAcl')  # ready 100%

    config.add_route(name='get_level_two_entity', pattern='/leveltwoentity/{client_id}/{object_id}',
                     factory='lingvodoc.models.PerspectiveEntityTwoAcl')  # ready, not tested
    config.add_route(name='get_level_two_entity_indict', pattern='/dictionary/'
                                                                 '{dictionary_client_id}/{dictionary_object_id}'
                                                                 '/perspective/'
                                                                 '{perspective_client_id}/{perspective_id}/'
                                                                 'lexical_entry/'
                                                                 '{lexical_entry_client_id}/{lexical_entry_object_id}/'
                                                                 'leveloneentity/'
                                                                 '{leveloneentity_client_id}/{leveloneentity_object_id}/'
                                                                 'leveltwoentity/'
                                                                 '{client_id}/{object_id}',
                     factory='lingvodoc.models.PerspectiveEntityTwoAcl')  # ready, not tested

    # API #GET && DELETE
    # {entity_type: <entity_type>, content: <tag>, connections: [{object_id: <obj_id>, client_id: <cl_id>}
    config.add_route(name='get_group_entity', pattern='/group_entity/{client_id}/{object_id}')  # ready, not tested

    # API #GET
    # GET parameter: entity_type = <type> (e.g: "etymology")
    config.add_route(name='get_connected_words', pattern='/lexical_entry/{client_id}/{object_id}/connected')
    config.add_route(name='get_connected_words_indict', pattern='/dictionary/'
                                                                '{dictionary_client_id}/{dictionary_object_id}'
                                                                '/perspective/'
                                                                '{perspective_client_id}/{perspective_id}/'
                                                                'lexical_entry/'
                                                                '{client_id}/{object_id}/'
                                                                'connected')

    # API #POST (TODO: change to PATCH method later)
    # {entity_type: <entity_type>, content: <tag>, connections: [{object_id: <obj_id>, client_id: <cl_id>}
    config.add_route(name='add_group_entity', pattern='/group_entity')  # ready, not tested
    config.add_route(name='add_group_indict', pattern='/dictionary/'
                                                      '{dictionary_client_id}/{dictionary_object_id}'
                                                      '/perspective/'
                                                      '{perspective_client_id}/{perspective_id}/'
                                                      'lexical_entry/'
                                                      'connect')  # ready, not tested

    # API #GET
    # like
    config.add_route(name='basic_search', pattern='/basic_search')


    # API #POST
    # no parameters needed.
    # ids are returned.
    config.add_route(name='create_lexical_entry', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                          '/perspective/{perspective_client_id}/{perspective_id}/'
                                                          'lexical_entry',
                     factory='lingvodoc.models.LexicalEntriesEntitiesAcl')  # ready, tested

    config.add_route(name='create_lexical_entry_bulk', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                               '/perspective/{perspective_client_id}/{perspective_id}/'
                                                               'lexical_entries',
                     factory='lingvodoc.models.LexicalEntriesEntitiesAcl')  # ready

    # API #POST
    # {'entity_type': <entity_type>, 'content': <content>, 'locale_id': <locale_id>, 'metadata': <metadata>}
    # ids are returned
    config.add_route(name='create_level_one_entity', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                      '/perspective/{perspective_client_id}/{perspective_id}/'
                                                      'lexical_entry/{lexical_entry_client_id}/'
                                                      '{lexical_entry_object_id}/leveloneentity',
                     factory='lingvodoc.models.LexicalEntriesEntitiesAcl')  # ready, tested

    config.add_route(name='create_entities_bulk', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                          '/perspective/{perspective_client_id}/{perspective_id}/entities',
                     factory='lingvodoc.models.LexicalEntriesEntitiesAcl')

    # API #POST
    # {'entity_type': <entity_type>, 'content': <content>, 'locale_id': <locale_id>, 'metadata': <metadata>}
    # ids are returned
    config.add_route(name='create_level_two_entity', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                   '/perspective/{perspective_client_id}/{perspective_id}/'
                                                   'lexical_entry/{lexical_entry_client_id}/'
                                                   '{lexical_entry_object_id}/leveloneentity/{level_one_client_id}/'
                                                   '{level_one_object_id}/leveltwoentity',
                     factory='lingvodoc.models.LexicalEntriesEntitiesAcl')  # ready, not tested

    # API #GET
    # params: start_from=M, count=N, sort_by=<entity_type>
    config.add_route(name='lexical_entries_all', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                         '/perspective/{perspective_client_id}/{perspective_id}/all',
                     factory='lingvodoc.models.PerspectiveLexicalViewAcl')  # filter not ready

    config.add_route(name='lexical_entries_all_count', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                               '/perspective/{perspective_client_id}/{perspective_id}/all_count',
                     factory='lingvodoc.models.PerspectiveLexicalViewAcl')

    config.add_route(name='lexical_entries_published', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                               '/perspective/{perspective_client_id}/{perspective_id}/published',
                     factory='lingvodoc.models.PerspectivePublishAcl')  # filter not ready

    config.add_route(name='lexical_entries_published_count', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                               '/perspective/{perspective_client_id}/{perspective_id}/published_count',
                     factory='lingvodoc.models.PerspectivePublishAcl')  # filter not ready
    # made only return list of ids, because another route fol full info exist

    # API #GET, DELETE
    # all children
    config.add_route(name='lexical_entry', pattern='/lexical_entry/{client_id}/{object_id}',
                     factory='lingvodoc.models.LexicalViewAcl')  # ready, not tested
    config.add_route(name='lexical_entry_in_perspective', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                                  '/perspective/{perspective_client_id}/{perspective_id}/'
                                                                  'lexical_entry/{client_id}/{object_id}',
                     factory='lingvodoc.models.LexicalViewAcl')
    # API #PATCH
    # Publishers view: this can approve word versions.
    # [{"type": <object_type>, "client_id": <client_id>, "object_id": <object_id>, "enabled": <boolean>}, ]
    config.add_route(name='approve_entity', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                    '/perspective/{perspective_client_id}/{perspective_id}/approve',
                     factory='lingvodoc.models.PerspectivePublishAcl')  # ready, not tested
    config.add_route(name='approve_all', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                    '/perspective/{perspective_client_id}/{perspective_id}/approve_all',
                     factory='lingvodoc.models.PerspectivePublishAcl')  # ready, not tested

    # web-view
    config.add_route(name='edit_dictionary', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                     '/perspective/{perspective_client_id}/{perspective_id}/edit')
    # web-view
    config.add_route(name='view_dictionary', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                     '/perspective/{perspective_client_id}/{perspective_id}/view')
    # web-view
    config.add_route(name='publish_dictionary', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                        '/perspective/{perspective_client_id}/{perspective_id}/publish')

    # Merge can be two kinds:
    #   1. Dictionaries merge
    #   2. Perspectives merge
    # To perform dictionaries merge one (or both) of the dictionaries owners should provide to the other a role
    # "can merge".
    # First kind of merge suggests to merge:
    #   1. dictionaries language
    #   2. dictionaries owners (both become owners)
    #   3. roles for dictionaries: perspective owners, editors, viewers. Basically we suggest to unite existing.
    #
    # After dictionaries merge, all the perspectives are moved to new dictionary.
    #
    # Second kind of merge suggests to perspectives. It's supposed to be in several stages:
    #   1. Prepare stage:
    #       1a. All the perspective fields are united as is (by names). We literally get perspective fields
    #           from first perspective and then from the second. If the names are equal, they are the same. If not,
    #           they could be merged later, after all the steps.
    #       1b. All the rest can be marked as active or not.
    #   2. New perspective is created; here will be merge actually done.
    #   3. Function 'get merge suggestions' tries to merge lexical entries and returns list of tuples with merge
    #      suggestions. Selected as correct suggestions are moved to new perspective with all the dependant objects.
    #      *That means that ids for lexical entry are changed.
    #   4. After all the steps are done and dictionary is marked as "merged" we provide an ability to rename
    #      perspective fiels. This action can not be undone, so it must be done after dictionaries are totally
    #      merged.

    # API #POST
    # Gets a list of two elements exactly. All the checks should be done corresponding to previous comment.
    # { "name": <new_dictionary_name>,
    #   "translation": <new_name_translation>,
    #   "language_client_id": <language_client_id>,
    #   "language_object_id": <language_object_id>,
    #   "dictionaries":
    #   [
    #     {"dictionary_client_id": <first_dictionary_client_id>, "dictionary_object_id": <first_dictionary_object_id>},
    #     {"dictionary_client_id": <second_dictionary_client_id>, "dictionary_object_id": <second_dictionary_object_id>}
    #   ]
    # Returns new dictionary client and object ids.
    config.add_route(name='merge_dictionaries', pattern='/merge/dictionaries')  # not tested

    # API #POST
    # {
    # "dictionary_client_id": <dictionary_client_id>,
    # "dictionary_object_id": <dictionary_object_id>},
    # "name": <new_name>,
    # "translation": <new_name_translation>,
    # "perspectives":
    # [
    #  {"perspective_client_id": <first_perspective_client_id, "perspective_object_id": <first_perspective_object_id>,
    #   "fields": [{"new_type_name":<new_type_name>,
    #               entity_type: <entity_type>, data_type:<text|img|sound|markup|grouping_tag>,
    #               status: <enabled|disabled>}, contains: [{}], group: <grouping_button_localization_str>]},
    #  {"perspective_client_id": <second_perspective_client_id, "perspective_object_id": <second_perspective_object_id>,
    #   "fields": [{"new_type_name":<new_type_name>,
    #               entity_type: <entity_type>, data_type:<text|img|sound|markup|grouping_tag>,
    #               status: <enabled|disabled>}, contains: [{}], group: <grouping_button_localization_str>]}
    # ]
    # }
    # Returns new perspective object and client ids.
    config.add_route(name='merge_perspectives', pattern='/merge/perspectives')

    # API #POST
    # {
    # "perspectives":
    # [
    #  {"perspective_client_id": <first_perspective_client_id, "perspective_object_id": <first_perspective_object_id>},
    #  {"perspective_client_id": <second_perspective_client_id, "perspective_object_id": <second_perspective_object_id>}
    # ]
    # }
    # As a response will be given a list of tuples of the following struct:
    # [
    #   {
    #       "suggestion":
    #       [
    #           {"lexical_entry_client_id": <client_id>, "lexical_entry_object_id": <object_id>)},
    #           {"lexical_entry_client_id": <client_id>, "lexical_entry_object_id": <object_id>)},
    #       ],
    #       "confidence": <float 0-1>
    #   },
    # ]

    config.add_route(name='merge_suggestions', pattern='/merge/suggestions')

    config.add_route(name='merge_suggestions_old', pattern='/merge/suggestionsold/'
        '{dictionary_client_id_1}/{dictionary_object_id_1}/'
        '{perspective_client_id_1}/{perspective_object_id_1}/'
        '{dictionary_client_id_2}/{dictionary_object_id_2}/'
        '{perspective_client_id_2}/{perspective_object_id_2}/'
        '{entity_type_primary}/{threshold}/{entity_type_secondary}/'
        '{levenstein}')

    # API #PATCH
    # {'client_id':<client_id>, 'object_id':<object_id>}  id's of entry where moving to
    config.add_route(name='move_lexical_entry', pattern='/lexical_entry/{client_id}/{object_id}/move',
                     factory='lingvodoc.models.LexicalViewAcl')

    # web-view
    config.add_route(name='merge_master', pattern='/dashboard/merge')

    # API #GET
    # Response example:
    # [{"id": <userid>, "login": <login>, "name": <name>, "intl_name": <international_name>, "userpic": <url_to_userpic>}, ]
    config.add_route(name='dictionary_authors', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}')  # 0% ready
    config.add_route(name='perspective_authors', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                         '/perspective/{perspective_client_id}/{perspective_id}')  # 0% ready

    # API #GET
    # params:
    # object_type = <type>
    # client_id = <client_id>
    # object_id = <object_id>
    config.add_route(name='get_object_info', pattern='/info')  # 0% ready

    # API #GET
    # This methods gets info about user by his client_id
    # client_id = <client_id>
    # Response example:
    # {"id": <userid>, "login": <login>, "name": <name>, "intl_name": <international_name>, "userpic": <url_to_userpic>}
    config.add_route(name='get_user_info', pattern='/user')  # ready, not tested
    # API #GET
    # Returns translations for a list of words for current or default or fallback locale
    # ["translation_string", "translation_string2", ...]
    config.add_route(name='get_translations', pattern='/translations')  # ready, not tested


    # web-view #GET
    config.add_route(name='blob_upload', pattern='/blob_upload')

    # API #POST
    # params:
    # {"blob_client_id": <id>, "blob_object_id": <id>, "parent_client_id": <language_client_id>, "parent_object_id": <language_object_id>}
    config.add_route(name='convert_dictionary', pattern='/convert')


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    from pyramid.config import Configurator
    authentication_policy = AuthTktAuthenticationPolicy('secret_string_that_you_should_change',
                                                        hashalg='sha512', callback=groupfinder)
    authorization_policy = ACLAuthorizationPolicy()
    config_file = global_config['__file__']
    parser = ConfigParser()
    parser.read(config_file)
    #TODO: DANGER
    storage = dict()
    for k, v in parser.items('backend:storage'):
        storage[k] = v
    settings['storage'] = storage
    config = Configurator(settings=settings)
    config.set_authentication_policy(authentication_policy)
    config.set_authorization_policy(authorization_policy)
    config.include('pyramid_chameleon')
    config.add_static_view(settings['storage']['static_route'], path=settings['storage']['path'], cache_max_age=3600)
    config.add_static_view('static', path='lingvodoc:static', cache_max_age=3600)
    configure_routes(config)
    config.add_route('testing', '/testing')
#    config.add_route('example', 'some/route/{object_id}/{client_id}/of/perspective', factory = 'lingvodoc.models.DictAcl')


#    config.add_route('home', '/')
#    config.add_route('login', 'login')
#    config.add_route('logout', 'logout')
#    config.add_route('register', 'register')
#    config.add_route('acquire_client_key', 'acquire_client_key')
#    config.add_route('dictionaries.list', 'dictionaries', factory='lingvodoc.models.DictionariesACL')
#    config.add_route('dictionary', 'dictionary')

#    config.add_route('metaword', 'dictionary/{dictionary_id}/etymology/metaword')



    config.scan('.views')
    return config.make_wsgi_app()
