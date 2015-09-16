# import unittest
# import transaction
#
# from pyramid import testing
#
# from lingvodoc.models import DBSession
# from pyramid.httpexceptions import HTTPNotFound, HTTPOk, HTTPBadRequest, HTTPConflict, HTTPInternalServerError
#
#
# class TestViewDictionarySuccessCondition(unittest.TestCase):
#
#     def setUp(self):
#         self.config = testing.setUp()
#         from sqlalchemy import create_engine
#         engine = create_engine('sqlite://')
#         from lingvodoc.models import (
#             Base,
#             Dictionary,
#             Locale,
#             UserEntitiesTranslationString
#             )
#         DBSession.configure(bind=engine)
#         Base.metadata.create_all(engine)
#         with transaction.manager:
#             ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
#             DBSession.add(ru_locale)
#             DBSession.flush()
#             new_uets = UserEntitiesTranslationString(object_id = 1, client_id = 1, locale_id=1,
#                                                      translation_string = 'test', translation = 'working')
#             DBSession.add(new_uets)
#             new_dict=Dictionary(client_id=1, object_id=1, name='test')
#             DBSession.add(new_dict)
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_view_dictionary(self):
#         from lingvodoc.views import view_dictionary
#         request = testing.DummyRequest()
#         request.matchdict['client_id'] = 1
#         request.matchdict['object_id'] = 1
#         response = view_dictionary(request)
#         self.assertEqual(response['status'], HTTPOk.code)
#         self.assertEqual(response['name'], 'working')
#
#
# class TestViewDictionaryFailureCondition(unittest.TestCase):
#
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
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_view_dictionary(self):
#         from lingvodoc.views import view_dictionary
#         request = testing.DummyRequest()
#         request.matchdict['client_id'] = 42
#         request.matchdict['object_id'] = 42
#         response = view_dictionary(request)
#         self.assertEqual(response['status'], HTTPNotFound.code)
#
#
# class TestEditDictionarySuccessCondition(unittest.TestCase):
#
#     def setUp(self):
#         self.config = testing.setUp()
#         import webtest
#         from pyramid import  paster
#         from sqlalchemy import create_engine
#         engine = create_engine('sqlite://')
#         myapp = paster.get_app('testing.ini')
#         self.app = webtest.TestApp(myapp)
#         from lingvodoc.models import (
#             Base,
#             Dictionary,
#             Language,
#             Locale,
#             User,
#             Client,
#             UserEntitiesTranslationString,
#             Passhash
#             )
#         DBSession.configure(bind=engine)
#         Base.metadata.create_all(engine)
#         with transaction.manager:
#             ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
#             DBSession.add(ru_locale)
#             en_locale = Locale(id=2, shortcut="en", intl_name="English")
#             DBSession.add(en_locale)
#             DBSession.flush()
#             new_user = User(id=1, login='test', default_locale_id=1)
#             new_pass = Passhash(password='pass')
#             DBSession.add(new_pass)
#             new_user.password = new_pass
#             DBSession.add(new_user)
#             new_client = Client(id=1, user=new_user)
#             DBSession.add(new_client)
#             DBSession.flush()
#             new_uets = UserEntitiesTranslationString(object_id=1, client_id=1,
#                                                      locale_id=1, translation_string='test',
#                                                      translation='not working')
#             DBSession.add(new_uets)
#             new_lang = Language(client_id=1, object_id=1)
#             DBSession.add(new_lang)
#             new_dict = Dictionary(client_id=1, object_id=1, name='test')
#             DBSession.add(new_dict)
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_edit_dictionary_name(self):
#         from lingvodoc.models import (
#             Base,
#             Dictionary,
#             Language,
#             UserEntitiesTranslationString
#             )
#         response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
#         response = self.app.put_json('/dictionary/1/1', params={'name_translation': 'working'})
#         self.assertEqual(response.status_int, HTTPOk.code)
#         dictionary = DBSession.query(Dictionary).filter_by(client_id=1, object_id=1).first()
#         self.assertNotEqual(dictionary, None)
#         uets = DBSession.query(UserEntitiesTranslationString).\
#             filter_by(translation_string=dictionary.name, locale_id=1).first()
#         self.assertNotEqual(uets, None)
#         self.assertEqual(uets.translation, 'working')
#
#
# class TestEditDictionaryFailureCondition(unittest.TestCase):
#
#     def setUp(self):
#         self.config = testing.setUp()
#         import webtest
#         from pyramid import  paster
#         from sqlalchemy import create_engine
#         engine = create_engine('sqlite://')
#         myapp = paster.get_app('testing.ini')
#         self.app = webtest.TestApp(myapp)
#         from lingvodoc.models import (
#             Base,
#             Locale,
#             User,
#             Passhash,
#             Client
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
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_edit_dictionary(self):
#         response = self.app.put_json('/dictionary/42/42',
#                                      params={'name': 'imastring', 'translation': 'imatranslation'},
#                                      status = HTTPBadRequest.code)
#         self.assertEqual(response.status_int, HTTPBadRequest.code)
#
#
# class TestDeleteDictionarySuccessCondition(unittest.TestCase):
#
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
#             new_dict = Dictionary(client_id=1, object_id=1, name='test')
#             DBSession.add(new_dict)
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_delete_dictionary(self):
#         from lingvodoc.views import delete_dictionary
#         from lingvodoc.models import (
#             Dictionary
#             )
#         request = testing.DummyRequest()
#         request.matchdict['client_id'] = 1
#         request.matchdict['object_id'] = 1
#         response = delete_dictionary(request)
#
#         self.assertEqual(response['status'], HTTPOk.code)
#         dictionary = DBSession.query(Dictionary).filter_by(client_id=1, object_id=1).first()
#         self.assertNotEqual(dictionary, None)
#         self.assertEqual(dictionary.marked_for_deletion, True)
#
#
# class TestDeleteDictionaryFailureCondition(unittest.TestCase):
#
#     def setUp(self):
#         self.config = testing.setUp()
#         from sqlalchemy import create_engine
#         engine = create_engine('sqlite://')
#         from lingvodoc.models import (
#             Base
#             )
#         DBSession.configure(bind=engine)
#         Base.metadata.create_all(engine)
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_delete_dictionary(self):
#         from lingvodoc.views import delete_dictionary
#         request = testing.DummyRequest()
#         request.matchdict['client_id'] = 42
#         request.matchdict['object_id'] = 42
#         response = delete_dictionary(request)
#         self.assertEqual(response['status'], HTTPNotFound.code)
#
#
# class TestCreateDictionarySuccessCondition(unittest.TestCase):
#
#     def setUp(self):
#         self.config = testing.setUp()
#         self.config.testing_securitypolicy(userid='1',
#                                            permissive=True)
#         import webtest
#         from pyramid import  paster
#         from sqlalchemy import create_engine
#         engine = create_engine('sqlite://')
#         myapp = paster.get_app('testing.ini')
#         self.app = webtest.TestApp(myapp)
#         from lingvodoc.models import (
#             Base,
#             User,
#             Client,
#             Passhash,
#             Language,
#             BaseGroup,
#             Locale
#             )
#         DBSession.configure(bind=engine)
#         Base.metadata.create_all(engine)
#         with transaction.manager:
#             ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
#             en_locale = Locale(id=2, shortcut="en", intl_name="English")
#             DBSession.add(ru_locale)
#             DBSession.add(en_locale)
#             DBSession.flush()
#             new_user = User(id=1, login='test', default_locale_id = 1)
#             new_pass = Passhash(password='pass')
#             DBSession.add(new_pass)
#             new_user.password = new_pass
#             DBSession.add(new_user)
#             new_client = Client(id=1, user=new_user)
#             DBSession.add(new_client)
#             new_language = Language(client_id=1, object_id=1, translation_string = 'WHAT')
#             DBSession.add(new_language)
#             new_base_group = BaseGroup(id=1, dictionary_default=True, name='for_testing', readable_name='For testing')
#             DBSession.add(new_base_group)
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_create_dictionary(self):
#         from lingvodoc.models import (
#             Dictionary,
#             Group
#              )
#         response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
#         response = self.app.post_json('/dictionary', params={'name': 'imaname', 'translation':'imaname', 'parent_client_id': 1, 'parent_object_id': 1})
#         self.assertEqual(response.status_int , HTTPOk.code)
#
#         dictionary = DBSession.query(Dictionary).filter_by(name='imaname').first()
#         self.assertNotEqual(dictionary, None)
#         self.assertEqual(dictionary.object_id, 1)
#         self.assertEqual(dictionary.client_id, 2)
#         group = DBSession.query(Group).filter_by(subject='dictionary1_2', base_group_id=1).first()
#         self.assertNotEqual(dictionary, group)
#
#
# class TestCreateDictionaryFailureCondition(unittest.TestCase):
#
#     def setUp(self):
#         self.config = testing.setUp()
#         self.config.testing_securitypolicy(userid='1',
#                                            permissive=True)
#         import webtest
#         from pyramid import  paster
#         from sqlalchemy import create_engine
#         engine = create_engine('sqlite://')
#         myapp = paster.get_app('testing.ini')
#         self.app = webtest.TestApp(myapp)
#         from lingvodoc.models import (
#             Base,
#             User,
#             Client,
#             Passhash
#             )
#         DBSession.configure(bind=engine)
#         Base.metadata.create_all(engine)
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_create_dictionary(self):
#         from lingvodoc.views import create_language
#         from lingvodoc.models import (
#             Base,
#             Dictionary,
#             Language
#              )
#         response = self.app.post_json('/dictionary', params={'name': 'imastring'}, status = HTTPBadRequest.code)
#         self.assertEqual(response.status_int, HTTPBadRequest.code)
#
#
# class TestViewDictionaryStatusSuccessCondition(unittest.TestCase):
#
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
#             new_dict = Dictionary(client_id=1, object_id=1, name='test', state='WiP')
#             DBSession.add(new_dict)
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_view_dictionary_status(self):
#         from lingvodoc.views import view_dictionary_status
#         request = testing.DummyRequest()
#         request.matchdict['client_id'] = 1
#         request.matchdict['object_id'] = 1
#         response = view_dictionary_status(request)
#         self.assertEqual(response['status'], HTTPOk.code)
#         self.assertEqual(response['state'], 'WiP')
#
#
# class TestViewDictionaryStatusFailureCondition(unittest.TestCase):
#
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
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_view_dictionary_status(self):
#         from lingvodoc.views import view_dictionary_status
#         request = testing.DummyRequest()
#         request.matchdict['client_id'] = 42
#         request.matchdict['object_id'] = 42
#         response = view_dictionary_status(request)
#         self.assertEqual(response['status'], HTTPNotFound.code)
#
#
# class TestEditDictionaryStatusSuccessCondition(unittest.TestCase):
#
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
#             new_dict = Dictionary(client_id=1, object_id=1, name='test', state='WiP')
#             DBSession.add(new_dict)
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_edit_dictionary_status(self):
#         from lingvodoc.views import edit_dictionary_status
#         from lingvodoc.models import Dictionary
#         request = testing.DummyRequest()
#         request.matchdict['client_id'] = 1
#         request.matchdict['object_id'] = 1
#         request.json_body={'state':'testing'}
#         response = edit_dictionary_status(request)
#         self.assertEqual(response['status'], HTTPOk.code)
#         dictionary = DBSession.query(Dictionary).filter_by(client_id=1, object_id=1).first()
#         self.assertNotEqual(dictionary, None)
#         self.assertEqual(dictionary.state, 'testing')
#
#
# class TestEditDictionaryStatusFailureCondition(unittest.TestCase):
#
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
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_edit_dictionary_status(self):
#         from lingvodoc.views import edit_dictionary_status
#         from lingvodoc.models import Dictionary
#         request = testing.DummyRequest()
#         request.matchdict['client_id'] = 42
#         request.matchdict['object_id'] = 42
#         request.json_body={'state':'testing'}
#         response = edit_dictionary_status(request)
#         self.assertEqual(response['status'], HTTPNotFound.code)
#
#
# class TestViewDictionaryRolesSuccessCondition(unittest.TestCase):
#
#     def setUp(self):
#         self.config = testing.setUp()
#         import webtest
#         from pyramid import  paster
#         from sqlalchemy import create_engine
#         engine = create_engine('sqlite://')
#         myapp = paster.get_app('testing.ini')
#         self.app = webtest.TestApp(myapp)
#         from lingvodoc.models import (
#             Base,
#             Dictionary,
#             Locale,
#             Client,
#             User,
#             Passhash,
#             Language,
#             BaseGroup,
#             Group
#             )
#         DBSession.configure(bind=engine)
#         Base.metadata.create_all(engine)
#         with transaction.manager:
#             ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
#             en_locale = Locale(id=2, shortcut="en", intl_name="English")
#             DBSession.add(ru_locale)
#             DBSession.add(en_locale)
#             DBSession.flush()
#             new_user = User(login='test', default_locale_id = 1)
#             new_pass = Passhash(password='pass')
#             DBSession.add(new_pass)
#             new_user.password = new_pass
#             DBSession.add(new_user)
#             new_user2 = User(login='test2', default_locale_id = 1)
#             new_pass = Passhash(password='pass')
#             DBSession.add(new_pass)
#             new_user2.password = new_pass
#             DBSession.add(new_user2)
#             new_user3 = User(login='test3', default_locale_id = 1)
#             new_pass = Passhash(password='pass')
#             DBSession.add(new_pass)
#             new_user3.password = new_pass
#             DBSession.add(new_user3)
#             new_user4 = User(login='test4', default_locale_id = 1)
#             new_pass = Passhash(password='pass')
#             DBSession.add(new_pass)
#             new_user4.password = new_pass
#             DBSession.add(new_user4)
#             DBSession.flush()
#             new_client = Client(id=1, user=new_user)
#             DBSession.add(new_client)
#             DBSession.flush()
#             new_language = Language(client_id=1, object_id=1, translation_string = 'WHAT')
#             DBSession.add(new_language)
#             new_base_group = BaseGroup(id=1, dictionary_default=True, name='for_testing', readable_name='For testing')
#             DBSession.add(new_base_group)
#             DBSession.flush()
#             new_base_group2 = BaseGroup(id=2, dictionary_default=True, name='for_testing2', readable_name='For testing 2')
#             DBSession.add(new_base_group2)
#             DBSession.flush()
#             new_dict = Dictionary(client_id=1, object_id=1, name='test', state='WiP')
#             DBSession.add(new_dict)
#             new_group = Group(parent = new_base_group, subject = 'dictionary1_1')
#             new_group.users.append(new_user)
#             new_group.users.append(new_user3)
#             new_group2 = Group(parent = new_base_group2, subject = 'dictionary1_1')
#             new_group2.users.append(new_user)
#             new_group2.users.append(new_user2)
#             new_group2.users.append(new_user4)
#             DBSession.add(new_group)
#             DBSession.add(new_group2)
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_view_dictionary_roles(self):
#         from lingvodoc.views import view_dictionary_roles
#         request = testing.DummyRequest()
#         request.matchdict['client_id'] = 1
#         request.matchdict['object_id'] = 1
#         response = view_dictionary_roles(request)
#         self.assertEqual(response['status'], HTTPOk.code)
#         self.assertEqual(response['roles'], {'For testing': [1, 3], 'For testing 2': [1,2,4]})
#
#
# class TestViewDictionaryRolesFailureCondition(unittest.TestCase):
#
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
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_view_dictionary_roles(self):
#         from lingvodoc.views import view_dictionary_roles
#         request = testing.DummyRequest()
#         request.matchdict['client_id'] = 42
#         request.matchdict['object_id'] = 42
#         response = view_dictionary_roles(request)
#         self.assertEqual(response['status'], HTTPNotFound.code)
#
#
# class TestEditDictionaryRolesSuccessCondition(unittest.TestCase):
#
#     def setUp(self):
#         self.config = testing.setUp()
#         self.config.testing_securitypolicy(userid='1',
#                                            permissive=True)
#         import webtest
#         from pyramid import paster
#         from sqlalchemy import create_engine
#         engine = create_engine('sqlite://')
#         myapp = paster.get_app('testing.ini')
#         self.app = webtest.TestApp(myapp)
#         from lingvodoc.models import (
#             Base,
#             Dictionary,
#             Locale,
#             Client,
#             User,
#             Passhash,
#             Language,
#             BaseGroup,
#             Group
#             )
#         DBSession.configure(bind=engine)
#         Base.metadata.create_all(engine)
#         with transaction.manager:
#             ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
#             en_locale = Locale(id=2, shortcut="en", intl_name="English")
#             DBSession.add(ru_locale)
#             DBSession.add(en_locale)
#             DBSession.flush()
#             new_user = User(login='test', default_locale_id = 1)
#             new_pass = Passhash(password='pass')
#             DBSession.add(new_pass)
#             new_user.password = new_pass
#             DBSession.add(new_user)
#             new_user2 = User(login='test2', default_locale_id = 1)
#             new_pass = Passhash(password='pass')
#             DBSession.add(new_pass)
#             new_user2.password = new_pass
#             DBSession.add(new_user2)
#             DBSession.flush()
#             new_client = Client(id=1, user=new_user)
#             DBSession.add(new_client)
#             DBSession.flush()
#             new_language = Language(client_id=1, object_id=1, translation_string = 'WHAT')
#             DBSession.add(new_language)
#             new_base_group = BaseGroup(id=1, dictionary_default=True, name='for_testing', readable_name='For testing')
#             DBSession.add(new_base_group)
#             DBSession.flush()
#             new_base_group2 = BaseGroup(id=2, dictionary_default=True, name='for_testing2', readable_name='For testing 2')
#             DBSession.add(new_base_group2)
#             DBSession.flush()
#             new_dict = Dictionary(client_id=1, object_id=1, name='test', state='WiP')
#             DBSession.add(new_dict)
#             new_group = Group(parent = new_base_group, subject = 'dictionary1_1')
#             new_group.users.append(new_user)
#             new_group2 = Group(parent = new_base_group2, subject = 'dictionary1_1')
#             new_group2.users.append(new_user)
#             DBSession.add(new_group)
#             DBSession.add(new_group2)
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_edit_dictionary_roles(self):
#         from lingvodoc.models import Group
#         request = testing.DummyRequest()
#         response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
#         response = self.app.post_json('/dictionary/1/1/roles', params={'user_id': 2, 'role_names': ['for_testing','for_testing2']})
#         self.assertEqual(response.status_int , HTTPOk.code)
#         groups = DBSession.query(Group).filter(Group.base_group_id.in_([1,2])).filter_by(subject='dictionary1_1').all()
#         self.assertNotEqual(groups, [])
#         for group in groups:
#             users = []
#             for user in group.users:
#                 users += [user.id]
#             self.assertEqual(users, [1,2])
#
#
# class TestDeleteDictionaryRolesSuccessCondition(unittest.TestCase):
#
#     def setUp(self):
#         self.config = testing.setUp()
#         self.config.testing_securitypolicy(userid='1',
#                                            permissive=True)
#         import webtest
#         from pyramid import paster
#         from sqlalchemy import create_engine
#         engine = create_engine('sqlite://')
#         myapp = paster.get_app('testing.ini')
#         self.app = webtest.TestApp(myapp)
#         from lingvodoc.models import (
#             Base,
#             Dictionary,
#             Locale,
#             Client,
#             User,
#             Passhash,
#             Language,
#             BaseGroup,
#             Group
#             )
#         DBSession.configure(bind=engine)
#         Base.metadata.create_all(engine)
#         with transaction.manager:
#             ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
#             en_locale = Locale(id=2, shortcut="en", intl_name="English")
#             DBSession.add(ru_locale)
#             DBSession.add(en_locale)
#             DBSession.flush()
#             new_user = User(login='test', default_locale_id = 1)
#             new_pass = Passhash(password='pass')
#             DBSession.add(new_pass)
#             new_user.password = new_pass
#             DBSession.add(new_user)
#             new_user2 = User(login='test2', default_locale_id = 1)
#             new_pass = Passhash(password='pass')
#             DBSession.add(new_pass)
#             new_user2.password = new_pass
#             DBSession.add(new_user2)
#             DBSession.flush()
#             new_client = Client(id=1, user=new_user)
#             DBSession.add(new_client)
#             DBSession.flush()
#             new_language = Language(client_id=1, object_id=1, translation_string = 'WHAT')
#             DBSession.add(new_language)
#             new_base_group = BaseGroup(id=1, dictionary_default=True, name='for_testing', readable_name='For testing')
#             DBSession.add(new_base_group)
#             DBSession.flush()
#             new_base_group2 = BaseGroup(id=2, dictionary_default=True, name='for_testing2', readable_name='For testing 2')
#             DBSession.add(new_base_group2)
#             DBSession.flush()
#             new_dict = Dictionary(client_id=1, object_id=1, name='test', state='WiP')
#             DBSession.add(new_dict)
#             new_group = Group(parent = new_base_group, subject = 'dictionary1_1')
#             new_group.users.append(new_user)
#             DBSession.flush()
#             new_group.users.append(new_user2)
#             DBSession.flush()
#             DBSession.add(new_group)
#             DBSession.flush()
#             new_group2 = Group(parent = new_base_group2, subject = 'dictionary1_1')
#             new_group2.users.append(new_user)
#             DBSession.flush()
#             new_group.users.append(new_user2)
#             DBSession.flush()
#             DBSession.add(new_group2)
#             DBSession.flush()
#
#     def tearDown(self):
#         DBSession.remove()
#         testing.tearDown()
#
#     def test_delete_dictionary_roles(self):
#         from lingvodoc.models import Group
#         response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
#         response = self.app.delete_json('/dictionary/1/1/roles', params={'user_id': 2, 'role_names': ['for_testing','for_testing2']})
#         self.assertEqual(response.status_int , HTTPOk.code)
#         groups = DBSession.query(Group).filter(Group.base_group_id.in_([1,2])).filter_by(subject='dictionary1_1').all()
#         self.assertNotEqual(groups, [])
#         for group in groups:
#             users = []
#             for user in group.users:
#                 users += [user.id]
#             self.assertEqual(users, [1])
