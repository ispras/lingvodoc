import logging
from configparser import (
    ConfigParser,
    NoSectionError
)

from sqlalchemy import engine_from_config
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

from .models import (
    DBSession,
    Base,
)
from lingvodoc.cache.caching import (
    initialize_cache
)
from .acl import (
    groupfinder
)


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
    config.add_route(name='main', pattern='/')

    # web-view #GET && POST
    # registration page
    config.add_route(name='signup', pattern='/signup')

    # web-view #GET
    # login page
    config.add_route(name='login', pattern='/login')  # tested

    # API #POST
    # this is the same operation as login - but params are sent via json
    config.add_route(name='signin', pattern='/signin')
    config.add_route(name='cheatlogin', pattern='/cheatlogin')

    # web-view #POST
    config.add_route(name='logout', pattern='/logout')  # tested

    # web-view #GET
    config.add_route(name='dashboard', pattern='/dashboard')

    # web-view #GET
    config.add_route(name='profile', pattern='/profile')

    # web-view #GET
    config.add_route(name='languages', pattern='/languages/map')

    # web-view #GET
    config.add_route(name='maps', pattern='/dashboard/maps')

    # API #GET && PUT && DELETE
    # Gets/puts info about language
    config.add_route(name='language', pattern='/language/{client_id}/{object_id}',
                     factory='lingvodoc.models.LanguageAcl')  # tested

    # API #POST
    # Convert blob
    config.add_route(name='convert', pattern='/convert/blob')  # TODO: when ready test

    # API #POST
    # Convert markup
    config.add_route(name='convert_markup', pattern='/convert/markup')  # TODO: test

    # API #POST
    # Create language
    config.add_route(name='create_language', pattern='/language',
                     factory='lingvodoc.models.LanguageAcl')  # tested

    # API #GET
    # view languages list
    config.add_route(name='get_languages', pattern='/languages')  # tested

    # API #GET
    # Dictionaries list. The following filters should be supported:
    # 1. Filter by:
    #    a) User created
    #    b) User participated
    #    c) Organization participated
    #    d) By language group (all the languages that point to the given one). Need to build a lang tree here.
    config.add_route('dictionaries', 'dictionaries')

    config.add_route(name='published_dictionaries', pattern='/published_dictionaries')  # tested

    # API #GET
    # Perspective list
    # 1. Filter by:
    #    a) template (param is_template=true/false)
    #    b) state  (param state=<state>)
    config.add_route('all_perspectives', '/perspectives')
    config.add_route('all_perspectives_meta', '/perspectives_meta')

    # API #GET
    config.add_route('users', '/users')  # tested

    # web-view
    config.add_route(name='new_dictionary', pattern='/create_dictionary')

    # API #POST
    # Creating dictionary
    config.add_route(name='create_dictionary', pattern='/dictionary',
                     factory='lingvodoc.models.DictionaryAcl')  # tested

    # API #GET && PUT && DELETE
    # Gets/puts info about dictionary (name/additional authors/etc)
    config.add_route(name='dictionary', pattern='/dictionary/{client_id}/{object_id}',
                     factory='lingvodoc.models.DictionaryAcl')  # tested
    config.add_route(name='dictionary_copy', pattern='/dictionary/{client_id}/{object_id}/copy',
                     factory='lingvodoc.models.DictionaryAcl')  # not done yet

    config.add_route(name='dictionary_info',
                     pattern='/dictionary/{client_id}/{object_id}/info',
                     factory='lingvodoc.models.DictionaryAcl')

    # API #DELETE
    config.add_route(name='dictionary_delete', pattern='/dictionary/{client_id}/{object_id}/delete',
                     factory='lingvodoc.models.DictionaryAcl')  # TODO: ?test? impossible with current test paradigm

    # web-view
    config.add_route(name='organizations', pattern='/organizations')

    # API #GET
    config.add_route(name='organization_list', pattern='/organization_list')  # TODO: ?test


    # API #POST
    # Creating organization
    config.add_route(name='create_organization', pattern='/organization',
                     factory='lingvodoc.models.OrganizationAcl')  # ?TODO: ?test

    # API #GET && PUT && DELETE
    # Gets/puts info about organization
    config.add_route(name='organization', pattern='/organization/{organization_id}',
                     factory='lingvodoc.models.OrganizationAcl')  # TODO: ?test

    # API #GET && POST && DELETE
    # Gets, creates and deletes roles related to dictionary (for now: who can create and modify perspectives)
    # Request format: {[user id: <user_id>, role_name: <role_name>]}. Get request is empty and returns list of roles.
    config.add_route(name='dictionary_roles',
                     pattern='/dictionary/{client_id}/{object_id}/roles',
                     factory='lingvodoc.models.DictionaryRolesAcl')  # tested (except delete?)

    # API #GET && PUT
    # Change visibility state for dictionary. States are: 'frozen', 'WiP', 'published', 'merging'
    config.add_route(name='dictionary_status',
                     pattern='/dictionary/{client_id}/{object_id}/state',
                     factory='lingvodoc.models.DictionaryAcl')  # tested

    # API #GET && PUT && DELETE
    # Gets/puts info about perspective.
    # Future note: PUT & DELETE should work on-server only.
    config.add_route(name='perspective',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}/'
                             'perspective/{perspective_client_id}/{perspective_object_id}',
                     factory='lingvodoc.models.PerspectiveAcl')  # tested
    config.add_route(name='perspective_outside',
                     pattern='perspective/{perspective_client_id}/{perspective_object_id}',
                     factory='lingvodoc.models.PerspectiveAcl')  # tested
    # API #POST
    # creates hash in metadata on objects
    config.add_route(name='perspective_hash',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}/'
                             'perspective/{perspective_client_id}/{perspective_object_id}/hash',
                     factory='lingvodoc.models.AdminAcl')  # TODO: ?test? only was used one time

    config.add_route(name='dangerous_perspectives_hash',
                     pattern='/perspectives/hash',
                     factory='lingvodoc.models.AdminAcl')  # TODO: ?test? same as above
    # API #GET && PUT && DELETE
    # {<some_data_name>:{"type""<datatype>, "content":<content>},}
    # for geo: {"location":{"type":"location", "content":{"lat":<lat>, "lng":<lng>}}}
    # for info:{"info":{"type":"list",
    #           "content":[{"info":{"type":"blob",
    #                               "content":{"client_id":<client_id>, "object_id":<object_id>}
    #                              }
    #                      },
    #                     ]
    #                  }
    #          }
    config.add_route(name='perspective_meta',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}/'
                             'perspective/{perspective_client_id}/{perspective_object_id}/meta',
                     factory='lingvodoc.models.PerspectiveAcl')  # tested

    config.add_route(name='perspective_tree',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}/'
                             'perspective/{perspective_client_id}/{perspective_object_id}/tree',
                     factory='lingvodoc.models.PerspectiveAcl')  # tested (?)
    config.add_route(name='perspective_outside_tree',
                     pattern='perspective/{perspective_client_id}/{perspective_object_id}/tree',
                     factory='lingvodoc.models.PerspectiveAcl')  # tested (?)

    config.add_route(name='perspective_info',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}/'
                             'perspective/{perspective_client_id}/{perspective_object_id}/info',
                     factory='lingvodoc.models.PerspectiveAcl')

    # config.add_route(name='test',
    #                  pattern='/test',
    #                  factory='lingvodoc.models.ApproveAllAcl')  # tested
    # API #POST
    # Creating perspective
    config.add_route(name='create_perspective',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}/'
                             'perspective',
                     factory='lingvodoc.models.PerspectiveCreateAcl')  # tested
    config.add_route(name='complex_create',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}/'
                             'complex_create',
                     factory='lingvodoc.models.PerspectiveCreateAcl')  # tested

    # API #GET
    # list perspectives
    config.add_route(name='perspectives',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}/'
                             'perspectives')  # tested TODO: recheck

    # API #GET && POST && DELETE
    # Gets, creates and deletes roles related to dictionary (for now: who can create entities, view entities, create
    # publisher-entities)
    # Request format: {[user id: <user_id>, role_name: <role_name>]}. Get request is empty and returns list of
    # roles and users that they are assigned.
    config.add_route(name='perspective_roles',
                     pattern='/dictionary/{client_id}/{object_id}/'
                             'perspective/{perspective_client_id}/{perspective_object_id}/roles',
                     factory='lingvodoc.models.PerspectiveRolesAcl')

    # API #GET && PUT
    # Get or change visibility state for perspective. States are: 'frozen', 'WiP', 'published'
    config.add_route(name='perspective_status',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                             '/perspective/{perspective_client_id}/{perspective_object_id}/state',
                     factory='lingvodoc.models.PerspectiveAcl')  # tested

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
                             '/perspective/{perspective_client_id}/{perspective_object_id}/fields',
                     factory='lingvodoc.models.PerspectiveAcl')  # tested (except delete, because it not used anywhere(?))

    config.add_route(name='create_field',
                     pattern='/field',
                     factory='lingvodoc.models.ApproveAllAcl')  # todo: acl
    config.add_route(name='field',
                     pattern='/field/{client_id}/{object_id}',
                     factory='lingvodoc.models.ApproveAllAcl')  # todo: acl
    config.add_route(name='fields',
                     pattern='/fields',
                     factory='lingvodoc.models.ApproveAllAcl')  # todo: acl
    config.add_route(name='all_statuses',
                     pattern='/all_statuses',
                     factory='lingvodoc.models.ApproveAllAcl')  # todo: acl
    config.add_route(name='all_locales',
                     pattern='/all_locales',
                     factory='lingvodoc.models.ApproveAllAcl')  # todo: acl
    config.add_route(name='all_data_types',
                     pattern='/all_data_types',
                     factory='lingvodoc.models.ApproveAllAcl')  # todo: acl

    # API #POST
    # should be done with standard form enctype="multipart/form-data"
    config.add_route(name="upload_user_blob",
                     pattern="/blob")

    # seems to be redundant
    # not anymore
    # API #GET
    # no params, returns file
    config.add_route(name="get_user_blob",
                     pattern="/blobs/{client_id}/{object_id}")
    # API #GET
    # no params, lists only own blobs
    config.add_route(name="list_user_blobs",
                     pattern="/blobs")

    # TODO: LOCALES!
    # API #GET && DELETE
    # [{'entity_type': '<entity_type>', 'parent_object_id': <parent_object_id>, 'parent_client_id': <parent_client_id>,
    # 'content': <'content'>, 'locale_id': <locale_id>}]
    config.add_route(name='get_entity', pattern='/entity/{client_id}/{object_id}',
                     factory='lingvodoc.models.PerspectiveEntityAcl')
    config.add_route(name='get_entity_indict', pattern='/dictionary/'
                                                       '{dictionary_client_id}/{dictionary_object_id}'
                                                       '/perspective/'
                                                       '{perspective_client_id}/{perspective_object_id}/'
                                                       'lexical_entry/'
                                                       '{lexical_entry_client_id}/{lexical_entry_object_id}/'
                                                       'entity/'
                                                       '{client_id}/{object_id}',
                     factory='lingvodoc.models.PerspectiveEntityAcl')  # tested (no del)

    # API #GET && DELETE
    # {entity_type: <entity_type>, content: <tag>, connections: [{object_id: <obj_id>, client_id: <cl_id>}
    config.add_route(name='get_group_entity', pattern='/group_entity/{client_id}/{object_id}',
                     factory='lingvodoc.models.PerspectiveEntityAcl')  # tested (no del)
    # tags are different there and in connected words

    # API #GET
    # GET parameter: entity_type = <type> (e.g: "etymology")
    config.add_route(name='get_connected_words', pattern='/lexical_entry/{client_id}/{object_id}/connected',
                     factory='lingvodoc.models.PerspectiveEntityAcl')  # tested (no del)
    config.add_route(name='get_connected_words_indict', pattern='/dictionary/'
                                                                '{dictionary_client_id}/{dictionary_object_id}'
                                                                '/perspective/'
                                                                '{perspective_client_id}/{perspective_object_id}/'
                                                                'lexical_entry/'
                                                                '{client_id}/{object_id}/'
                                                                'connected',
                     factory='lingvodoc.models.PerspectiveEntityAcl')  # tested

    # API #POST (TODO: change to PATCH method later)
    # {entity_type: <entity_type>, content: <tag>, connections: [{object_id: <obj_id>, client_id: <cl_id>}
    config.add_route(name='add_group_entity', pattern='/group_entity',
                     factory='lingvodoc.models.PerspectiveEntityAcl')  # tested
    config.add_route(name='add_group_indict', pattern='/dictionary/'
                                                      '{dictionary_client_id}/{dictionary_object_id}'
                                                      '/perspective/'
                                                      '{perspective_client_id}/{perspective_object_id}/'
                                                      'lexical_entry/'
                                                      'connect',
                     factory='lingvodoc.models.PerspectiveEntityAcl')  # tested

    # API #GET
    # like
    # perspective_client_id
    # perspective_object_id
    config.add_route(name='basic_search', pattern='/basic_search')  # TODO: test

    # API #POST
    # {"searchstrings":[{"searchstring":<searchstring>, "entity_type":<entity_type>, "search_by_or":true/false},
    #                  ],
    #  "perspectives":[{"client_id":<persp_client_id>,"object_id":<persp_object_id>},
    #                 ]
    #   "adopted":True/False,
    #   "adopted_type":<entity_type_where_to_search_if_lexical_entry_is_adopted>,
    #   "count":True/False,
    #   "with_etimology":True/False}
    config.add_route(name='advanced_search', pattern='/advanced_search')  # TODO: test

    # API #GET
    # like
    config.add_route(name='entity_metadata_search', pattern='/meta_search')  # TODO: test

    # API #POST
    # no parameters needed.
    # ids are returned.
    config.add_route(name='create_lexical_entry', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                          '/perspective/{perspective_client_id}/{perspective_object_id}/'
                                                          'lexical_entry',
                     factory='lingvodoc.models.CreateLexicalEntriesEntitiesAcl')  # tested

    config.add_route(name='create_lexical_entry_bulk',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                             '/perspective/{perspective_client_id}/{perspective_object_id}/'
                             'lexical_entries',
                     factory='lingvodoc.models.CreateLexicalEntriesEntitiesAcl')  # tested

    # API #POST
    # {'entity_type': <entity_type>, 'content': <content>, 'locale_id': <locale_id>, 'metadata': <metadata>}
    # ids are returned
    config.add_route(name='create_entity', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                   '/perspective/{perspective_client_id}/{perspective_object_id}/'
                                                   'lexical_entry/{lexical_entry_client_id}/'
                                                   '{lexical_entry_object_id}/entity',
                     factory='lingvodoc.models.CreateLexicalEntriesEntitiesAcl')  # tested

    config.add_route(name='create_entities_bulk', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                          '/perspective/{perspective_client_id}/{perspective_object_id}/entities',
                     factory='lingvodoc.models.CreateLexicalEntriesEntitiesAcl')  # TODO: test

    # API #GET
    # params: start_from=M, count=N, sort_by=<entity_type>
    config.add_route(name='lexical_entries_all', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                         '/perspective/{perspective_client_id}/{perspective_object_id}/all',
                     factory='lingvodoc.models.PerspectiveLexicalViewAcl')
    config.add_route(name='all_perspective_authors', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                         '/perspective/{perspective_client_id}/{perspective_object_id}/authors')
    config.add_route(name='all_perspective_clients', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                         '/perspective/{perspective_client_id}/{perspective_object_id}/clients')

    config.add_route(name='lexical_entries_all_count',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                             '/perspective/{perspective_client_id}/{perspective_object_id}/all_count',
                     factory='lingvodoc.models.PerspectiveLexicalViewAcl')  # tested

    config.add_route(name='lexical_entries_published',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                             '/perspective/{perspective_client_id}/{perspective_object_id}/published',
                     factory='lingvodoc.models.PerspectiveLexicalViewAcl')

    config.add_route(name='lexical_entries_not_accepted',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                             '/perspective/{perspective_client_id}/{perspective_object_id}/not_accepted')

    config.add_route(name='lexical_entries_published_count',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                             '/perspective/{perspective_client_id}/{perspective_object_id}/published_count',
                     factory='lingvodoc.models.PerspectiveLexicalViewAcl')

    config.add_route(name='lexical_entries_not_accepted_count',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                             '/perspective/{perspective_client_id}/{perspective_object_id}/not_accepted_count')
    # made only return list of ids, because another route fol full info exist

    # API #GET, DELETE
    # all children
    config.add_route(name='lexical_entry', pattern='/lexical_entry/{client_id}/{object_id}',
                     factory='lingvodoc.models.LexicalViewAcl')  # tested
    config.add_route(name='lexical_entry_in_perspective',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                             '/perspective/{perspective_client_id}/{perspective_object_id}/'
                             'lexical_entry/{client_id}/{object_id}',
                     factory='lingvodoc.models.LexicalViewAcl')  # tested
    # API #PATCH
    # Publishers view: this can approve word versions.
    # "type": "leveloneentity", "leveltwoentity"
    # {"entity": [{"type": <object_type>, "client_id": <client_id>, "object_id": <object_id>}, ] }
    config.add_route(name='approve_entity', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                    '/perspective/{perspective_client_id}/{perspective_object_id}/approve',
                     factory='lingvodoc.models.PerspectivePublishAcl')

    config.add_route(name='accept_entity', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                    '/perspective/{perspective_client_id}/{perspective_object_id}/accept',
                     factory='lingvodoc.models.PerspectivePublishAcl')
    # todo: DANGEROUS! Anyone can approve, if the have their own dictionary and know ids of entity, they want to approve
    # todo: fix this
    config.add_route(name='approve_all', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                 '/perspective/{perspective_client_id}/{perspective_object_id}/approve_all',
                     factory='lingvodoc.models.PerspectivePublishAcl')
    config.add_route(name='accept_all', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                 '/perspective/{perspective_client_id}/{perspective_object_id}/accept_all',
                     factory='lingvodoc.models.PerspectivePublishAcl')
    config.add_route(name='approve_all_outer', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                       '/perspective/{perspective_client_id}/{perspective_object_id}/approve_all_outer',
                     factory='lingvodoc.models.PerspectivePublishAcl')  # TODO: test

    # web-view
    config.add_route(name='edit_dictionary', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                     '/perspective/{perspective_client_id}/{perspective_object_id}/edit')
    # web-view
    config.add_route(name='view_dictionary', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                     '/perspective/{perspective_client_id}/{perspective_object_id}/view')
    # web-view
    config.add_route(name='publish_dictionary', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                        '/perspective/{perspective_client_id}/{perspective_object_id}/publish')

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
    config.add_route(name='merge_dictionaries', pattern='/merge/dictionaries')  # TODO: test

    # API #POST
    # {
    # "dictionary_client_id": <dictionary_client_id>,
    # "dictionary_object_id": <dictionary_object_id>},
    # "name": <new_name>,
    # "translation": <new_name_translation>,
    # "perspectives":
    # [
    #  {"client_id": <first_perspective_client_id, "object_id": <first_perspective_object_id>,
    #   "fields": [{"new_type_name":<new_type_name>,
    #               "entity_type": <entity_type>, "data_type":<text|img|sound|markup|grouping_tag>,
    #               "status": <enabled|disabled>}, "contains": [{}], "group": <grouping_button_localization_str>]},
    #  {"client_id": <second_perspective_client_id, "object_id": <second_perspective_object_id>,
    #   "fields": [{"new_type_name":<new_type_name>,
    #               "entity_type": <entity_type>, "data_type":<text|img|sound|markup|grouping_tag>,
    #               "status": <enabled|disabled>}, "contains": [{}], "group": <grouping_button_localization_str>]}
    # ]
    # }
    # Returns new perspective object and client ids.
    config.add_route(name='merge_perspectives', pattern='/merge/perspectives')  # TODO: test

    # API #POST
    # {'entity_type_primary':<entity_type_primary>,
    # 'entity_type_secondary' : <entity_type_secondary>,
    # 'threshold': <threshold>,
    # 'levenstein' : <levenstein>,
    # 'client_id' : <client_id>,
    # 'object_id' : <object_id>
    # }
    config.add_route(name='merge_suggestions', pattern='/merge/suggestions')  # TODO: test

    config.add_route(name='merge_suggestions_old', pattern='/merge/suggestionsold/'  # should be removed?
                                                           '{dictionary_client_id_1}/{dictionary_object_id_1}/'
                                                           '{perspective_client_id_1}/{perspective_object_id_1}/'
                                                           '{dictionary_client_id_2}/{dictionary_object_id_2}/'
                                                           '{perspective_client_id_2}/{perspective_object_id_2}/'
                                                           '{entity_type_primary}/{threshold}/{entity_type_secondary}/'
                                                           '{levenstein}')

    # API #PATCH
    # {'client_id':<client_id>, 'object_id':<object_id>, 'real_delete':true/false}  id's of entry where moving to
    config.add_route(name='move_lexical_entry', pattern='/lexical_entry/{client_id}/{object_id}/move',
                     factory='lingvodoc.models.ApproveAllAcl')  # TODO: test

    # {real_delete':true/false,
    #  'move_list':[{'client_id': <where_to_client_id>,
    #               'object_id': <where_to_object_id>,
    #               'lexical_entries': [{'client_id': <where_from_client_id>, 'object_id': <where_from_object_id>}, ]}
    #              ,]
    # }
    config.add_route(name='move_lexical_entry_bulk', pattern='/move/lexical_entries')  # TODO: test

    # web-view
    config.add_route(name='merge_master', pattern='/dashboard/merge')

    # API #GET
    # Response example:
    # [{"id": <userid>, "login": <login>, "name": <name>, "intl_name": <international_name>, "userpic": <url_to_userpic>}, ]
    config.add_route(name='dictionary_authors',
                     pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}')  # TODO: do it
    config.add_route(name='perspective_authors', pattern='/dictionary/{dictionary_client_id}/{dictionary_object_id}'
                                                         '/perspective/{perspective_client_id}/{perspective_object_id}')  # TODO: just do it

    # API #GET
    # This methods gets info about user by his client_id
    # client_id = <client_id>
    # Response example:
    # {"id": <userid>, "login": <login>, "name": <name>, "intl_name": <international_name>, "userpic": <url_to_userpic>}
    # #PUT
    # {"client_id":<client_id> OR "user_id":<user_id>,
    #  "new_password": <new_password>, "old_password":<old_password>,
    #  "name":<name>, "birthday":<birthday>, "email":<email>, "about":<about>}
    config.add_route(name='get_user_info', pattern='/user')  # tested

    # web-view #GET
    config.add_route(name='blob_upload', pattern='/blob_upload')
    config.add_route(name='corpora_fields', pattern='/corpora_fields')

    # API #POST
    # params:
    # {"blob_client_id": <id>, "blob_object_id": <id>, "parent_client_id": <language_client_id>, "parent_object_id": <language_object_id>}
    config.add_route(name='convert_dictionary', pattern='/convert')  # tested
    config.add_route(name='convert_dictionary_check', pattern='/convert_check')  # tested
    config.add_route(name='convert_dictionary_dialeqt', pattern='/convert_dictionary_dialeqt')  # TODO: dododo
    config.add_route(name='convert_five_tiers', pattern='/convert_five_tiers')  # TODO: dododo
    config.add_route(name='convert_dictionary_dialeqt_get_info', pattern='/convert_dictionary_dialeqt_get_info/{blob_client_id}/{blob_object_id}')  # TODO: dododo

    # Check the documentation in celery_test.view.py
    # config.add_route(name='test_queue_set', pattern='/test_queue_set')
    # config.add_route(name='test_queue_get', pattern='/test_queue_get')

    config.add_route(name='create_translationgist', pattern='/translationgist',
                     factory='lingvodoc.models.ApproveAllAcl')
    config.add_route(name='translationgist', pattern='/translationgist/{client_id}/{object_id}',
                     factory='lingvodoc.models.ApproveAllAcl')
    config.add_route(name='create_translationatom', pattern='/translationatom',
                     factory='lingvodoc.models.ApproveAllAcl')
    config.add_route(name='translationatom', pattern='/translationatom/{client_id}/{object_id}',
                     factory='lingvodoc.models.ApproveAllAcl')
    config.add_route(name='translation_search', pattern='/translation_search',
                     factory='lingvodoc.models.ApproveAllAcl')

    config.add_route(name='translation_service_search', pattern='/translation_service_search',
                     factory='lingvodoc.models.ApproveAllAcl')


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    from pyramid.config import Configurator
    config_file = global_config['__file__']
    parser = ConfigParser()
    parser.read(config_file)
    # TODO: DANGER
    storage = dict()
    for k, v in parser.items('backend:storage'):
        storage[k] = v
    settings['storage'] = storage
    config = Configurator(settings=settings)
    log = logging.getLogger(__name__)

    # TODO: Find a more neat way
    try:
        cache_kwargs = dict()
        for k, v in parser.items('cache:dogpile'):
            cache_kwargs[k] = v
        cache_args = dict()
        for k, v in parser.items('cache:dogpile:args'):
            cache_args[k] = v
        cache_kwargs['arguments'] = cache_args
        if 'expiration_time' in cache_kwargs:
            cache_kwargs['expiration_time'] = int(cache_kwargs['expiration_time'])
        if 'redis_expiration_time' in cache_kwargs:
            cache_kwargs['redis_expiration_time'] = int(cache_kwargs['redis_expiration_time'])
    except NoSectionError:
        log.warn("No 'cache:dogpile' or/and 'cache:dogpile:args' sections in config; disabling caching")
        initialize_cache(None)
    else:
        initialize_cache(cache_kwargs)

    # config.configure_celery('development_test.ini')

    authentication_policy = AuthTktAuthenticationPolicy(settings['secret'],
                                                        hashalg='sha512', callback=groupfinder)
    authorization_policy = ACLAuthorizationPolicy()
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
