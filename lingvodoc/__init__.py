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

def configure_routes(config):
    config.add_route('home', '/')
    config.add_route('register', 'register')
    config.add_route('register/validate', 'register/validate/{param}')
    config.add_route('login', 'login')
    config.add_route('logout', 'logout')
    config.add_route('dashboard', 'dashboard')
    config.add_route('create_dictionary_page', 'create_dictionary_page')
    config.add_route('own_dictionaries_list', 'own_dictionaries_list')
    config.add_route('create_language_page', 'create_language_page')
    config.add_route('create_language', 'create_language')
    config.add_route('edit_dictionary',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/edit')
    config.add_route('view_page', 'view')

    # NOTE: TODO: it's a workaround for demo -- we are showing the contents of the page as for edit (with the same data)
    config.add_route('view_dictionary',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/view')
    config.add_route('publish_dictionary',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/publish')
    config.add_route('view_metaword',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/'
                     'metawords/{metaword_client_id}/{metaword_id}/view')
    config.add_route('get_metawords_for_edit', 'dictionaries/{client_id}/{dictionary_id}/edit/metawords/')
    config.add_route('save_metaword_objects', 'dictionaries/{client_id}/{dictionary_id}/edit/save/')

    # API stuff
    # : dictionaries
    # : : single operations
    config.add_route('create_dictionary_post',
                     'create_dictionary',
                     request_method='POST')

    # : metawords
    # : : single operations
    config.add_route('api_metaword_get',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/metawords/'
                     '{metaword_client_id}/{metaword_id}',
                     #factory=DummyDeny,
                     request_method='GET')
    config.add_route('api_metaword_post',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/metawords/'
                     '{metaword_client_id}/{metaword_id}',
                     #factory=DummyDeny,
                     request_method='POST')
    config.add_route('api_metaword_delete',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/metawords/'
                     '{metaword_client_id}/{metaword_id}',
                     #factory=DummyDeny,
                     request_method='DELETE')
    # : : batch operations
    config.add_route('api_metaword_get_batch',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/metawords/',
                     #factory=DummyDeny,
                     request_method='GET')
    config.add_route('api_metaword_post_batch',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/metawords/',
                     #factory=DummyDeny,
                     request_method='POST')
    # : metaword sounds
    config.add_route('api_metaword_sound_get',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/metawords/'
                     '{metaword_client_id}/{metaword_id}/sounds/{sound_client_id}/{sound_id}',
                     #factory=DummyDeny,
                     request_method='GET')
    # : metaword paradigms
    # : : single operations
    config.add_route('api_metaparadigm_get',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/metawords/'
                     '{metaword_client_id}/{metaword_id}/metaparadigm/'
                     '{metaparadigm_client_id}/{metaparadigm_id}',
                     #factory=DummyDeny,
                     request_method='GET')
    # : : batch operations
    config.add_route('api_metaparadigm_get_batch',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/metawords/'
                     '{metaword_client_id}/{metaword_id}/metaparadigms',
                     #factory=DummyDeny,
                     request_method='GET')
    config.add_route('api_metaparadigm_post_batch',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/metawords/'
                     '{metaword_client_id}/{metaword_id}/metaparadigms',
                     #factory=DummyDeny,
                     request_method='POST')
    # : metaparadigm sounds
    config.add_route('api_metaparadigm_sound_get',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/metawords/'
                     '{metaword_client_id}/{metaword_id}/metaparadigms/'
                     '{metaparadigm_client_id}/{metaparadigm_id}/sounds/{sound_client_id}/{sound_id}',
                     request_method='GET')
    # : etymology actions
    config.add_route('api_etymology_get',
                     'dictionaries/{dictionary_client_id}/{dictionary_id}/metawords/'
                     '{metaword_client_id}/{metaword_id}/etymology',
                     request_method='GET')

    # : get corpus
    config.add_route('api_corpora_get', 'corpora/{corpus_client_id}/{corpus_id}', request_method='GET')


    # : default words for publishing



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
    config = Configurator(settings=settings)
    config.set_authentication_policy(authentication_policy)
    config.set_authorization_policy(authorization_policy)
    config.include('pyramid_chameleon')
    config.add_static_view('static', path='lingvodoc:static', cache_max_age=3600)
    configure_routes(config)
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
