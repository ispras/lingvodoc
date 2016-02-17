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

class NewTestClass(MyTestCase):

    def testlogin(self):
        self.signup_common()
        response = self.app.get('/user')
        correct_answer = {'intl_name': 'test', 'login': 'test', 'organizations': [],
                          'is_active': 'True',  'name': 'test', 'email': 'test@test.com',
                          'default_locale_id': None, 'birthday': '1970-01-01', 'about': None}

        self.assertDictEqual(response.json, correct_answer, stop_words=['id', 'signup_date'])


class DictionaryTest(MyTestCase):

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

    # Tests 'dictionaries' API call case a)
    def testDictionaries(self):
        id_tester = self.signup_common()
        id_u1 = self.signup_common('user1')
        id_u2 = self.signup_common('user2')
        id_u3 = self.signup_common('user3')
        id_u4 = self.signup_common('user4')
        id_l1 = self.create_language('language1')
        id_l2 = self.create_language('language2')
        id_l3 = self.create_language('language3')
        id_l4 = self.create_language('language4')

        self.login_common('user1')
        dict_1 = self.create_dictionary('user1_dict1', id_l1)
        self.login_common('user2')
        dict_2 = self.create_dictionary('user2_dict1', id_l2)
        self.login_common('user3')
        dict_3 = self.create_dictionary('user3_dict1', id_l3)

        # Tests filtering by user
        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [id_u1, id_u2]})
        result, answer = self._build_ordered_lists(response, [dict_1, dict_2])
        self.assertEqual(result, answer)

        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [id_u3]})
        result, answer = self._build_ordered_lists(response, [dict_3])
        self.assertEqual(result, answer)

        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [id_u4]})
        result, answer = self._build_ordered_lists(response, [])
        self.assertFalse(result)

        # Tests filtering by languages
        response = self.app.post_json('/dictionaries',
                                      params = {'languages': [id_l1, id_l2]})
        result, answer = self._build_ordered_lists(response, [dict_1, dict_2])
        self.assertEqual(result, answer)

        response = self.app.post_json('/dictionaries',
                                      params = {'languages': [id_l3]})
        result, answer = self._build_ordered_lists(response, [dict_3])
        self.assertEqual(result, answer)

        response = self.app.post_json('/dictionaries',
                                      params = {'languages': [id_l4]})
        result, answer = self._build_ordered_lists(response, [])
        self.assertFalse(result)

        # Tests filtering by users and languages
        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [id_u2, id_u3], 'languages': [id_l1, id_l2]})
        result, answer = self._build_ordered_lists(response, [dict_2])
        self.assertEqual(result, answer)

        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [id_u3, id_u4], 'languages': [id_l1, id_l2]})
        result, answer = self._build_ordered_lists(response, [])
        self.assertFalse(result)

        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [id_u1, id_u2, id_u3, id_u4],
                                                'languages': [id_l1, id_l2, id_l3, id_l4]})
        result, answer = self._build_ordered_lists(response, [dict_1, dict_2, dict_3])
        self.assertEqual(result, answer)

        response = self.app.post_json('/dictionaries',
                                      params = {'user_created': [], 'languages': []})
        result, answer = self._build_ordered_lists(
            response, [dict_1, dict_2, dict_3] + [{'client_id': 1, 'object_id': 1}])
        self.assertEqual(result, answer)

    def testDictionaryInfo(self):
        id_u1 = self.signup_common('user1', 'user1')
        id_u2 = self.signup_common('user2', 'user1')
        id_l1 = self.create_language('language1')
        dict_1 = self.create_dictionary('user1_dict1', id_l1)
        response = self.app.get('/dictionary/%s/%s/info' % (dict_1['client_id'], dict_1['object_id']))
        self.assertDictEqual(response.json, {"count": []})
        print(response)
        # TODO: change dictionary roles
        persp_1 = self.create_perspective('translation_string1', dict_1, "Published", False)
        persp_2 = self.create_perspective('translation_string2', dict_1, "Published", False)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/fields'
                                % (1, 1, 1, 1))
        fields = response.json
        response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/fields'
                                      % (dict_1['client_id'],
                                         dict_1['object_id'],
                                         persp_1['client_id'],
                                         persp_1['object_id']),
                                      params=fields)
        response = self.app.get('/dictionary/%s/%s/info' % (dict_1['client_id'], dict_1['object_id']))
        self.assertDictEqual(response.json, {"count": []})
        print(response)
        response = self.app.get('/dictionary/%s/%s/roles' % (dict_1['client_id'], dict_1['object_id']))
        print(response)

        params = {'roles_users':
                              {"Can create lexical entries": [id_u1, id_u2],
                               "Can get perspective role list": [id_u1, id_u2],
                               "Can resign users from dictionary editors": [id_u1, id_u2],
                               "Can approve lexical entries and publish": [id_u1, id_u2],
                               "Can create perspective roles and assign collaborators":[id_u1, id_u2],
                               "Can edit perspective": [id_u1, id_u2],
                               "Can delete perspective": [id_u1, id_u2],
                               "Can delete lexical entries": [id_u1, id_u2],
                               "Can deactivate lexical entries": [id_u1, id_u2],
                               "Can view unpublished lexical entries": [id_u1, id_u2],
                               "Can view published lexical entries": [id_u1, id_u2]}
                  }

        response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']), params=params)
        response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/lexical_entries' %
                              (dict_1['client_id'], dict_1['object_id'],
                               persp_1['client_id'], persp_1['object_id']), params={'count': 3})
        to_be_approved = list()
        to_be_approved.append(self.add_l1e(dict_1, persp_1, response.json[0], 'text1', 'Word'))
        to_be_approved.append(self.add_l1e(dict_1, persp_1, response.json[0], 'text2', 'Word'))
        to_be_approved.append(self.add_l1e(dict_1, persp_1, response.json[0], 'translation1', 'Translation'))
        to_be_approved.append(self.add_l1e(dict_1, persp_1, response.json[1], 'translation2', 'Translation'))
        self.login_common(username='user2')
        # We don't want to approve this entity
        self.add_l1e(dict_1, persp_1, response.json[1], 'text3', 'Word')
        to_be_approved.append(self.add_l1e(dict_1, persp_1, response.json[1], 'translation3', 'Translation'))
        to_be_approved.append(self.add_l1e(dict_1, persp_1, response.json[2], 'transcription1', 'Transcription'))
        list(map(lambda x: x.update({"type": 'leveloneentity'}), to_be_approved))
        response = self.app.patch_json(
            '/dictionary/%s/%s/perspective/%s/%s/approve' % (dict_1['client_id'], dict_1['object_id'],
                                                             persp_1['client_id'], persp_1['object_id']),
            params={"entities": to_be_approved}
        )

        response = self.app.get('/dictionary/%s/%s/info' %
                                (dict_1['client_id'], dict_1['object_id']))
