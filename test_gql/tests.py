import pytest

import os

from subprocess import PIPE, Popen
from configparser import ConfigParser

import transaction
from pyramid.httpexceptions import HTTPForbidden
from pyramid.paster import get_appsettings


from lingvodoc.scripts.initializedb import data_init
#from lingvodoc.utils.creation import create_dbdictionary
#from lingvodoc.schema.gql_holders import ResponseError
from lingvodoc.utils.search import translation_gist_search
from lingvodoc.models import (
    Dictionary,
    DBSession,
    Group,
    BaseGroup,
    Language,
)

from graphene.test import Client

#from lingvodoc.scheme import schema

from sqlalchemy import create_engine
import webtest.http
import webtest
from pyramid import paster


class TestConnection:

    def setup_class(self):
        self.alembic_ini_path = os.path.join(
            os.path.dirname(__file__), 'testing.ini')
        parser = ConfigParser()
        parser.read(self.alembic_ini_path)
        alembic_conf = dict()
        for k, v in parser.items('alembic'):
            alembic_conf[k] = v
        dbname = alembic_conf['sqlalchemy.url']
        my_env = os.environ
        pathdir = os.path.dirname(os.path.realpath(__file__))
        bashcommand = "alembic -c %s upgrade head" % self.alembic_ini_path
        myapp = paster.get_app(self.alembic_ini_path)
        self.app = webtest.TestApp(myapp)
        args = bashcommand.split()
        pathdir = "/".join(pathdir.split("/")[:-1])
        proc = Popen(args, cwd=pathdir, env=my_env)
        proc.communicate()

        self.ws = webtest.http.StopableWSGIServer.create(myapp, port=6543, host="0.0.0.0")  # todo: change to pserve
        self.ws.wait()
        self.set_server_is_up = True

        accounts = get_appsettings(self.alembic_ini_path, 'accounts')
        #          Create dictionary for tests
        #engine = create_engine(dbname)
        #DBSession.configure(bind=engine)
        #self.create_dbdictionary(id=[1, None], parent_id=[1, 13])
        data_init(transaction.manager, accounts, dbname)

        # Get admin's and user's headers
        self.admin_header = self.return_header_for_admin(self)
        self.user_header = self.return_header_of_new_user(self)
        #with open(os.path.dirname(__file__) + '/test_file.txt', 'w', encoding='utf-8') as file:
         #   file.write("one")
        a = 2+1
        print(a)



    def teardown_class(self):

        bashcommand = "alembic -c %s downgrade base" % self.alembic_ini_path
        args = bashcommand.split()
        pathdir = os.path.dirname(os.path.realpath(__file__))
        pathdir = "/".join(pathdir.split("/")[:-1])
        my_env = os.environ
        proc = Popen(args, cwd=pathdir, env=my_env)
        #proc.communicate()

    # def create_dbdictionary(id=None,
    #                         parent_id=None,
    #                         translation_gist_id=None,
    #                         additional_metadata=None,
    #                         domain=0,
    #                         category=0):
    #     client_id, object_id = id
    #
    #     if not parent_id:
    #         raise
    #     parent_client_id, parent_object_id = parent_id
    #     translation_gist_client_id, translation_gist_object_id = translation_gist_id if translation_gist_id else (
    #     None, None)
    #
    #     duplicate_check = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).all()
    #     if duplicate_check:
    #         raise
    #     parent = DBSession.query(Language).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    #     if not parent:
    #         raise
    #
    #     resp = translation_gist_search("WiP")
    #     state_translation_gist_object_id, state_translation_gist_client_id = resp.object_id, resp.client_id
    #     dbdictionary_obj = Dictionary(client_id=client_id,
    #                                   object_id=object_id,
    #                                   state_translation_gist_object_id=state_translation_gist_object_id,
    #                                   state_translation_gist_client_id=state_translation_gist_client_id,
    #                                   parent=parent,
    #                                   translation_gist_client_id=translation_gist_client_id,
    #                                   translation_gist_object_id=translation_gist_object_id,
    #                                   additional_metadata=additional_metadata,
    #                                   domain=domain,
    #                                   category=category
    #                                   )
    #
    #     client = DBSession.query(Client).filter_by(id=client_id).first()
    #     user = client.user
    #     for base in DBSession.query(BaseGroup).filter_by(dictionary_default=True):
    #         new_group = Group(parent=base,
    #                           subject_object_id=dbdictionary_obj.object_id,
    #                           subject_client_id=dbdictionary_obj.client_id)
    #         if user not in new_group.users:
    #             new_group.users.append(user)
    #         DBSession.add(new_group)
    #         DBSession.flush()
    #     return dbdictionary_obj

    def graphql_request(self, query, variables="{}", header="", content_type="application/json"):
        # if variables is None:
        #     params = query
        # else:
        #params = '{"variables":' + variables + ', "query": "' + query + '"}'
        params = '{"variables":%s, "query": "%s"}' % (variables, query)
        params = params.replace("\n", " ").replace("\t", ' ')
        #params = params.replace("\\'", "")
        response = self.app.post('/graphql',
                                 params=params,
                                 content_type=content_type,
                                 headers={"Cookie": header})
        return response


    def get_cookie_from_headers(self, headers):
        string_headers = str(headers)
        start_of_auth = string_headers.find("auth_tkt=", 0, 120)
        finish_of_auth = string_headers.find("Max-Age=315360000", 120, 290)
        auth_tkt = string_headers[start_of_auth:finish_of_auth]
        start_of_client_id = string_headers.find("client_id", 900, 1000)
        finish_of_client_id = string_headers.find("; Max-Age=315360000", start_of_client_id, start_of_client_id + 30)
        client_id = string_headers[start_of_client_id:finish_of_client_id]
        cookie = auth_tkt + "locale_id=2; " + client_id
        return cookie

    def return_header_for_admin(self):
        response = self.app.post('/login', params={'login': "admin",
                                              'password': 'password'}, headers={"Cookie": "locale_id=2"})
        return self.get_cookie_from_headers(self, response.headers)


    def return_header_of_new_user(self):
        self.app.post('/signup', params='''{"login":"tester",
                                                        "name":"tester",
                                                        "email":"tester@test.com",
                                                        "password":"password",
                                                        "day":2,
                                                        "month":3,
                                                        "year":1980}''',
                                 content_type="application/json",
                                 headers = {"Cookie" : "locale_id=2"})
        #response = self.app.post('/logout')
        response = self.app.post('/login', params={'login': "tester",
                                                   'password': "password"}, headers={"Cookie" : "locale_id=2"})
        return self.get_cookie_from_headers(self, response.headers)


#     def test_hey(self, snapshot):
#         response = self.app.post('/graphql',
#             params='''query myQuery {
#       dictionary(id: [2, 2]) {
#         id
#         translation
#         parent_id
#         marked_for_deletion
#         translation_gist_id
#         additional_metadata {
#           blob_description
#         }
#          perspectives{id translation}
#
#       }
#     }''',
#             content_type = "application/graphql",
#             headers = {"Cookie" : self.admin_header})
#         snapshot.assert_match(response.json_body)
#
#
    # def test_test(self, snapshot):
    #     variables = '{"id": [%s, %s]}' % ('2', '2')
    #     query = '''query myQuery($id:LingvodocID){
    #                 dictionary(id: $id) {
    #                  id
    #                  }}'''
    #     response = self.graphql_request(query, variables)
    #     snapshot.assert_match(response.json_body)
#
#################################################################
#                       Languages tests
#################################################################
    def test_USE_BANHAMMER(self, snapshot):
        query = '''mutation {
        activate_deactivate_user(user_id: 3, is_active: false) { triumph } }
        '''
        response = self.graphql_request(query, header=self.admin_header)
        snapshot.assert_match(response.json_body)


    def test_give_roles_to_user(self, snapshot):
        query = '''mutation Add_roles {
                    add_perspective_roles(id: [2, 3], user_id:3 , roles_users:[8, 12, 13, 15, 20, 21, 22, 23, 24, 26]){
              triumph

             }
                }'''
        response = self.graphql_request(query, header=self.admin_header)
        snapshot.assert_match(response.json_body)


    def test_get_language(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('1', '13')        # English language
        query = '''query Language ($id: LingvodocID){
                    language(id: $id) {
                      id
                      translation
                      parent_id
                      translation_gist_id
                      marked_for_deletion
                      dictionaries {
                            id
                            parent_id
                            translation
                            translation_gist_id
                            marked_for_deletion
                            state_translation_gist_id
                            category
                            domain
                            status
                      }
            }
        }'''
        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)

    def test_get_all_languages(self, snapshot):
        query = '''query LanguagesList{
                    languages {
                      id
                      translation
                      parent_id
                      translation_gist_id
                      marked_for_deletion
                      dictionaries {
                            id
                            parent_id
                            translation
                            translation_gist_id
                            marked_for_deletion
                            state_translation_gist_id
                            category
                            domain
                            status
                      }
            }
        }'''
        response = self.graphql_request(query)
        snapshot.assert_match(response.json_body)


    def test_create_language_with_old_gist_none_header(self, snapshot):
        query = '''mutation  create_language{
                    create_language(translation_gist_id: [1, 4],
                        parent_id: [1, 13])
                            {
                            language {
                                id
                                translation_gist_id
                            }
        }
    }'''
        response = self.graphql_request(query)
        snapshot.assert_match(response.json_body)

    def test_create_language_with_old_gist_user_header(self, snapshot):
        query = '''mutation  create_language{
                    create_language(translation_gist_id: [1, 4],
                        parent_id: [1, 13])
                            {
                            language {
                                id
                                translation_gist_id
                            }
        }
    }'''
        response = self.graphql_request(query, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_create_language_with_old_gist_admin_header(self, snapshot):
        query = '''mutation create_language{
                    create_language(translation_gist_id: [1, 4],
                        parent_id: [1, 13])
                            {
                            language {
                                id
                                translation_gist_id
                            }
        }
    }'''
        response = self.graphql_request(query, header=self.admin_header)
        snapshot.assert_match(response.json_body)

    def test_create_language_with_new_gist_none_header(self, snapshot):
        objectval = '[{"locale_id": 2, "content": "test content"}]'
        variables = '{"atoms": %s}' % objectval
        query = '''mutation create_language ($atoms: [ObjectVal]){
                    create_language (translation_atoms: $atoms)
                    {
                    language {
                        id
                        translation_gist_id
                              }
                    }
    }'''
        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)

    def test_create_language_with_new_gist_user_header(self, snapshot):
        objectval = '[{"locale_id": 2, "content": "test content"}]'
        variables = '{"atoms": %s}' % objectval
        query = '''mutation create_language ($atoms: [ObjectVal]){
                    create_language (translation_atoms: $atoms)
                    {
                    language {
                        id
                        translation_gist_id
                              }
                    }
    }'''
        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_create_language_with_new_gist_admin_header(self, snapshot):
        objectval = '[{"locale_id": 2, "content": "test content 2"}]'
        variables = '{"atoms": %s}' % objectval
        query = '''mutation create_language ($atoms: [ObjectVal]){
                            create_language (translation_atoms: $atoms)
                            {
                            language {
                                id
                                translation_gist_id
                                      }
                            }
            }'''
        response = self.graphql_request(query, variables, header=self.admin_header)
        snapshot.assert_match(response.json_body)

    def test_update_language_no_header(self, snapshot):
        variables = '{"lang_id": [%s, %s], "gist_id": [%s, %s]}'%('1', '14', '1', '2')  # Finnish language, Russian gist
        query = '''mutation update_lang($lang_id: LingvodocID!, $gist_id: LingvodocID!) {
        update_language(id: $lang_id, translation_gist_id: $gist_id) {
            language {
                id
                translation_gist_id
            }
        }
    }'''
        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)

    def test_update_language_user_header(self, snapshot):
        variables = '{"lang_id": [%s, %s], "gist_id": [%s, %s]}'%('1', '14', '1', '2')  # Finnish language, Russian gist
        query = '''mutation update_lang($lang_id: LingvodocID!, $gist_id: LingvodocID!) {
        update_language(id: $lang_id, translation_gist_id: $gist_id) {
            language {
                id
                translation_gist_id
            }
        }
    }'''
        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_update_language_admin_header(self, snapshot):
        variables = '{"lang_id": [%s, %s], "gist_id": [%s, %s]}'%('1', '14', '1', '2')  # Finnish language, Russian gist
        query = '''mutation update_lang($lang_id: LingvodocID!, $gist_id: LingvodocID!) {
        update_language(id: $lang_id, translation_gist_id: $gist_id) {
            language {
                id
                translation_gist_id
            }
        }
    }'''
        response = self.graphql_request(query, variables, header=self.admin_header)
        snapshot.assert_match(response.json_body)

    def test_delete_language_no_header(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('1', '14')  # Finnish language
        query = '''mutation del_language($id: LingvodocID!) {
                    delete_language(id: $id) {
                        triumph
                        language {
                          id  
                          translation
                          marked_for_deletion
            }
        }
    }'''
        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)

    def test_delete_language_user_header(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('1', '14')  # Finnish language
        query = '''mutation del_language($id: LingvodocID!) {
                    delete_language(id: $id) {
                        triumph
                        language {
                          id  
                          translation
                          marked_for_deletion
            }
        }
    }'''
        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_delete_language_admin_header(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('1', '14')  # Finnish language
        query = '''mutation del_language($id: LingvodocID!) {
                    delete_language(id: $id) {
                        triumph
                        language {
                          id  
                          translation
                          marked_for_deletion
            }
        }
    }'''
        response = self.graphql_request(query, variables, header=self.admin_header)
        snapshot.assert_match(response.json_body)


#################################################################
#                       Entities tests
#################################################################

    def test_get_entity(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('2', '22')
        query = '''query getEntities ($id: LingvodocID!){
                    entity(id: $id) {
                      id
                      marked_for_deletion
                      parent_id
                      content
                    }
        }'''
        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)

    def test_create_entity_no_header(self, snapshot):
        variables = '{"parent_id": [%s, %s], "field_id": [%s, %s], "content": "%s"}' % (
        '2', '18', '2', '5', 'test_content')
        query = '''mutation createEntity ($parent_id: LingvodocID!, $field_id: LingvodocID!, $content: String){
                            create_entity(parent_id: $parent_id, field_id: $field_id, content: $content) {
                              entity {
                                  id
                                  parent_id
                                  content
                                  marked_for_deletion
                                  }
                            triumph
                            }
                }'''
        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)

    def test_create_entity_user_header(self, snapshot):
        variables = '{"parent_id": [%s, %s], "field_id": [%s, %s], "content": "%s"}' % (
            '2', '18', '2', '5', 'test_content')
        query = '''mutation createEntity ($parent_id: LingvodocID!, $field_id: LingvodocID!, $content: String){
                                    create_entity(parent_id: $parent_id, field_id: $field_id, content: $content) {
                                      entity {
                                          id
                                          parent_id
                                          content
                                          marked_for_deletion
                                          published
                                          }
                                    triumph
                                    }
                        }'''
        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_create_entity_admin_header(self, snapshot):
        variables = '{"parent_id": [%s, %s], "field_id": [%s, %s], "content": "%s"}' % (
        '2', '18', '2', '5', 'test_content')
        query = '''mutation createEntity ($parent_id: LingvodocID!, $field_id: LingvodocID!, $content: String){
                            create_entity(parent_id: $parent_id, field_id: $field_id, content: $content) {
                              entity {
                                  id
                                  parent_id
                                  content
                                  marked_for_deletion
                                  published
                                  }
                            triumph
                            }
                }'''
        response = self.graphql_request(query, variables, header=self.admin_header)
        snapshot.assert_match(response.json_body)

    def test_update_entity_no_header(self, snapshot):
        variables = '{"id": [%s, %s], "published": %s}' % ('2', '22', 'true')
        query = '''mutation updateEntity ($id: LingvodocID!, $published: Boolean){
                            update_entity(id: $id, published: $published) {
                              entity {
                                  id
                                  parent_id
                                  content
                                  marked_for_deletion
                                  published
                                  }
                            triumph
                            }
                }'''
        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)

    def test_update_entity_user_header(self, snapshot):
        variables = '{"id": [%s, %s], "published": %s}' % ('2', '23', 'true')
        query = '''mutation updateEntity ($id: LingvodocID!, $published: Boolean){
                            update_entity(id: $id, published: $published) {
                              entity {
                                  id
                                  parent_id
                                  content
                                  marked_for_deletion
                                  published
                                  }
                            triumph
                            }
                }'''
        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_update_entity_admin_header(self, snapshot):
        variables = '{"id": [%s, %s], "published": %s}' % ('2', '22', 'true')
        query = '''mutation updateEntity ($id: LingvodocID!, $published: Boolean){
                            update_entity(id: $id, published: $published) {
                              entity {
                                  id
                                  parent_id
                                  content
                                  marked_for_deletion
                                  published
                                  }
                            triumph
                            }
                }'''
        response = self.graphql_request(query, variables, header=self.admin_header)
        snapshot.assert_match(response.json_body)

    def test_delete_entity_no_header(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('2', '23')
        query = '''mutation deleteEntity ($id: LingvodocID!){
                            delete_entity(id: $id) {
                              entity {
                                  id
                                  parent_id
                                  content
                                  marked_for_deletion
                                  published
                                  }
                            triumph
                            }
                }'''
        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)

    def test_delete_entity_not_owner_header(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('2', '24')
        query = '''mutation deleteEntity ($id: LingvodocID!){
                            delete_entity(id: $id) {
                              entity {
                                  id
                                  parent_id
                                  content
                                  marked_for_deletion
                                  published
                                  }
                            triumph
                            }
                }'''
        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_delete_entity_owner_header(self, snapshot):
        #variables = '{"id": [%s, %s]}' % ('4', '3')
        variables = '{"id": [%s, %s]}' % ('2', '22')
        query = '''mutation deleteEntity ($id: LingvodocID!){
                            delete_entity(id: $id) {
                              entity {
                                  id
                                  parent_id
                                  content
                                  marked_for_deletion
                                  published
                                  }
                            triumph
                            }
                }'''
        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_delete_entity_admin_header(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('2', '25')
        query = '''mutation deleteEntity ($id: LingvodocID!){
                            delete_entity(id: $id) {
                              entity {
                                  id
                                  parent_id
                                  content
                                  marked_for_deletion
                                  published
                                  }
                            triumph
                            }
                }'''
        response = self.graphql_request(query, variables, header=self.admin_header)
        snapshot.assert_match(response.json_body)

#################################################################
#                       Gists tests
#################################################################

    def test_get_gist(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('1', '193')
        query = """query getTranslationGist($id:LingvodocID){
                       translationgist (id: $id) {
                           id
                           marked_for_deletion
                           type
                           translation
                           translationatoms {
                                id
                                parent_id
                                marked_for_deletion
                                content
                           }
               }
           }"""
        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)

    def test_create_gist_no_header(self, snapshot):
        variables = '{"type": "%s"}' % ("Text")
        query = """mutation create_trans_gist($type: String!){
                    create_translationgist(type: $type) {
                        translationgist {
                         id
                         type
                         marked_for_deletion
                         translation
                         translationatoms{
                            id
                            parent_id
                            content
                         }
                        }
                    triumph
                    }
        }"""



        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)


    def test_create_gist_user_header(self, snapshot):
        variables = '{"type": "%s"}' % ("Text")
        query = """mutation create_trans_gist($type: String!){
                    create_translationgist(type: $type) {
                        translationgist {
                         id
                         type
                         marked_for_deletion
                         translation
                         translationatoms{
                            id
                            parent_id
                            content
                         }
                        }
                    triumph
                    }
        }"""



        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_create_gist_admin_header(self, snapshot):
        variables = '{"type": "%s"}' % ("Text")
        query = """mutation create_trans_gist($type: String!){
                    create_translationgist(type: $type) {
                        translationgist {
                         id
                         type
                         marked_for_deletion
                         translation
                         translationatoms{
                            id
                            parent_id
                            content
                         }
                        }
                    triumph
                    }
        }"""

        response = self.graphql_request(query, variables, header=self.admin_header)
        snapshot.assert_match(response.json_body)

    def test_delete_gist_no_header(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('4', '4')
        query = """mutation delete_translationgist($id: LingvodocID!){
                    delete_translationgist(id: $id) {
                        translationgist {
                         id
                         type
                         marked_for_deletion
                         translation
                         translationatoms{
                            id
                            parent_id
                            content
                         }
                        }
                    triumph
                    }
        }"""

        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)

    def test_delete_gist_not_owners_header(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('3', '4')
        query = """mutation delete_translationgist($id: LingvodocID!){
                    delete_translationgist(id: $id) {
                        translationgist {
                         id
                         type
                         marked_for_deletion
                         translation
                         translationatoms{
                            id
                            parent_id
                            content
                         }
                        }
                    triumph
                    }
        }"""

        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_delete_gist_owner_header(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('4', '7')
        query = """mutation delete_translationgist($id: LingvodocID!){
                    delete_translationgist(id: $id) {
                        translationgist {
                         id
                         type
                         marked_for_deletion
                         translation
                         translationatoms{
                            id
                            parent_id
                            content
                         }
                        }
                    triumph
                    }
        }"""

        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_delete_gist_admin_header(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('3', '7')
        query = """mutation delete_translationgist($id: LingvodocID!){
                    delete_translationgist(id: $id) {
                        translationgist {
                         id
                         type
                         marked_for_deletion
                         translation
                         translationatoms{
                            id
                            parent_id
                            content
                         }
                        }
                    triumph
                    }
        }"""

        response = self.graphql_request(query, variables, header=self.admin_header)
        snapshot.assert_match(response.json_body)

#################################################################
#                       Atoms tests
#################################################################

    def test_get_atom(self, snapshot):
        variables = '{"id": [%s, %s]}' % ('1', '8')
        query = '''query getAtom ($id: LingvodocID!){
                    translationatom(id: $id) {
                      id
                      parent_id
                      marked_for_deletion
                      content
                      locale_id
                    }
        }'''
        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)

    def test_create_atom_no_header(self, snapshot):
        variables = '{"parent_id": [%s, %s], "locale_id": %s, "content": "%s"}' % ('1', '61', '7', "test atom content")
        query = """mutation create_atom ($parent_id: LingvodocID!, $locale_id: Int!, $content: String!){
                    create_translationatom(parent_id: $parent_id, locale_id: $locale_id, content: $content) {
                         translationatom{
                            id
                            parent_id
                            content
                            marked_for_deletion
                            locale_id
                         }
                    triumph
                    }
        }"""

        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)

    def test_create_atom_user_header(self, snapshot):
        variables = '{"parent_id": [%s, %s], "locale_id": %s, "content": "%s"}' % ('1', '61', '5', "test atom content")
        query = """mutation create_atom ($parent_id: LingvodocID!, $locale_id: Int!, $content: String!){
                    create_translationatom(parent_id: $parent_id, locale_id: $locale_id, content: $content) {
                         translationatom{
                            id
                            parent_id
                            content
                            marked_for_deletion
                            locale_id
                         }
                    triumph
                    }
        }"""

        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_create_atom_admin_header(self, snapshot):
        variables = '{"parent_id": [%s, %s], "locale_id": %s, "content": "%s"}' % ('1', '61', '6', "test atom content")
        query = """mutation create_atom ($parent_id: LingvodocID!, $locale_id: Int!, $content: String!){
                    create_translationatom(parent_id: $parent_id, locale_id: $locale_id, content: $content) {
                         translationatom{
                            id
                            parent_id
                            content
                            marked_for_deletion
                            locale_id
                         }
                    triumph
                    }
        }"""

        response = self.graphql_request(query, variables, header=self.admin_header)
        snapshot.assert_match(response.json_body)

    def test_update_atom_no_header(self, snapshot):
        variables = '{"id": [%s, %s], "content": "%s", "locale_id": %s}' % ('4', '8', 'never happends', '20')
        query = """mutation update_translationatom ($id: LingvodocID!, $content: String, $locale_id: Int){
                    update_translationatom (id: $id, content: $content, locale_id: $locale_id) {
                        translationatom{
                            id
                            parent_id
                            content
                            marked_for_deletion
                            locale_id
                         }
                    triumph
                    }
        }"""

        response = self.graphql_request(query, variables)
        snapshot.assert_match(response.json_body)

    def test_update_atom_not_owner_header(self, snapshot):
        variables = '{"id": [%s, %s], "content": "%s", "locale_id": %s}' % ('3', '8', 'never happends', '20')
        query = """mutation update_translationatom ($id: LingvodocID!, $content: String, $locale_id: Int){
                    update_translationatom (id: $id, content: $content, locale_id: $locale_id) {
                        translationatom{
                            id
                            parent_id
                            content
                            marked_for_deletion
                            locale_id
                         }
                    triumph
                    }
        }"""

        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_update_atom_owner_header(self, snapshot):
        variables = '{"id": [%s, %s], "content": "%s", "locale_id": %s}' % ('4', '8', 'test updated content', '21')
        query = """mutation update_translationatom ($id: LingvodocID!, $content: String, $locale_id: Int){
                    update_translationatom (id: $id, content: $content, locale_id: $locale_id) {
                        translationatom{
                            id
                            parent_id
                            content
                            marked_for_deletion
                            locale_id
                         }
                    triumph
                    }
        }"""

        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)

    def test_update_atom_admin_header(self, snapshot):
        variables = '{"id": [%s, %s], "content": "%s", "locale_id": %s}' % ('3', '8', 'test content updated by admin', '22')
        query = """mutation update_translationatom ($id: LingvodocID!, $content: String, $locale_id: Int){
                    update_translationatom (id: $id, content: $content, locale_id: $locale_id) {
                        translationatom{
                            id
                            parent_id
                            content
                            marked_for_deletion
                            locale_id
                         }
                    triumph
                    }
        }"""

        response = self.graphql_request(query, variables, header=self.admin_header)
        snapshot.assert_match(response.json_body)


#################################################################
#                       Dictionary tests
#################################################################
    #
    # def test_get_all_dictionaries_published_true(self, snapshot):
    #     query = '''query DictionaryList {
    #         dictionaries(published: true, mode:1) {
    #             id
    #             translation
    #             parent_id
    #             translation_gist_id
    #             state_translation_gist_id
    #             category
    #             domain
    #         }
    #     }'''
    #     response = self.graphql_request(query, header=self.user_header)
    #     snapshot.assert_match(response.json_body)

    def test_get_perspective_list(self, snapshot):
        variables = '{"id": [%s, %s], "mode": "%s"}' % ('2', '3', 'all')
        query = """query PerspectiveList($id:LingvodocID, $mode:String){
                    perspective (id: $id) {
                        id
                        lexical_entries (mode: $mode){
                                        id
                                        marked_for_deletion
                                        parent_id
                                        entities {
                                                  id
                                                  marked_for_deletion
                                                  parent_id
                                                  content
                                                  locale_id
                                                  data_type
                                                  }
                                        }
                                        columns{
                                                id
                                                parent_id
                                                position
                                                }
                                        marked_for_deletion
                                        authors {
                                                id
                                                name
                                                }
                                        tree {
                                              translation
                                              translation_gist_id
                                              parent_id
                                              id
                                              marked_for_deletion
                                              }
            }
        }"""
        response = self.graphql_request(query, variables, header=self.user_header)
        snapshot.assert_match(response.json_body)