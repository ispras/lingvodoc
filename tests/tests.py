import unittest
import transaction

from pyramid import testing

from lingvodoc.models import DBSession
from pyramid.httpexceptions import HTTPNotFound, HTTPOk, HTTPBadRequest, HTTPConflict, HTTPInternalServerError
#
#
# class SimpleTestDictionariesListSuccessCondition(unittest.TestCase):
#     def setUp(self):
#         self.config = testing.setUp()
#         from sqlalchemy import create_engine
#         engine = create_engine('sqlite://')
#         from lingvodoc.models import (
#             Base,
#             Dictionary
#             )
#         DBSession.configure(bind=engine)
#         Base.metadata.create_all(engine)
#         with transaction.manager:
#             new_dict=Dictionary(client_id=1, object_id=1, name='test')
#             DBSession.add(new_dict)
#             new_dict=Dictionary(client_id=1, object_id=2, name='test2')
#             DBSession.add(new_dict)
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_passing_view(self):
#         from lingvodoc.views import dictionaries_list
#         request = testing.DummyRequest()
#         request.json_body={}
#         response = dictionaries_list(request)
#
#         self.assertEqual(response['status'], HTTPOk.code)
#         self.assertEqual(response['dictionaries'], [{'object_id': 1, 'client_id': 1}, {'object_id':2,'client_id':1}])


class TestDictionariesListSuccessCondition(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        import webtest
        from pyramid import paster
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        myapp = paster.get_app('testing.ini')
        self.app = webtest.TestApp(myapp)
        from lingvodoc.models import (
            Base,
            Dictionary,
            Language,
            Organization,
            Locale,
            User,
            Passhash,
            Client,
            DictionaryPerspective
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
            DBSession.add(ru_locale)
            en_locale = Locale(id=2, shortcut="en", intl_name="English")
            DBSession.add(en_locale)
            DBSession.flush()
            new_user = User(id=1, login='test', default_locale_id = 1)
            new_pass = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user.password = new_pass
            DBSession.add(new_user)
            new_client = Client(id=1, user=new_user)
            DBSession.add(new_client)
            new_user2 = User(id=2, login='test2', default_locale_id = 1)
            new_pass2 = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user2.password = new_pass2
            DBSession.add(new_user2)
            new_client = Client(id=2, user=new_user2)
            DBSession.add(new_client)
            new_client = Client(id=3, user=new_user)
            DBSession.add(new_client)
            DBSession.flush()
            new_user3 = User(id=3, login='test3', default_locale_id = 1)
            new_pass3 = Passhash(password='pass')
            DBSession.add(new_pass3)
            new_user3.password = new_pass3
            DBSession.add(new_user3)
            new_client = Client(id=4, user=new_user3)
            DBSession.add(new_client)
            new_user4 = User(id=4, login='test4', default_locale_id = 1)
            new_pass4 = Passhash(password='pass')
            DBSession.add(new_pass4)
            new_user4.password = new_pass4
            DBSession.add(new_user4)
            new_client = Client(id=5, user=new_user4)
            DBSession.add(new_client)
            new_lang1 = Language(client_id=1, object_id=1, translation_string='head')
            DBSession.add(new_lang1)
            new_lang2 = Language(client_id=2, object_id=5, translation_string='left son', parent=new_lang1)
            DBSession.add(new_lang2)
            new_lang3 = Language(client_id=1, object_id=3, translation_string='right son', parent=new_lang1)
            DBSession.add(new_lang3)
            new_lang4 = Language(client_id=2, object_id=4, translation_string='first grand son', parent=new_lang3)
            DBSession.add(new_lang4)
            new_lang5 = Language(client_id=1, object_id=5, translation_string='second grand son', parent=new_lang3)
            DBSession.add(new_lang5)
            new_lang6 = Language(client_id=1, object_id=6, translation_string='third grand son', parent=new_lang3)
            DBSession.add(new_lang6)
            new_lang7 = Language(client_id=1, object_id=7, translation_string='grand grand son', parent=new_lang5)
            DBSession.add(new_lang7)
            new_lang8 = Language(client_id=1, object_id=8, translation_string='second head')
            DBSession.add(new_lang8)
            new_lang9 = Language(client_id=1, object_id=9, translation_string='second left son', parent=new_lang8)
            DBSession.add(new_lang9)
            new_lang10 = Language(client_id=1, object_id=10, translation_string='second right son', parent=new_lang8)
            DBSession.add(new_lang10)
            new_org1 = Organization(name='first')
            new_org1.users.append(new_user)
            new_org1.users.append(new_user3)
            DBSession.add(new_org1)
            new_org2 = Organization(name='second')
            DBSession.add(new_org2)
            new_dict1 = Dictionary(client_id=1, object_id=1, name='test', parent=new_lang3)
            DBSession.add(new_dict1)
            new_dict2 = Dictionary(client_id=2, object_id=1, name='test2', parent=new_lang5)
            DBSession.add(new_dict2)
            new_dict3 = Dictionary(client_id=3, object_id=1, name='test3', parent=new_lang8)
            DBSession.add(new_dict3)
            new_dict4 = Dictionary(client_id=5, object_id=1, name='test4', parent=new_lang9)
            DBSession.add(new_dict4)
            new_dict5 = Dictionary(client_id=4, object_id=1, name='test5', parent=new_lang10)
            DBSession.add(new_dict5)
            new_dict6 = Dictionary(client_id=4, object_id=2, name='test3', parent=new_lang4)
            DBSession.add(new_dict6)
            new_dict_persp = DictionaryPerspective(client_id=4, object_id=1, name='test', parent=new_dict2)
            DBSession.add(new_dict_persp)


    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_language_filter(self):
        response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
        response = self.app.post_json('/dictionaries',
                                      params={'languages': [{'client_id': 1, 'object_id': 3}]})
        self.assertEqual(response.status_int, HTTPOk.code)
        # self.assertCountEqual(response.json['dictionaries'],
        #                  [{'object_id': 1, 'client_id': 1}, {'object_id': 1, 'client_id': 2}])
        # print("LOOK HERE", response.json['dictionaries'])

    def test_no_filter(self):
        response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
        response = self.app.post_json('/dictionaries', params={})
        self.assertEqual(response.status_int, HTTPOk.code)
        # print()
        # print("WTF", response.json)
        # print()

    def test_languages_list(self):
        response = self.app.get('/languages')
        self.assertEqual(response.status_int, HTTPOk.code)
        # print("ANSWER TO EVERYTHING", response.json['languages'])

class TestEmptyListSuccessCondition(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        import webtest
        from pyramid import paster
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        myapp = paster.get_app('testing.ini')
        self.app = webtest.TestApp(myapp)
        from lingvodoc.models import (
            Base,
            Dictionary,
            Language,
            Organization,
            Locale,
            User,
            Passhash,
            Client,
            DictionaryPerspective
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            pass


    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_languages_list(self):
        response = self.app.get('/languages')
        self.assertEqual(response.status_int, HTTPOk.code)
        # print("ANSWER TO EVERYTHING 2", response.json['languages'])

    # def test_user_created_filter(self):
    #     response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
    #     response = self.app.post_json('/dictionaries', params={'user_created': 1})
    #     self.assertEqual(response.status_int, HTTPOk.code)
    #     self.assertEqual(response.json['dictionaries'],
    #                      [{'object_id': 1, 'client_id': 1}, {'object_id': 1, 'client_id': 3}])
    #     response = self.app.post_json('/dictionaries', params={'user_created': 2})
    #     self.assertEqual(response.status_int, HTTPOk.code)
    #     self.assertEqual(response.json['dictionaries'],
    #                      [{'object_id': 1, 'client_id': 2}])
    #
    # def test_user_participated_filter(self):
    #     response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
    #     response = self.app.post_json('/dictionaries', params={'user_participated': [3]})
    #     self.assertEqual(response.status_int, HTTPOk.code)
    #     self.assertEqual(response.json['dictionaries'],
    #                      [{'object_id': 1, 'client_id': 2}, {'object_id': 1, 'client_id': 4}])
    #
    # def test_organization_participated(self):
    #     response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
    #     response = self.app.post_json('/dictionaries', params={'organization_participated': 1})
    #     self.assertEqual(response.status_int, HTTPOk.code)
    #     dicts = [{'object_id': 1, 'client_id': 2},
    #              {'object_id': 1, 'client_id': 1},
    #              {'object_id': 1, 'client_id': 4},
    #              {'object_id': 1, 'client_id': 3}]
    #     self.assertCountEqual(response.json['dictionaries'], dicts)

#
# class TestViewPerspectiveFieldsSuccessCondition(unittest.TestCase):
#
#     def setUp(self):
#         self.config = testing.setUp()
#         import webtest
#         from pyramid import paster
#         from sqlalchemy import create_engine
#         engine = create_engine('sqlite://')
#         myapp = paster.get_app('testing.ini')
#         self.app = webtest.TestApp(myapp)
#         from lingvodoc.models import (
#             Base,
#             DictionaryPerspectiveField,
#             DictionaryPerspective,
#             Dictionary,
#             User,
#             Locale,
#             Passhash,
#             Client,
#             UserEntitiesTranslationString
#             )
#         DBSession.configure(bind=engine)
#         Base.metadata.create_all(engine)
#         with transaction.manager:
#             ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
#             DBSession.add(ru_locale)
#             en_locale = Locale(id=2, shortcut="en", intl_name="English")
#             DBSession.add(en_locale)
#             DBSession.flush()
#             new_user = User(id=1, login='test', default_locale_id = 1)
#             new_pass = Passhash(password='pass')
#             DBSession.add(new_pass)
#             new_user.password = new_pass
#             DBSession.add(new_user)
#             new_client = Client(id=1, user=new_user)
#             DBSession.add(new_client)
#             DBSession.flush()
#             persp = DictionaryPerspective(client_id=1, object_id=1, name='test',
#                                              parent_client_id=1, parent_object_id=1)
#             DBSession.add(persp)
#             new_dict = Dictionary(client_id=1, object_id=1, name='test', state='WiP')
#             DBSession.add(new_dict)
#             field = DictionaryPerspectiveField(parent = persp, client_id=1, object_id=1,
#                                                entity_type='protoform', data_type='text',
#                                                level='L1E', state='enabled', position=1)
#             DBSession.add(field)
#             field1 = DictionaryPerspectiveField(parent=persp, client_id=1, object_id=2,entity_type='sound',
#                                                 data_type='sound', level='L1E', state = 'enabled', position=2)
#             DBSession.add(field1)
#             field2 = DictionaryPerspectiveField(parent_entity=field1, parent=persp, client_id=1,
#                                                 object_id=3, entity_type='praat', level='L2E',
#                                                 data_type='markup', state='enabled', position=1)
#             DBSession.add(field2)
#             fieldgroup = DictionaryPerspectiveField(parent=persp, client_id=1, object_id=4,
#                                                     entity_type='protoform', data_type='text',
#                                                     level='L1E', group='testgroup', state='enabled', position=3)
#             DBSession.add(fieldgroup)
#             grouping = DictionaryPerspectiveField(parent=persp, client_id=1, object_id=5, entity_type='etymology',
#                                                   data_type='grouping_tag', level='GE', state='enabled', position=4)
#             DBSession.add(grouping)
#             field3 = DictionaryPerspectiveField(parent_entity=field1, parent=persp, client_id=1,
#                                                 object_id=6, entity_type='praat2', level='L2E',
#                                                 data_type='markup', state='enabled', position=1)
#             DBSession.add(field3)
#             new_uets = UserEntitiesTranslationString(object_id=1, client_id = 1,
#                                                      locale_id=1, translation_string='protoform',
#                                                      translation='protoform1')
#             DBSession.add(new_uets)
#             new_uets = UserEntitiesTranslationString(object_id=2, client_id = 1,
#                                                      locale_id=1, translation_string='sound',
#                                                      translation='sound1')
#             DBSession.add(new_uets)
#             new_uets = UserEntitiesTranslationString(object_id=3, client_id = 1,
#                                                      locale_id=1, translation_string='text',
#                                                      translation='text1')
#             DBSession.add(new_uets)
#             new_uets = UserEntitiesTranslationString(object_id=4, client_id = 1,
#                                                      locale_id=1, translation_string='etymology',
#                                                      translation='etymology1')
#             DBSession.add(new_uets)
#             new_uets = UserEntitiesTranslationString(object_id=5, client_id = 1,
#                                                      locale_id=1, translation_string='grouping_tag',
#                                                      translation='grouping_tag1')
#             DBSession.add(new_uets)
#             new_uets = UserEntitiesTranslationString(object_id=6, client_id = 1,
#                                                      locale_id=1, translation_string='testgroup',
#                                                      translation='testgroup1')
#             DBSession.add(new_uets)
#             new_uets = UserEntitiesTranslationString(object_id=7, client_id = 1,
#                                                      locale_id=1, translation_string='praat',
#                                                      translation='praat1')
#             DBSession.add(new_uets)
#             new_uets = UserEntitiesTranslationString(object_id=8, client_id = 1,
#                                                      locale_id=1, translation_string='markup',
#                                                      translation='markup1')
#             DBSession.add(new_uets)
#             new_uets = UserEntitiesTranslationString(object_id=9, client_id = 1,
#                                                      locale_id=1, translation_string='praat2',
#                                                      translation='praat3')
#             DBSession.add(new_uets)
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_view_perspective_fields(self):
#         response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
#         response = self.app.get('/dictionary/1/1/perspective/1/1/fields')
#         self.assertEqual(response.status_int, HTTPOk.code)
#         self.assertCountEqual(response.json['fields'],  # may be problems with checking in 'contains'
#                          [
#                              {'entity_type': 'protoform1', 'data_type': 'text1', 'state': 'enabled', 'position': 1},
#                              {'entity_type': 'sound1', 'data_type': 'sound1', 'state': 'enabled', 'position': 2,
#                               'contains': [{'entity_type': 'praat1',
#                                             'data_type': 'markup1',
#                                             'state': 'enabled',
#                                             'position': 1},
#                                            {'entity_type': 'praat3',
#                                             'data_type': 'markup1',
#                                             'state': 'enabled',
#                                             'position': 1}]},
#                              {'entity_type': 'protoform1', 'data_type': 'text1',
#                               'state': 'enabled', 'group': 'testgroup1', 'position': 3},
#                              {'entity_type': 'etymology1', 'data_type': 'grouping_tag1',
#                               'state': 'enabled', 'position': 4}
#                          ])
#
#
# class TestDeletePerspectiveFieldsSuccessCondition(unittest.TestCase):
#
#     def setUp(self):
#         self.config = testing.setUp()
#         import webtest
#         from pyramid import paster
#         from sqlalchemy import create_engine
#         engine = create_engine('sqlite://')
#         myapp = paster.get_app('testing.ini')
#         self.app = webtest.TestApp(myapp)
#         from lingvodoc.models import (
#             Base,
#             DictionaryPerspectiveField,
#             DictionaryPerspective,
#             Dictionary,
#             User,
#             Locale,
#             Passhash,
#             Client,
#             UserEntitiesTranslationString
#             )
#         DBSession.configure(bind=engine)
#         Base.metadata.create_all(engine)
#         with transaction.manager:
#             ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
#             DBSession.add(ru_locale)
#             en_locale = Locale(id=2, shortcut="en", intl_name="English")
#             DBSession.add(en_locale)
#             DBSession.flush()
#             new_user = User(id=1, login='test', default_locale_id = 1)
#             new_pass = Passhash(password='pass')
#             DBSession.add(new_pass)
#             new_user.password = new_pass
#             DBSession.add(new_user)
#             new_client = Client(id=1, user=new_user)
#             DBSession.add(new_client)
#             DBSession.flush()
#             persp = DictionaryPerspective(client_id=1, object_id=1, name='test',
#                                              parent_client_id=1, parent_object_id=1)
#             DBSession.add(persp)
#             new_dict = Dictionary(client_id=1, object_id=1, name='test', state='WiP')
#             DBSession.add(new_dict)
#             field = DictionaryPerspectiveField(parent = persp, client_id=1, object_id=1,
#                                                entity_type='protoform', data_type='text',
#                                                level='L1E', state='enabled', position=1)
#             DBSession.add(field)
#             new_uets = UserEntitiesTranslationString(object_id=1, client_id = 1,
#                                                      locale_id=1, translation_string='protoform',
#                                                      translation='protoform1')
#             DBSession.add(new_uets)
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_delete_perspective_fields(self):
#         from lingvodoc.models import DictionaryPerspectiveField
#         response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
#         response = self.app.delete_json('/dictionary/1/1/perspective/1/1/fields',
#                                         params={'field_object_id': 1, 'field_client_id': 1})
#         self.assertEqual(response.status_int, HTTPOk.code)
#         field = DBSession.query(DictionaryPerspectiveField).filter_by(client_id=1, object_id=1).first()
#         self.assertNotEqual(field, None)
#         self.assertEqual(field.marked_for_deletion, True)
#
#
# class TestCreatePerspectiveFieldsSuccessCondition(unittest.TestCase):
#
#     def setUp(self):
#         self.config = testing.setUp()
#         import webtest
#         from pyramid import paster
#         from sqlalchemy import create_engine
#         engine = create_engine('sqlite://')
#         myapp = paster.get_app('testing.ini')
#         self.app = webtest.TestApp(myapp)
#         from lingvodoc.models import (
#             Base,
#             DictionaryPerspectiveField,
#             DictionaryPerspective,
#             Dictionary,
#             User,
#             Locale,
#             Passhash,
#             Client,
#             UserEntitiesTranslationString
#             )
#         DBSession.configure(bind=engine)
#         Base.metadata.create_all(engine)
#         with transaction.manager:
#             ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
#             DBSession.add(ru_locale)
#             en_locale = Locale(id=2, shortcut="en", intl_name="English")
#             DBSession.add(en_locale)
#             DBSession.flush()
#             new_user = User(id=1, login='test', default_locale_id = 1)
#             new_pass = Passhash(password='pass')
#             DBSession.add(new_pass)
#             new_user.password = new_pass
#             DBSession.add(new_user)
#             new_client = Client(id=1, user=new_user)
#             DBSession.add(new_client)
#             DBSession.flush()
#             new_dict = Dictionary(client_id=1, object_id=1, name='test', state='WiP')
#             DBSession.add(new_dict)
#             persp = DictionaryPerspective(client_id=1, object_id=1, name='test',
#                                           parent_client_id=1, parent_object_id=1)
#             DBSession.add(persp)
#             DBSession.flush()
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_view_perspective_fields(self):
#         from lingvodoc.models import DictionaryPerspectiveField
#         fields = [{'entity_type_translation': 'protoform1', 'entity_type': 'protoform',
#                    'data_type_translation': 'text1', 'data_type': 'text',
#                    'state': 'enabled', 'level': 'L1E', 'position': 1},
#                   {'entity_type_translation': 'sound1', 'entity_type': 'sound', 'data_type_translation': 'sound1',
#                    'data_type': 'sound', 'state': 'enabled',
#                    'contains': [{'entity_type_translation': 'praat1',
#                                  'entity_type': 'praat',
#                                  'data_type_translation': 'markup1',
#                                  'data_type': 'markup',
#                                  'state': 'enabled', 'level': 'L2E', 'position': 1}], 'level': 'L1E', 'position': 2},
#                   {'entity_type_translation': 'protoform1', 'entity_type': 'protoform',
#                    'data_type_translation': 'text1', 'data_type': 'text', 'state': 'enabled',
#                    'group_translation':'testgroup1', 'group':'testgroup', 'level': 'L1E', 'position': 3},
#                   {'entity_type_translation': 'etymology1', 'entity_type': 'etymology',
#                    'data_type_translation': 'grouping_tag1', 'data_type': 'grouping_tag',
#                    'state': 'enabled', 'level': 'GE', 'position': 4}]
#
#         response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
#         response = self.app.post_json('/dictionary/1/1/perspective/1/1/fields', params={'fields': fields})
#         self.assertEqual(response.status_int, HTTPOk.code)
#         response = self.app.get('/dictionary/1/1/perspective/1/1/fields')
#         self.assertEqual(response.status_int, HTTPOk.code)
#         field = DBSession.query(DictionaryPerspectiveField).filter_by(parent_client_id=1,
#                                                                       parent_object_id=1,
#                                                                       entity_type='protoform',
#                                                                       data_type='text',
#                                                                       state='enabled',
#                                                                       level='L1E',
#                                                                       group=None,
#                                                                       position=1).first()
#         self.assertNotEqual(field, None)
#         field = DBSession.query(DictionaryPerspectiveField).filter_by(parent_client_id=1,
#                                                                       parent_object_id=1,
#                                                                       entity_type='sound',
#                                                                       data_type='sound',
#                                                                       state='enabled',
#                                                                       level='L1E',
#                                                                       position=2).first()
#         self.assertNotEqual(field, None)
#         field = DBSession.query(DictionaryPerspectiveField).filter_by(parent_client_id=1,
#                                                                       parent_object_id=1,
#                                                                       entity_type='praat',
#                                                                       data_type='markup',
#                                                                       state='enabled',
#                                                                       level='L2E',
#                                                                       position=1).first()
#         self.assertNotEqual(field, None)
#         field = DBSession.query(DictionaryPerspectiveField).filter_by(parent_client_id=1,
#                                                                       parent_object_id=1,
#                                                                       entity_type='protoform',
#                                                                       data_type='text',
#                                                                       state='enabled',
#                                                                       level='L1E',
#                                                                       group='testgroup',
#                                                                       position=3).first()
#         self.assertNotEqual(field, None)
#         field = DBSession.query(DictionaryPerspectiveField).filter_by(parent_client_id=1,
#                                                                       parent_object_id=1,
#                                                                       entity_type='etymology',
#                                                                       data_type='grouping_tag',
#                                                                       state='enabled',
#                                                                       level='GE',
#                                                                       position=4).first()
#         self.assertNotEqual(field, None)


class TestDictionariesList(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        import webtest
        from pyramid import paster
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        myapp = paster.get_app('testing.ini')
        self.app = webtest.TestApp(myapp)
        from lingvodoc.models import (
            Base,
            Dictionary,
            Language,
            Organization,
            Locale,
            User,
            Passhash,
            Client,
            DictionaryPerspective
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
            DBSession.add(ru_locale)
            en_locale = Locale(id=2, shortcut="en", intl_name="English")
            DBSession.add(en_locale)
            DBSession.flush()
            new_user = User(id=1, login='test', default_locale_id = 1)
            new_pass = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user.password = new_pass
            DBSession.add(new_user)
            new_client = Client(id=1, user=new_user)
            DBSession.add(new_client)
            new_user2 = User(id=2, login='test2', default_locale_id = 1)
            new_pass2 = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user2.password = new_pass2
            DBSession.add(new_user2)
            new_client = Client(id=2, user=new_user2)
            DBSession.add(new_client)
            new_client = Client(id=3, user=new_user)
            DBSession.add(new_client)
            DBSession.flush()
            new_user3 = User(id=3, login='test3', default_locale_id = 1)
            new_pass3 = Passhash(password='pass')
            DBSession.add(new_pass3)
            new_user3.password = new_pass3
            DBSession.add(new_user3)
            new_client = Client(id=4, user=new_user3)
            DBSession.add(new_client)
            new_user4 = User(id=4, login='test4', default_locale_id = 1)
            new_pass4 = Passhash(password='pass')
            DBSession.add(new_pass4)
            new_user4.password = new_pass4
            DBSession.add(new_user4)
            new_client = Client(id=5, user=new_user4)
            DBSession.add(new_client)
            new_lang1 = Language(client_id=1, object_id=1, translation_string='head')
            DBSession.add(new_lang1)
            new_lang2 = Language(client_id=2, object_id=5, translation_string='left son', parent=new_lang1)
            DBSession.add(new_lang2)
            new_lang3 = Language(client_id=1, object_id=3, translation_string='right son', parent=new_lang1)
            DBSession.add(new_lang3)
            new_lang4 = Language(client_id=2, object_id=4, translation_string='first grand son', parent=new_lang3)
            DBSession.add(new_lang4)
            new_lang5 = Language(client_id=1, object_id=5, translation_string='second grand son', parent=new_lang3)
            DBSession.add(new_lang5)
            new_lang6 = Language(client_id=1, object_id=6, translation_string='third grand son', parent=new_lang3)
            DBSession.add(new_lang6)
            new_lang7 = Language(client_id=1, object_id=7, translation_string='grand grand son', parent=new_lang5)
            DBSession.add(new_lang7)
            new_lang8 = Language(client_id=1, object_id=8, translation_string='second head')
            DBSession.add(new_lang8)
            new_lang9 = Language(client_id=1, object_id=9, translation_string='second left son', parent=new_lang8)
            DBSession.add(new_lang9)
            new_lang10 = Language(client_id=1, object_id=10, translation_string='second right son', parent=new_lang8)
            DBSession.add(new_lang10)
            new_org1 = Organization(name='first')
            new_org1.users.append(new_user)
            new_org1.users.append(new_user3)
            DBSession.add(new_org1)
            new_org2 = Organization(name='second')
            DBSession.add(new_org2)


    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_no_filter(self):
        response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
        response = self.app.post_json('/dictionary',
                                      params={'parent_client_id':1,
                                              'parent_object_id':1,
                                              'name':'dict',
                                              'translation':'name_translation'})
        response = self.app.post_json('/dictionaries', params={'user_created':[1]})
        self.assertEqual(response.status_int, HTTPOk.code)
        print()
        print("WHY", response.json)
        print()