class initValuesFactory:

    @staticmethod
    def get_role_params(users=None):
        if users is None: users = []
        return {'roles_users':
                {"Can create lexical entries": users,
                 "Can get perspective role list": users,
                 "Can resign users from dictionary editors": users,
                 "Can approve lexical entries and publish": users,
                 "Can create perspective roles and assign collaborators": users,
                 "Can edit perspective": users,
                 "Can delete perspective": users,
                 "Can delete lexical entries": users,
                 "Can deactivate lexical entries": users,
                 "Can view unpublished lexical entries": users,
                 "Can view published lexical entries": users}
        }