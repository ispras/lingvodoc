from tests.tests import MyTestCase

from pyramid.httpexceptions import (
    HTTPNotFound,
    HTTPOk,
    HTTPBadRequest,
    HTTPConflict,
    HTTPInternalServerError,
    HTTPUnauthorized,
    HTTPFound,
    HTTPForbidden
)
import json


def func_name():
    import traceback
    return traceback.extract_stack(None, 2)[0][2]


class TestHelperMethods(MyTestCase):

    def testsignup(self):
        id = self.signup_common()
        response = self.app.get('/user')
        correct_answer = {'intl_name': 'test', 'login': 'test', 'organizations': [],
                          'is_active': 'True',  'name': 'test', 'email': 'test@test.com',
                          'default_locale_id': None, 'birthday': '1970-01-01', 'about': None}

        self.assertDictEqual(response.json, correct_answer, stop_words=['id', 'signup_date'])
        # print('==========')
        # print(func_name())
        # print(json.dumps(response.json))

    def testlogin(self):
        id = self.signup_common('user1', 'user1')
        self.login_common('user1')
        response = self.app.get('/user')
        correct_answer = {'intl_name': 'user1', 'login': 'user1', 'organizations': [],
                          'is_active': 'True',  'name': 'test', 'email': 'user1@test.com',
                          'default_locale_id': None, 'birthday': '1970-01-01', 'about': None}

        self.assertDictEqual(response.json, correct_answer, stop_words=['id', 'signup_date'])
        # print('==========')
        # print(func_name())
        # print(json.dumps(response.json))

    def testlogout(self):
        id = self.signup_common()
        response = self.app.request('/logout')
        self.assertEqual(response.status_int, HTTPFound.code)

        response = self.app.get('/user', status=HTTPNotFound.code)
        self.assertEqual(response.status_int, HTTPNotFound.code)
        self.login_common()
        response = self.app.get('/user')
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json['id'], id)

    def test_create_language(self):
        id = self.signup_common()

        lang_name = 'lang name'
        lang_ids = self.create_language(lang_name)
        response = self.app.get('/language/%s/%s' % (lang_ids['client_id'], lang_ids['object_id']))
        correct_answer = {'client_id': lang_ids['client_id'], 'object_id': lang_ids['object_id'],
                          'locale_exist': False, 'translation': lang_name,
                          'parent_client_id': None,
                          'translation_string': lang_name,
                          'parent_object_id': None}
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, correct_answer)
        # print('==========')
        # print(func_name())
        # print(json.dumps(response.json))

    def test_create_dictionary(self):
        id = self.signup_common()

        lang_name = 'lang name'
        lang_ids = self.create_language(lang_name)
        dict_name = 'dict name'
        dict_ids = self.create_dictionary(dict_name, lang_ids)
        response = self.app.get('/dictionary/%s/%s' % (dict_ids['client_id'], dict_ids['object_id']))
        correct_answer = {'client_id': dict_ids['client_id'], 'object_id': dict_ids['object_id'],
                          'additional_metadata': None,
                          'parent_client_id':  lang_ids['client_id'],
                          'parent_object_id':  lang_ids['object_id'],
                          'translation': dict_name,
                          'translation_string': dict_name,
                          'status': 'WiP'}

        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, correct_answer)
        # print('==========')
        # print(func_name())
        # print(json.dumps(response.json))

    def test_dictionary_change_state(self):
        id = self.signup_common()
        lang_name = 'lang name'
        lang_ids = self.create_language(lang_name)
        dict_name = 'dict name'
        dict_ids = self.create_dictionary(dict_name, lang_ids)

        dict_state = 'dict state'
        self.dictionary_change_state(dict_ids, dict_state)

        response = self.app.get('/dictionary/%s/%s/state' % (dict_ids['client_id'], dict_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, {'status': dict_state})
        # print('==========')
        # print(func_name())
        # print(json.dumps(response.json))

    def test_create_perspective(self):
        id = self.signup_common()
        lang_name = 'lang name'
        lang_ids = self.create_language(lang_name)
        dict_name = 'dict name'
        dict_ids = self.create_dictionary(dict_name, lang_ids)

        persp_name = 'persp name'
        persp_ids = self.create_perspective(persp_name, dict_ids)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s' % (dict_ids['client_id'],dict_ids['object_id'],
                                                                         persp_ids['client_id'], persp_ids['object_id']))
        correct_answer = {'client_id': persp_ids['client_id'], 'object_id': persp_ids['object_id'],
                          'additional_metadata': None,
                          'parent_client_id':  dict_ids['client_id'],
                          'parent_object_id':  dict_ids['object_id'],
                          'translation': persp_name,
                          'translation_string': persp_name,
                          'is_template': False,
                          'marked_for_deletion': False,
                          'status': 'WiP'}
        first_view = response.json
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(first_view, correct_answer)
        response = self.app.get('/perspective/%s/%s' % (persp_ids['client_id'], persp_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, correct_answer)
        # print('==========')
        # print(func_name())
        # print(json.dumps(response.json))

    def test_perspective_change_state(self):
        id = self.signup_common()
        lang_name = 'lang name'
        lang_ids = self.create_language(lang_name)
        dict_name = 'dict name'
        dict_ids = self.create_dictionary(dict_name, lang_ids)
        persp_name = 'persp name'
        persp_ids = self.create_perspective(persp_name, dict_ids)
        persp_state = 'persp state'
        self.perspective_change_state(dict_ids, persp_ids,persp_state)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/state' % (dict_ids['client_id'],dict_ids['object_id'],
                                                                         persp_ids['client_id'], persp_ids['object_id']))

        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, {'status': persp_state})
        # print('==========')
        # print(func_name())
        # print(json.dumps(response.json))

    def test_create_level_one_entity(self):
        id = self.signup_common()
        lang_name = 'lang name'
        lang_ids = self.create_language(lang_name)
        dict_name = 'dict name'
        dict_ids = self.create_dictionary(dict_name, lang_ids)
        persp_name = 'persp name'
        persp_ids = self.create_perspective(persp_name, dict_ids)
        response = self.app.post('/dictionary/%s/%s/perspective/%s/%s/lexical_entry' % (dict_ids['client_id'],dict_ids['object_id'],
                                                                         persp_ids['client_id'], persp_ids['object_id']))
        lex_ids = response.json
        entity_type = 'entity type'
        content = 'content'
        l1e_ids = self.add_l1e(dict_ids,persp_ids,lex_ids, content=content, entity_type=entity_type)

        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/lexical_entry/%s/%s/leveloneentity/%s/%s'
                                % (dict_ids['client_id'],
                                   dict_ids['object_id'],
                                   persp_ids['client_id'],
                                   persp_ids['object_id'],
                                   lex_ids['client_id'],
                                   lex_ids['object_id'],
                                   l1e_ids['client_id'],
                                   l1e_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        correct_answer = {'client_id': l1e_ids['client_id'],
                          'parent_client_id': lex_ids['client_id'],
                          'parent_object_id': lex_ids['object_id'],
                          'object_id': l1e_ids['object_id'],
                          'entity_type': entity_type,
                          'level': 'leveloneentity',
                          'marked_for_deletion': False,
                          'locale_id': 1,
                          'content': content}
        self.assertDictEqual(response.json, correct_answer)
        # print('==========')
        # print(func_name())
        # print(json.dumps(response.json))

    def test_dict_convert_method(self):
        tester_id = self.signup_common()
        dict_ids, persp_ids = self.dict_convert('dictionary/test_dict_lvl2_entity.sqlite', tester_id)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/all'
                                % (dict_ids['client_id'],
                                   dict_ids['object_id'],
                                   persp_ids['client_id'],
                                   persp_ids['object_id']))
        # json_file = open('helper_methods/test_dict_convert.json', 'w')
        # json_file.write(json.dumps(response.json))
        # json_file.close()
        json_file = open('helper_methods/test_dict_convert.json', 'r')
        correct_answer = json.loads(json_file.read())
        self.assertDictEqual(response.json, correct_answer, stop_words=['client_id',
                                                                        'object_id',
                                                                        'parent_client_id',
                                                                        'parent_object_id'], set_like= True)
