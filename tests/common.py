# 
# NOTE
#
# See information on how tests are organized and how they should work in the tests' package __init__.py file
# (currently lingvodoc/tests/__init__.py).
#


import json
import os


def load_correct_answers(test_name):
        with open(os.path.join(os.path.dirname(__file__), test_name)) as data_file:
            data = json.load(data_file)
        return data


class initValuesFactory:

    @staticmethod
    def get_role_params(users=None):
        if users is None: users = []
        return {'roles_users':
                {"Can create lexical entries": users,
                 "Can get perspective role list": users,
                 "Can resign users from perspective editors": users,
                 "Can approve lexical entries and publish": users,
                 "Can create perspective roles and assign collaborators": users,
                 "Can edit perspective": users,
                 "Can delete perspective": users,
                 "Can delete lexical entries": users,
                 "Can deactivate lexical entries": users,
                 "Can view unpublished lexical entries": users,
                 "Can view published lexical entries": users}
        }
