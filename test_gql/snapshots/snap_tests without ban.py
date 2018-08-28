# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots['TestConnection.test_give_roles_to_user 1'] = {
    'data': {
        'add_perspective_roles': {
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_get_language 1'] = {
    'data': {
        'language': {
            'dictionaries': [
            ],
            'id': [
                1,
                13
            ],
            'marked_for_deletion': False,
            'parent_id': None,
            'translation': 'English language',
            'translation_gist_id': [
                1,
                3
            ]
        }
    }
}

snapshots['TestConnection.test_get_all_languages 1'] = {
    'data': {
        'languages': [
            {
                'dictionaries': [
                    {
                        'category': 0,
                        'domain': 0,
                        'id': [
                            2,
                            2
                        ],
                        'marked_for_deletion': False,
                        'parent_id': [
                            1,
                            12
                        ],
                        'state_translation_gist_id': [
                            1,
                            189
                        ],
                        'status': 'WiP',
                        'translation': 'Dictionary of Middle-Ob dialect Mansi',
                        'translation_gist_id': [
                            1,
                            61
                        ]
                    }
                ],
                'id': [
                    1,
                    12
                ],
                'marked_for_deletion': False,
                'parent_id': None,
                'translation': 'Russian language',
                'translation_gist_id': [
                    1,
                    2
                ]
            },
            {
                'dictionaries': [
                ],
                'id': [
                    1,
                    13
                ],
                'marked_for_deletion': False,
                'parent_id': None,
                'translation': 'English language',
                'translation_gist_id': [
                    1,
                    3
                ]
            },
            {
                'dictionaries': [
                ],
                'id': [
                    1,
                    14
                ],
                'marked_for_deletion': False,
                'parent_id': None,
                'translation': 'Finnish language',
                'translation_gist_id': [
                    1,
                    4
                ]
            },
            {
                'dictionaries': [
                ],
                'id': [
                    1,
                    15
                ],
                'marked_for_deletion': False,
                'parent_id': None,
                'translation': 'French language',
                'translation_gist_id': [
                    1,
                    5
                ]
            },
            {
                'dictionaries': [
                ],
                'id': [
                    1,
                    16
                ],
                'marked_for_deletion': False,
                'parent_id': None,
                'translation': 'German language',
                'translation_gist_id': [
                    1,
                    6
                ]
            }
        ]
    }
}

snapshots['TestConnection.test_create_language_with_old_gist_none_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "('Invalid client id (not registered on server). Try to logout and then login.', None)"
        }
    ]
}

snapshots['TestConnection.test_create_language_with_old_gist_user_header 1'] = {
    'data': {
        'create_language': {
            'language': {
                'id': [
                    4,
                    2
                ],
                'translation_gist_id': [
                    1,
                    4
                ]
            }
        }
    }
}

snapshots['TestConnection.test_create_language_with_old_gist_admin_header 1'] = {
    'data': {
        'create_language': {
            'language': {
                'id': [
                    3,
                    2
                ],
                'translation_gist_id': [
                    1,
                    4
                ]
            }
        }
    }
}

snapshots['TestConnection.test_create_language_with_new_gist_none_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "('Invalid client id (not registered on server). Try to logout and then login.', None)"
        }
    ]
}

snapshots['TestConnection.test_create_language_with_new_gist_user_header 1'] = {
    'data': {
        'create_language': {
            'language': {
                'id': [
                    4,
                    5
                ],
                'translation_gist_id': [
                    4,
                    3
                ]
            }
        }
    }
}

snapshots['TestConnection.test_create_language_with_new_gist_admin_header 1'] = {
    'data': {
        'create_language': {
            'language': {
                'id': [
                    3,
                    5
                ],
                'translation_gist_id': [
                    3,
                    3
                ]
            }
        }
    }
}

snapshots['TestConnection.test_update_language_no_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "Client None doesn't have 'edit' permissions for 'language' [1, 14]."
        }
    ]
}

snapshots['TestConnection.test_update_language_user_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "Client 4 doesn't have 'edit' permissions for 'language' [1, 14]."
        }
    ]
}

snapshots['TestConnection.test_update_language_admin_header 1'] = {
    'data': {
        'update_language': {
            'language': {
                'id': [
                    1,
                    14
                ],
                'translation_gist_id': [
                    1,
                    2
                ]
            }
        }
    }
}

snapshots['TestConnection.test_delete_language_no_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "Client None doesn't have 'delete' permissions for 'language' [1, 14]."
        }
    ]
}

snapshots['TestConnection.test_delete_language_user_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "Client 4 doesn't have 'delete' permissions for 'language' [1, 14]."
        }
    ]
}

snapshots['TestConnection.test_delete_language_admin_header 1'] = {
    'data': {
        'delete_language': {
            'language': {
                'id': [
                    1,
                    14
                ],
                'marked_for_deletion': True,
                'translation': 'Russian language'
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_get_entity 1'] = {
    'data': {
        'entity': {
            'content': 'lex entity 1',
            'id': [
                2,
                22
            ],
            'marked_for_deletion': False,
            'parent_id': [
                2,
                18
            ]
        }
    }
}

snapshots['TestConnection.test_create_entity_no_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "('Invalid client id (not registered on server). Try to logout and then login.', None)"
        }
    ]
}

snapshots['TestConnection.test_create_entity_user_header 1'] = {
    'data': {
        'create_entity': {
            'entity': {
                'content': 'test_content',
                'id': [
                    4,
                    6
                ],
                'marked_for_deletion': False,
                'parent_id': [
                    2,
                    18
                ],
                'published': False
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_create_entity_admin_header 1'] = {
    'data': {
        'create_entity': {
            'entity': {
                'content': 'test_content',
                'id': [
                    3,
                    6
                ],
                'marked_for_deletion': False,
                'parent_id': [
                    2,
                    18
                ],
                'published': False
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_update_entity_no_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "Client None doesn't have 'create' permissions for 'approve_entities' (2, 3)."
        }
    ]
}

snapshots['TestConnection.test_update_entity_user_header 1'] = {
    'data': {
        'update_entity': {
            'entity': {
                'content': 'lex entity 2',
                'id': [
                    2,
                    23
                ],
                'marked_for_deletion': False,
                'parent_id': [
                    2,
                    19
                ],
                'published': True
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_update_entity_admin_header 1'] = {
    'data': {
        'update_entity': {
            'entity': {
                'content': 'lex entity 1',
                'id': [
                    2,
                    22
                ],
                'marked_for_deletion': False,
                'parent_id': [
                    2,
                    18
                ],
                'published': True
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_delete_entity_no_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "Client None doesn't have 'delete' permissions for 'lexical_entries_and_entities' (2, 3)."
        }
    ]
}

snapshots['TestConnection.test_delete_entity_not_owner_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "Client 4 doesn't have 'delete' permissions for 'lexical_entries_and_entities' (2, 4)."
        }
    ]
}

snapshots['TestConnection.test_delete_entity_owner_header 1'] = {
    'data': {
        'delete_entity': {
            'entity': {
                'content': 'lex entity 1',
                'id': [
                    2,
                    22
                ],
                'marked_for_deletion': True,
                'parent_id': [
                    2,
                    18
                ],
                'published': True
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_delete_entity_admin_header 1'] = {
    'data': {
        'delete_entity': {
            'entity': {
                'content': 'link lex entity 2',
                'id': [
                    2,
                    25
                ],
                'marked_for_deletion': True,
                'parent_id': [
                    2,
                    21
                ],
                'published': False
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_get_gist 1'] = {
    'data': {
        'translationgist': {
            'id': [
                1,
                193
            ],
            'marked_for_deletion': False,
            'translation': 'Word',
            'translationatoms': [
                {
                    'content': 'Word',
                    'id': [
                        1,
                        194
                    ],
                    'marked_for_deletion': False,
                    'parent_id': [
                        1,
                        193
                    ]
                },
                {
                    'content': 'Wort',
                    'id': [
                        1,
                        195
                    ],
                    'marked_for_deletion': False,
                    'parent_id': [
                        1,
                        193
                    ]
                },
                {
                    'content': 'Word',
                    'id': [
                        1,
                        196
                    ],
                    'marked_for_deletion': False,
                    'parent_id': [
                        1,
                        193
                    ]
                }
            ],
            'type': 'Field'
        }
    }
}

snapshots['TestConnection.test_create_gist_no_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "('Invalid client id (not registered on server). Try to logout and then login.', None)"
        }
    ]
}

snapshots['TestConnection.test_create_gist_user_header 1'] = {
    'data': {
        'create_translationgist': {
            'translationgist': {
                'id': [
                    4,
                    7
                ],
                'marked_for_deletion': False,
                'translation': 'Translation missing for all locales',
                'translationatoms': [
                ],
                'type': 'Text'
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_create_gist_admin_header 1'] = {
    'data': {
        'create_translationgist': {
            'translationgist': {
                'id': [
                    3,
                    7
                ],
                'marked_for_deletion': False,
                'translation': 'Translation missing for all locales',
                'translationatoms': [
                ],
                'type': 'Text'
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_delete_gist_no_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "Client None doesn't have 'delete' permissions for 'translations' [4, 4]."
        }
    ]
}

snapshots['TestConnection.test_delete_gist_not_owners_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "Client 4 doesn't have 'delete' permissions for 'translations' [3, 4]."
        }
    ]
}

snapshots['TestConnection.test_delete_gist_owner_header 1'] = {
    'data': {
        'delete_translationgist': {
            'translationgist': {
                'id': [
                    4,
                    7
                ],
                'marked_for_deletion': True,
                'translation': 'Translation missing for all locales',
                'translationatoms': [
                ],
                'type': 'Text'
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_delete_gist_admin_header 1'] = {
    'data': {
        'delete_translationgist': {
            'translationgist': {
                'id': [
                    3,
                    7
                ],
                'marked_for_deletion': True,
                'translation': 'Translation missing for all locales',
                'translationatoms': [
                ],
                'type': 'Text'
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_get_atom 1'] = {
    'data': {
        'translationatom': {
            'content': 'English language',
            'id': [
                1,
                8
            ],
            'locale_id': 2,
            'marked_for_deletion': False,
            'parent_id': [
                1,
                3
            ]
        }
    }
}

snapshots['TestConnection.test_create_atom_no_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "('Invalid client id (not registered on server). Try to logout and then login.', None)"
        }
    ]
}

snapshots['TestConnection.test_create_atom_user_header 1'] = {
    'data': {
        'create_translationatom': {
            'translationatom': {
                'content': 'test atom content',
                'id': [
                    4,
                    8
                ],
                'locale_id': 5,
                'marked_for_deletion': False,
                'parent_id': [
                    1,
                    61
                ]
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_create_atom_admin_header 1'] = {
    'data': {
        'create_translationatom': {
            'translationatom': {
                'content': 'test atom content',
                'id': [
                    3,
                    8
                ],
                'locale_id': 6,
                'marked_for_deletion': False,
                'parent_id': [
                    1,
                    61
                ]
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_update_atom_no_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "Client None doesn't have 'edit' permissions for 'translations' [4, 8]."
        }
    ]
}

snapshots['TestConnection.test_update_atom_not_owner_header 1'] = {
    'data': None,
    'errors': [
        {
            'message': "Client 4 doesn't have 'edit' permissions for 'translations' [3, 8]."
        }
    ]
}

snapshots['TestConnection.test_update_atom_owner_header 1'] = {
    'data': {
        'update_translationatom': {
            'translationatom': {
                'content': 'test updated content',
                'id': [
                    4,
                    8
                ],
                'locale_id': 21,
                'marked_for_deletion': False,
                'parent_id': [
                    1,
                    61
                ]
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_update_atom_admin_header 1'] = {
    'data': {
        'update_translationatom': {
            'translationatom': {
                'content': 'test content updated by admin',
                'id': [
                    3,
                    8
                ],
                'locale_id': 22,
                'marked_for_deletion': False,
                'parent_id': [
                    1,
                    61
                ]
            },
            'triumph': True
        }
    }
}

snapshots['TestConnection.test_get_perspective_list 1'] = {
    'data': {
        'perspective': {
            'authors': [
                {
                    'id': 2,
                    'name': 'Test'
                },
                {
                    'id': 1,
                    'name': 'Администратор'
                },
                {
                    'id': 3,
                    'name': 'tester'
                }
            ],
            'columns': [
                {
                    'id': [
                        2,
                        11
                    ],
                    'parent_id': [
                        2,
                        3
                    ],
                    'position': 1
                },
                {
                    'id': [
                        2,
                        12
                    ],
                    'parent_id': [
                        2,
                        3
                    ],
                    'position': 2
                },
                {
                    'id': [
                        2,
                        13
                    ],
                    'parent_id': [
                        2,
                        3
                    ],
                    'position': 3
                },
                {
                    'id': [
                        2,
                        14
                    ],
                    'parent_id': [
                        2,
                        3
                    ],
                    'position': 4
                }
            ],
            'id': [
                2,
                3
            ],
            'lexical_entries': [
                {
                    'entities': [
                        {
                            'content': 'lex entity 2',
                            'data_type': 'Text',
                            'id': [
                                2,
                                23
                            ],
                            'locale_id': 2,
                            'marked_for_deletion': False,
                            'parent_id': [
                                2,
                                19
                            ]
                        }
                    ],
                    'id': [
                        2,
                        19
                    ],
                    'marked_for_deletion': False,
                    'parent_id': [
                        2,
                        3
                    ]
                },
                {
                    'entities': [
                        {
                            'content': 'test_content',
                            'data_type': 'Text',
                            'id': [
                                4,
                                6
                            ],
                            'locale_id': 2,
                            'marked_for_deletion': False,
                            'parent_id': [
                                2,
                                18
                            ]
                        },
                        {
                            'content': 'test_content',
                            'data_type': 'Text',
                            'id': [
                                3,
                                6
                            ],
                            'locale_id': 2,
                            'marked_for_deletion': False,
                            'parent_id': [
                                2,
                                18
                            ]
                        }
                    ],
                    'id': [
                        2,
                        18
                    ],
                    'marked_for_deletion': False,
                    'parent_id': [
                        2,
                        3
                    ]
                }
            ],
            'marked_for_deletion': False,
            'tree': [
                {
                    'id': [
                        2,
                        3
                    ],
                    'marked_for_deletion': False,
                    'parent_id': [
                        2,
                        2
                    ],
                    'translation': 'Lexical Entries',
                    'translation_gist_id': [
                        1,
                        93
                    ]
                },
                {
                    'id': [
                        2,
                        2
                    ],
                    'marked_for_deletion': False,
                    'parent_id': [
                        1,
                        12
                    ],
                    'translation': 'Dictionary of Middle-Ob dialect Mansi',
                    'translation_gist_id': [
                        1,
                        61
                    ]
                },
                {
                    'id': [
                        1,
                        12
                    ],
                    'marked_for_deletion': False,
                    'parent_id': None,
                    'translation': 'Russian language',
                    'translation_gist_id': [
                        1,
                        2
                    ]
                }
            ]
        }
    }
}
