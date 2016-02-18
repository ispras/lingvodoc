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

class PerspectiveTest(MyTestCase):
    def _build_ordered_lists(self, response, correct_answer):
        self.assertEqual(response.status_int, HTTPOk.code)
        answer = sorted(correct_answer, key=lambda x: (x['client_id'], x['object_id']))
        response = response.json
        result = list()
        for i in response['perspectives']:
            self.assertIn('client_id', i)
            self.assertIn('object_id', i)
            result.append(dict(client_id = i['client_id'], object_id = i['object_id']))
        result = sorted(result, key=lambda x: (x['client_id'], x['object_id']))
        return (result, answer)

    def testAllPerspectives(self):
        correct_answers = load_correct_answers("perspective/answers_all_perspectives.json")

        id_tester = self.signup_common()
        id_u1 = self.signup_common('user1', 'user1')
        id_l1 = self.create_language('language1')
        dict_1 = self.create_dictionary('user1_dict1', id_l1)
        default_persp = [
            {"object_id": 1, "client_id": 1},
            {"object_id": 2, "client_id": 1},
            {"object_id": 3, "client_id": 1}
        ]

        test_name = "empty_perspective"
        response = self.app.get('/perspectives',
                                params = {'is_template': False})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        persp_1 = self.create_perspective('translation_string1', dict_1, "Published", False)
        persp_2 = self.create_perspective('translation_string2', dict_1, "Published", True)
        persp_3 = self.create_perspective('translation_string3', dict_1, "Marked", False)
        persp_4 = self.create_perspective('translation_string4', dict_1, "Marked", True)

        test_name = "template_true"
        response = self.app.get('/perspectives',
                                params = {'is_template': True})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        test_name = "template_false"
        response = self.app.get('/perspectives',
                                params = {'is_template': False})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        test_name = "combined_condition_1"
        response = self.app.get('/perspectives',
                                params = {'state': "Published"})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        test_name = "combined_condition_2"
        response = self.app.get('/perspectives',
                                params = {'state': "Marked", 'is_template': False})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        test_name = "missing_state"
        response = self.app.get('/perspectives',
                                params = {'state': "NoState"})
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        test_name = "all"
        response = self.app.get('/perspectives')
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

    def testPerspectives(self):
        correct_answers = load_correct_answers("perspective/answers_perspectives.json")
        id_tester = self.signup_common()
        id_u1 = self.signup_common('user1', 'user1')
        id_l1 = self.create_language('language1')
        dict_1 = self.create_dictionary('user1_dict1', id_l1)
        dict_2 = self.create_dictionary('user1_dict2', id_l1)
        unexisting_dict = {"object_id": 4, "client_id": 4}
        persp_1 = self.create_perspective('translation_string1', dict_1, "Published", False)
        persp_2 = self.create_perspective('translation_string1', dict_1, "Marked", True)

        test_name = "filled_perspective"
        response = self.app.get('/dictionary/%(client_id)s/%(object_id)s/perspectives' % dict_1)
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        test_name = "empty_perspective"
        response = self.app.get('/dictionary/%(client_id)s/%(object_id)s/perspectives' % dict_2)
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        #TODO: catch bad response exception and check it
        # try:
        #     response = self.app.get('/dictionary/%(client_id)s/%(object_id)s/perspectives' % unexisting_dict)
        # except AppError as app_error:
        #
        # self.assertEqual(response.status_int, HTTPNotFound.code)

    def testViewPerspectiveRoles(self):
        correct_answers = load_correct_answers("perspective/answers_view_perspective_roles.json")
        id_tester = self.signup_common()
        id_u1 = self.signup_common('user1', 'user1')
        id_u2 = self.signup_common('user2', 'user1')
        id_u3 = self.signup_common('user3', 'user1')
        id_l1 = self.create_language('language1')
        dict_1 = self.create_dictionary('user1_dict1', id_l1)
        persp_1 = self.create_perspective('translation_string1', dict_1, "Published", False)

        correct_answer = {
            "roles_users": {
                "Can view published lexical entries": [id_u1, id_u2],
                "Can get perspective role list": [id_u1],
                "Can view unpublished lexical entries": [id_u1, id_u2],
                "Can create perspective roles and assign collaborators": [id_u1, id_u2, id_u3],
                "Can approve lexical entries and publish": [id_u1, id_u3],
                "Can resign users from dictionary editors": [id_u1, id_u2],
                "Can create lexical entries": [id_u1],
                "Can edit perspective": [id_u1, id_u2],
                "Can deactivate lexical entries": [id_u1, id_u2],
                "Can delete lexical entries": [id_u1, id_u2],
                "Can delete perspective": [id_u1, id_u2]
            },
            "roles_organizations": {
                "Can view published lexical entries": [],
                "Can get perspective role list": [],
                "Can view unpublished lexical entries": [],
                "Can create perspective roles and assign collaborators": [],
                "Can approve lexical entries and publish": [],
                "Can resign users from dictionary editors": [],
                "Can create lexical entries": [],
                "Can edit perspective": [],
                "Can deactivate lexical entries": [],
                "Can delete lexical entries": [],
                "Can delete perspective": []
            }
        }

        params = initValuesFactory.get_role_params([id_u2])
        params['roles_users']['Can create lexical entries'] = []
        params['roles_users']['Can get perspective role list'] = [id_u1]
        params['roles_users']['Can approve lexical entries and publish'] = [id_u3]
        params['roles_users']['Can create perspective roles and assign collaborators'] = [id_u2, id_u3]

        # Testing get and post
        test_name = "change_several_roles"
        response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']), params=params)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        params = {'roles_users':
                              {"Can view unpublished lexical entries": [id_u3]}}
        test_name = "add_single_role"
        response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']), params=params)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        params = {'roles_users': {}}
        test_name = "empty_test_1"
        response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']), params=params)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        params = {}
        test_name = "empty_test_2"
        response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']), params=params)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        # Testing get and delete
        params = {'roles_users':
                              {"Can view unpublished lexical entries": [id_u3]}}
        test_name = "delete_one_user"
        response = self.app.delete_json('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']), params=params)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        params = {'roles_users':
                              {"Can resign users from dictionary editors": [id_u3]}}
        test_name = "delete_missing_user"
        response = self.app.delete_json('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']), params=params)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        params = {'roles_users':
                              {"Can create perspective roles and assign collaborators": [id_u2, id_u3]}}
        test_name = "delete_several_users"
        response = self.app.delete_json('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']), params=params)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        params = {'roles_users':
                              {}}
        test_name = "empty_delete_test_1"
        response = self.app.delete_json('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']), params=params)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        params = {}
        test_name = "empty_delete_test_2"
        response = self.app.delete_json('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']), params=params)
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/roles' % (dict_1['client_id'],
                                   dict_1['object_id'], persp_1['client_id'], persp_1['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        # TODO: add test for prohibited deletion of the owner from user roles

    def testPerspectiveInfo(self):
        correct_answers = load_correct_answers("perspective/answers_perspective_info.json")
        id_tester = self.signup_common()
        id_u1 = self.signup_common('user1', 'user1')
        id_u2 = self.signup_common('user2', 'user1')
        id_l1 = self.create_language('language1')
        dict_1 = self.create_dictionary('user1_dict1', id_l1)
        persp_1 = self.create_perspective('translation_string1', dict_1, "Published", False)

        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/fields'
                                % (1, 1, 1, 1))
        fields = response.json
        response = self.app.post_json('/dictionary/%s/%s/perspective/%s/%s/fields'
                                      % (dict_1['client_id'],
                                         dict_1['object_id'],
                                         persp_1['client_id'],
                                         persp_1['object_id']),
                                      params=fields)

        test_name = "empty_perspective"
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/info' %
                                (dict_1['client_id'], dict_1['object_id'], persp_1['client_id'], persp_1['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])

        params = initValuesFactory.get_role_params([id_u1, id_u2])
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

        test_name = "filled_perspective"
        response = self.app.get('/dictionary/%s/%s/perspective/%s/%s/info' %
                                (dict_1['client_id'], dict_1['object_id'], persp_1['client_id'], persp_1['object_id']))
        self.assertEqual(response.status_int, HTTPOk.code)
        self.assertEqual(response.json, correct_answers[test_name])
