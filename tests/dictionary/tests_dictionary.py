from tests.tests import MyTestCase
from tests.common import initValuesFactory
from tests.common import load_correct_answers

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


class NewTestClass(MyTestCase):

    def testlogin(self):
        self.signup_common()
        response = self.app.get('/user')
        correct_answer = {'intl_name': 'test', 'login': 'test', 'organizations': [],
                          'is_active': 'True',  'name': 'test', 'email': 'test@test.com',
                          'default_locale_id': None, 'birthday': '1970-01-01', 'about': None}

        self.assertDictEqual(response.json, correct_answer, stop_words=['id', 'signup_date'])


class DictionaryTest(MyTestCase):

    def setUp(self):
        super(DictionaryTest, self).setUp()
        self.id_tester = self.signup_common()
        self.id_u1 = self.signup_common('user1')
        self.id_u2 = self.signup_common('user2')
        self.id_u3 = self.signup_common('user3')
        self.id_u4 = self.signup_common('user4')
        self.id_l1 = self.create_language('language1')
        self.id_l2 = self.create_language('language2')
        self.id_l3 = self.create_language('language3')
        self.id_l4 = self.create_language('language4')

    def _build_ordered_lists(self, response, correct_answer):
        answer = sorted(correct_answer, key=lambda x: (x['client_id'], x['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        response = response.json
        result = list()
        for i in response['dictionaries']:
            self.assertIn('client_id', i)
            self.assertIn('object_id', i)
            result.append(dict(client_id = i['client_id'], object_id = i['object_id']))
        result = sorted(result, key=lambda x: (x['client_id'], x['object_id']))
        return (result, answer)

    # Tests 'dictionaries' API call
    def testDictionaries(self):
        correct_answers = load_correct_answers("dictionary/answers_dictionaries.json")

        self.login_common('user1')
        dict_1 = self.create_dictionary('user1_dict1', self.id_l1)
        self.login_common('user2')
        dict_2 = self.create_dictionary('user2_dict1', self.id_l2)
        self.login_common('user3')
        dict_3 = self.create_dictionary('user3_dict1', self.id_l3)

        # Tests filtering by user
        test_name = "filter_by_user_1"
        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [self.id_u1, self.id_u2]})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        test_name = "filter_by_user_2"
        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [self.id_u3]})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, correct_answers[test_name], set_like=True)

        test_name = "filter_by_user_3"
        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [self.id_u4]})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        # Tests filtering by languages
        test_name = "filter_by_language_1"
        response = self.app.post_json('/dictionaries',
                                      params = {'languages': [self.id_l1, self.id_l2]})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        test_name = "filter_by_language_2"
        response = self.app.post_json('/dictionaries',
                                      params = {'languages': [self.id_l3]})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        test_name = "filter_by_language_3"
        response = self.app.post_json('/dictionaries',
                                      params = {'languages': [self.id_l4]})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        test_name = "filter_by_user_language_1"
        # Tests filtering by users and languages
        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [self.id_u2, self.id_u3],
                                                'languages': [self.id_l1, self.id_l2]})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        test_name = "filter_by_user_language_2"
        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [self.id_u3, self.id_u4],
                                                'languages': [self.id_l1,self. id_l2]})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        test_name = "filter_by_user_language_3"
        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [self.id_u1, self.id_u2, self.id_u3, self.id_u4],
                                                'languages': [self.id_l1, self.id_l2, self.id_l3, self.id_l4]})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        test_name = "filter_by_user_language_4"
        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [], 'languages': []})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

    # Tests 'dictionary_info' API call
    def testDictionaryInfo(self):
        correct_answers = load_correct_answers("dictionary/answers_dictionary_info.json")
        self.login_common('user1')
        dict_1 = self.create_dictionary('user1_dict1', self.id_l1)

        persp_1 = self.create_perspective('translation_string1', dict_1, "Published", False)
        persp_2 = self.create_perspective('translation_string2', dict_1, "Published", False)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/fields'
                                % (1, 6, 1, 7)) # 1 1 1 1 with old
        fields = response.json
        response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/fields'
                                      % (dict_1['client_id'],
                                         dict_1['object_id'],
                                         persp_1['client_id'],
                                         persp_1['object_id']),
                                      params=fields)

        test_name = "empty_dict"
        response = self.app.get('/dictionary/%s/%s/info' % (dict_1['client_id'], dict_1['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        dictionary_roles = initValuesFactory.get_role_params()
        for k in dictionary_roles["roles_users"]:
            dictionary_roles["roles_users"][k] += [self.id_u1, self.id_u2]

        response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']),
                                      params=dictionary_roles)
        response = self.app.get('/dictionary/%s/%s/roles' % (dict_1['client_id'], dict_1['object_id']))

        to_be_approved = list()
        response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/lexical_entries' %
                              (dict_1['client_id'], dict_1['object_id'],
                               persp_1['client_id'], persp_1['object_id']), params={'count': 3})
        to_be_approved.append(self.add_l1e(dict_1, persp_1, response.json[0], 'translation1', 'Translation'))
        to_be_approved.append(self.add_l1e(dict_1, persp_1, response.json[1], 'translation2', 'Translation'))
        to_be_approved.append(self.add_l1e(dict_1, persp_1, response.json[0], 'text1', 'Word'))
        to_be_approved.append(self.add_l1e(dict_1, persp_1, response.json[0], 'text2', 'Word'))
        self.login_common(username='user2')
        # We don't want to approve this entity
        self.add_l1e(dict_1, persp_1, response.json[1], 'text3', 'Word')
        to_be_approved.append(self.add_l1e(dict_1, persp_1, response.json[1], 'translation3', 'Translation'))
        to_be_approved.append(self.add_l1e(dict_1, persp_1, response.json[2], 'transcription1', 'Transcription'))

        self.login_common(username='user1')
        response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/lexical_entries' %
                              (dict_1['client_id'], dict_1['object_id'],
                               persp_2['client_id'], persp_2['object_id']), params={'count': 2})
        self.add_l1e(dict_1, persp_2, response.json[0], 'text1', 'Word')
        to_be_approved.append(self.add_l1e(dict_1, persp_2, response.json[1], 'translation1', 'Translation'))

        list(map(lambda x: x.update({"type": 'leveloneentity'}), to_be_approved))
        response = self.app.patch_json(
            '/dictionary/%s/%s/perspective/%s/%s/approve' % (dict_1['client_id'], dict_1['object_id'],
                                                             persp_1['client_id'], persp_1['object_id']),
            params={"entities": to_be_approved}
        )

        test_name = "filled_dict"
        response = self.app.get('/dictionary/%s/%s/info' %
                                (dict_1['client_id'], dict_1['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])


class ConvertedDictionaryTest(MyTestCase):

    def test_dict_convert(self):
        import hashlib
        from time import sleep
        import json
        import os
        from werkzeug.utils import secure_filename
        real_filename = 'dictionary/test_dict_convert.sqlite'
        filename = secure_filename(real_filename)
        user_id = self.signup_common()
        self.login_common()
        root_ids = self.create_language('Корень')
        first_hash = hashlib.md5(open(real_filename, 'rb').read()).hexdigest()
        response = self.app.post('/blob', params = {'data_type':'dialeqt_dictionary'},
                                 upload_files=([('blob', real_filename)]))
        self.assertEqual(response.status_int, HTTPOk.code)
        blob_ids = response.json
        response = self.app.get('/blobs/%s/%s' % (blob_ids['client_id'],
                                                          blob_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        file_response = self.app.get(response.json['content'])
        second_hash = hashlib.md5(file_response.body).hexdigest()
        self.assertEqual(first_hash, second_hash)
        response = self.app.post_json('/convert_check', params={'blob_client_id': blob_ids['client_id'],
                                                         'blob_object_id': blob_ids['object_id']})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, [])
        # a = input()
        response = self.app.post_json('/convert', params={'blob_client_id': blob_ids['client_id'],
                                                         'blob_object_id': blob_ids['object_id'],
                                                          'parent_client_id':root_ids['client_id'],
                                                          'parent_object_id':root_ids['object_id']})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertDictEqual(response.json, {"status": "Your dictionary is being converted."
                                                       " Wait 5-15 minutes and you will see new dictionary in your dashboard."})
        not_found = True
        for i in range(3):
            response = self.app.post_json('/dictionaries', params={'user_created': [user_id]})
            if response.json['dictionaries']:
                not_found = False
                break
            sleep(10)
        if not_found:
            self.assertEqual('error', 'dictionary was not found')
        dict_ids = response.json['dictionaries'][0]
        for i in range(20):
            response = self.app.get('/dictionary/%s/%s/state' % (dict_ids['client_id'], dict_ids['object_id']))
            if response.json['status'].lower() == 'Converting 100%'.lower():
                break
            sleep(60)
        response = self.app.get('/dictionary/%s/%s/perspectives' % (dict_ids['client_id'], dict_ids['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        persp_ids = response.json['perspectives'][0]
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/all'
                                % (dict_ids['client_id'],
                                   dict_ids['object_id'],
                                   persp_ids['client_id'],
                                   persp_ids['object_id']))
        # Uncomment to create json
        json_file = open('dictionary/test_dict_convert.json', 'w')
        json_file.write(json.dumps(response.json))
        json_file.close()

        json_file = open('dictionary/test_dict_convert.json', 'r')
        correct_answer = json.loads(json_file.read())
        self.assertDictEqual(response.json, correct_answer, set_like= True)
