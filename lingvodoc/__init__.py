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
    config.add_route('home', '/')

    # web-view #GET && POST
    # registration page
    config.add_route('signup', 'signup')

    # internal #POST
    # validation for registration parameters: unique email, unique login
    config.add_route('signup/validate', 'signup/validate/{param}')

    # web-view #GET
    # login page
    config.add_route('login', 'login')

    # API #POST
    # this is the same operation as login - but params are sent via json
    config.add_route('signin', 'signin')

    # web-view #POST
    config.add_route('logout', 'logout')

    # web-view #GET
    config.add_route('dashboard', 'dashboard')

    # web-view #GET
    config.add_route('languages', 'languages')

    # API #GET && PUT && DELETE
    # Gets/puts info about language
    config.add_route('language', 'language/{language_id}')

    # API #POST
    # Create language
    config.add_route('language', 'language')

    # API #GET
    # Dictionaries list. The following filters should be supported:
    # 1. Filter by:
    #    a) User created
    #    b) User participated
    #    c) Organization participated
    #    d) By language group (all the languages that point to the given one). Need to build a lang tree here.
    #    e) Maps location (coordinates) +- radius in kilometers
    config.add_route('dictionaries', 'dictionaries')

    # API #POST
    # Creating dictionary
    config.add_route('dictionary', 'dictionary')

    # API #GET && PUT && DELETE
    # Gets/puts info about dictionary (name/additional authors/etc)
    config.add_route('dictionary', 'dictionary/{client_id}/{object_id}')

    # API #GET && POST && DELETE
    # Gets, creates and deletes roles related to dictionary (for now: who can create and modify perspectives)
    # Request format: {[user id: <user_id>, role_name: <role_name>]}. Get request is empty and returns list of roles.
    config.add_route(name='dictionary_roles',
                     pattern='dictionary/{client_id}/{object_id}/roles')

    # API #GET && PUT
    # Change visibility state for dictionary. States are: 'frozen', 'WiP', 'published', 'merging'
    config.add_route(name='dictionary_status',
                     pattern='dictionary/{client_id}/{object_id}/state')

    # API #GET && PUT && DELETE
    # Gets/puts info about perspective.
    # Future note: PUT & DELETE should work on-server only.
    config.add_route(name='perspective',
                     pattern='dictionary/{dictionary_client_id}/{dictionary_object_id}/'
                             'perspective/{perspective_client_id}/{perspective_id}')

    # API #GET && POST && DELETE
    # Gets, creates and deletes roles related to dictionary (for now: who can create entities, view entities, create
    # publisher-entities)
    # Request format: {[user id: <user_id>, role_name: <role_name>]}. Get request is empty and returns list of
    # roles and users that they are assigned.
    config.add_route(name='perspective_roles',
                     pattern='dictionary/{client_id}/{object_id}/'
                             'perspective/{perspective_client_id}/{perspective_id}/roles')

    # API #GET && PUT
    # Get or change visibility state for perspective. States are: 'frozen', 'WiP', 'published'
    config.add_route(name='perspective_status',
                     pattern='dictionary/{dictionary_client_id}/{dictionary_object_id}'
                     '/perspective/{perspective_client_id}/{perspective_id}/status')

    # API #GET && POST && DELETE
    # Configuring columns in perspective table.
    # TODO: fix 'level' field in models: supposed to be a string indicating class for entity (L1E, L2E or GE)
    # TODO: add 'position' field in models
    # TODO: add 'data_type' field in models
    # TODO: add localization strings (name for the field) for fields (each field should have name) (it's entity_type).
    # TODO: group also indicates user localisation string
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
                     pattern='dictionary/{dictionary_client_id}/{dictionary_object_id}'
                             '/perspective/{perspective_client_id}/{perspective_id}/fields')

    # API #GET && POST && DELETE
    #


    #creation date, author
    'get_object_info'
    'get_author_info'


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

    parser = ConfigParser()
    parser.read('development.ini')
    storage = dict()
    for k, v in parser.items('backend:storage'):
        storage[k] = v
    settings['storage'] = storage

    config = Configurator(settings=settings)
    config.set_authentication_policy(authentication_policy)
    config.set_authorization_policy(authorization_policy)
    config.include('pyramid_chameleon')
    config.add_static_view('static', path='lingvodoc:static', cache_max_age=3600)
    configure_routes(config)
    config.add_route('testing', '/testing')
    config.add_route('upload', '/upload')
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
