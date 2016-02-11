from tests.tests import MyTestCase

class NewTestClass(MyTestCase):

    def testlogin(self):
        self.signup_common()
        response = self.app.get('/user')
        correct_answer = {'intl_name': 'test', 'login': 'test', 'organizations': [],
                          'is_active': 'True',  'name': 'test', 'email': 'test@test.com',
                          'default_locale_id': None, 'birthday': '1970-01-01', 'about': None}

        self.assertDictEqual(response.json, correct_answer, stop_words=['id', 'signup_date'])