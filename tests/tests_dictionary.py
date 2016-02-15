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

        def buildLists(correct_answer, users=[], languages=[]):
            answer = sorted(correct_answer, key=lambda x: (x['client_id'], x['object_id']))
            response = self.app.post_json('/dictionaries',
                                          params = {'user_created': users, 'languages': languages})
            self.assertEqual(response.status_int, HTTPOk.code)
            response = response.json
            result = list()
            for i in response['dictionaries']:
                self.assertIn('client_id', i)
                self.assertIn('object_id', i)
                result.append(dict(client_id = i['client_id'], object_id = i['object_id']))
            result = sorted(result, key=lambda x: (x['client_id'], x['object_id']))
            return (result, answer)

        # TODO: uncomment tests after the bug is fixed

        # Tests filtering by user
        result, answer = buildLists([dict_1, dict_2], users=[id_u1, id_u2])
        self.assertEqual(result, answer)
        result, answer = buildLists([dict_3], [id_u3])
        self.assertEqual(result, answer)
        result, answer = buildLists([], [id_u4])
        self.assertFalse(result)

        # # Tests filtering by languages
        # result, answer = buildLists([dict_1, dict_2], languages=[id_l1, id_l2])
        # self.assertEqual(result, answer)
        # result, answer = buildLists([dict_3], languages=[id_l3])
        # self.assertEqual(result, answer)
        # result, answer = buildLists([], languages=[id_l4])
        # self.assertFalse(result)
        #
        # # Tests filtering by users and languages
        # result, answer = buildLists([dict_2], users = [id_u2, id_u3], languages=[id_l1, id_l2])
        # self.assertEqual(result, answer)
        # result, answer = buildLists([], users = [id_u3, id_u4], languages=[id_l1, id_l2])
        # self.assertFalse(result)
        # result, answer = buildLists([],users = [id_u1, id_u2, id_u3, id_u4],
        #                             languages=[id_l1, id_l2, id_l3, id_l4])
        # self.assertFalse(result)
        # result, answer = buildLists([], users = [], languages=[])
        # self.assertFalse(result)
