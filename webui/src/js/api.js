var lingvodoc = {};

lingvodoc.Object = function(clientId, objectId) {

    this.client_id = clientId;
    this.object_id = objectId;
    //this.type = 'abstract';

    this.getId = function() {
        return this.client_id + '' + this.object_id;
    };

    this.export = function() {
        return {};
    }
};
lingvodoc.Object.prototype.equals = function(obj) {
    return !!(this.client_id == obj.client_id && this.object_id == obj.object_id);
};


lingvodoc.Language = function(clientId, objectId, translation, translation_string) {

    lingvodoc.Object.call(this, clientId, objectId);

    this.translation = translation;
    this.translation_string = translation_string;
    this.languages = [];
    this.dictionaries = [];

    this.equals = function(obj) {
        return !!(this.client_id == obj.client_id && this.object_id == obj.object_id);
    };

};
lingvodoc.Language.fromJS = function (js) {
    return new lingvodoc.Language(js.client_id,
        js.object_id,
        js.translation,
        js.translation_string);
};
lingvodoc.Language.prototype = new lingvodoc.Object();
lingvodoc.Language.prototype.constructor = lingvodoc.Language;

lingvodoc.Dictionary = function(clientId, objectId, parentClientId, parentObjectId, translation, translation_string, status) {

    lingvodoc.Object.call(this, clientId, objectId);
    this.parent_client_id = parentClientId;
    this.parent_object_id = parentObjectId;
    this.translation = translation;
    this.translation_string = translation_string;
    this.status = status;
    this.perspectives = [];

    this.equals = function(obj) {
        return lingvodoc.Object.prototype.equals.call(this, obj) &&
            (this.translation == obj.translation);
    };
};
lingvodoc.Dictionary.fromJS = function (js) {
    return new lingvodoc.Dictionary(js.client_id,
        js.object_id,
        js.parent_client_id,
        js.parent_object_id,
        js.translation,
        js.translation_string,
        js.status);
};
lingvodoc.Dictionary.prototype = new lingvodoc.Object();
lingvodoc.Dictionary.prototype.constructor = lingvodoc.Dictionary;

lingvodoc.Perspective = function(client_id, object_id, parent_client_id, parent_object_id,
    translation, translation_string, status, is_template, marked_for_deletion) {

    lingvodoc.Object.call(this, client_id, object_id);

    this.parent_client_id = parent_client_id;
    this.parent_object_id = parent_object_id;
    this.translation = translation;
    this.translation_string = translation_string;
    this.status = status;
    this.is_template = is_template;
    this.marked_for_deletion = marked_for_deletion;
    this.fields = [];

    this.equals = function(obj) {
        return lingvodoc.Object.prototype.equals.call(this, obj) &&
             (this.translation == obj.translation);
    };
};
lingvodoc.Perspective.fromJS = function (js) {
    return new lingvodoc.Perspective(js.client_id, js.object_id, js.parent_client_id, js.parent_object_id,
        js.translation, js.translation_string, js.status, js.is_template, js.marked_for_deletion);
};
lingvodoc.Perspective.prototype = new lingvodoc.Object();
lingvodoc.Perspective.prototype.constructor = lingvodoc.Perspective;

lingvodoc.User = function(id, login, name, email, intl_name, about, signup_date, organizations) {

    this.id = id;
    this.login = login;
    this.name = name;
    this.email = email;
    this.intl_name = intl_name;
    this.about = about;
    this.signup_date = signup_date;
    this.organizations = organizations;

    this.equals = function(obj) {
        return (this.id == obj.id);
    };
};
lingvodoc.User.fromJS = function (js) {
    return new lingvodoc.User(js.id, js.login, js.name, js.email, js.intl_name, js.about, js.signup_date, js.organizations);
};



function lingvodocAPI($http, $q) {

    var addUrlParameter = function(url, key, value) {
        return url + (url.indexOf('?') >= 0 ? '&' : '?') + encodeURIComponent(key) + '=' + encodeURIComponent(value);
    };

    // merges group fields like Paradigm (-translation, -transcription, -sound, etc) into single cell
    var perspectiveToDictionaryFields = function(perspectiveFields) {
        var fields = [];
        angular.forEach(perspectiveFields, function(field, index) {
            if (typeof field.group == 'string') {

                var createNewGroup = true;
                for (var j = 0; j < fields.length; j++) {
                    if (fields[j].entity_type == field.group && fields[j].isGroup) {
                        fields[j].contains.push(field);
                        createNewGroup = false;
                        break;
                    }
                }

                if (createNewGroup) {
                    fields.push({
                        'entity_type': field.group,
                        'isGroup': true,
                        'contains': [field]
                    });
                }

            } else {
                fields.push(field);
            }
        });
        return fields;
    };

    var getLexicalEntries = function(url, offset, count) {

        var deferred = $q.defer();

        var allLexicalEntriesUrl = url;
        allLexicalEntriesUrl = addUrlParameter(allLexicalEntriesUrl, 'start_from', offset);
        allLexicalEntriesUrl = addUrlParameter(allLexicalEntriesUrl, 'count', count);

        $http.get(allLexicalEntriesUrl).success(function(data, status, headers, config) {
            if (data.lexical_entries && angular.isArray(data.lexical_entries)) {
                deferred.resolve(data.lexical_entries);
            } else {
                deferred.reject('An error occured while fetching lexical entries!');
            }
        }).error(function() {
            deferred.reject('An error occured while fetching lexical entries!');
        });
        return deferred.promise;
    };

    var getLexicalEntriesCount = function(url) {
        var deferred = $q.defer();
        $http.get(url).success(function(data, status, headers, config) {
            var totalEntries = parseInt(data.count);
            if (!isNaN(totalEntries)) {
                deferred.resolve(totalEntries);
            } else {
                deferred.reject('An error occurred while fetching dictionary stats');
            }
        }).error(function(data, status, headers, config) {
            deferred.reject('An error occurred while fetching dictionary stats');
        });

        return deferred.promise;
    };

    var getPerspectiveDictionaryFields = function(url) {
        var deferred = $q.defer();
        $http.get(url).success(function(data, status, headers, config) {
            if (angular.isArray(data.fields)) {
                var fields = perspectiveToDictionaryFields(data.fields);
                deferred.resolve(fields);
            } else {
                deferred.reject('An error occurred while fetching perspective fields');
            }
        }).error(function(data, status, headers, config) {
            deferred.reject('An error occurred while fetching perspective fields');
        });

        return deferred.promise;
    };

    var removeValue = function(entry, field, fieldValue, parent) {

        var deferred = $q.defer();
        var url;
        if (field.level) {
            switch (field.level) {
                case  'leveloneentity':
                    url =
                        '/dictionary/' + encodeURIComponent(dictionaryClientId) + '/' + encodeURIComponent(dictionaryObjectId) + '/perspective/' + encodeURIComponent(perspectiveClientId) + '/' + encodeURIComponent(perspectiveId) + '/lexical_entry/' + encodeURIComponent(entry.client_id) + '/' + encodeURIComponent(entry.object_id) + '/leveloneentity/' + encodeURIComponent(fieldValue.client_id) + '/' + encodeURIComponent(fieldValue.object_id);
                    break;
                case 'leveltwoentity':
                    if (parentClientId && parentObjectId) {
                        url =
                            '/dictionary/' + encodeURIComponent(dictionaryClientId) + '/' + encodeURIComponent(dictionaryObjectId) + '/perspective/' + encodeURIComponent(perspectiveClientId) + '/' + encodeURIComponent(perspectiveId) + '/lexical_entry/' + encodeURIComponent(fieldValue.client_id) + '/' + encodeURIComponent(fieldValue.object_id) + '/leveloneentity/' + encodeURIComponent(parent.client_id) + '/' + encodeURIComponent(parent.object_id) + '/leveltwoentity/' + encodeURIComponent(fieldValue.client_id) + '/' + encodeURIComponent(fieldValue.object_id);
                    } else {
                        deferred.reject('Attempting to delete Level2 entry with no Level1 entry.');
                        return deferred.promise;
                    }
                    break;
                default:
                    deferred.reject('Unknown level.');
                    return deferred.promise;
            }

            $http.delete(url).success(function(data, status, headers, config) {
                deferred.resolve(data);
            }).error(function(data, status, headers, config) {
                deferred.reject('An error  occurred while removing value');
            });

        } else {
            deferred.reject('An error  occurred while removing value');
        }

        return deferred.promise;
    };


    var saveValue = function(dictionaryClientId, dictionaryObjectId, perspectiveClientId, perspectiveObjectId, entry, field, value, parent) {

        var deferred = $q.defer();
        var url;
        if (field.level) {
            switch (field.level) {
                case  'leveloneentity':
                    url =
                        '/dictionary/' + encodeURIComponent(dictionaryClientId) + '/' + encodeURIComponent(dictionaryObjectId) + '/perspective/' + encodeURIComponent(perspectiveClientId) + '/' + encodeURIComponent(perspectiveObjectId) + '/lexical_entry/' + encodeURIComponent(entry.client_id) + '/' + encodeURIComponent(entry.object_id) + '/leveloneentity';
                    break;
                case 'leveltwoentity':
                    if (parent.client_id && parent.object_id) {
                        url =
                            '/dictionary/' + encodeURIComponent(dictionaryClientId) + '/' + encodeURIComponent(dictionaryObjectId) + '/perspective/' + encodeURIComponent(perspectiveClientId) + '/' + encodeURIComponent(perspectiveObjectId) + '/lexical_entry/' + encodeURIComponent(entry.client_id) + '/' + encodeURIComponent(entry.object_id) + '/leveloneentity/' + encodeURIComponent(parent.client_id) + '/' + encodeURIComponent(parent.object_id) + '/leveltwoentity';
                    } else {
                        deferred.reject('Attempting to save Level2 entry with no Level1 entry.');
                        return deferred.promise;
                    }
                    break;
                default:
                    deferred.reject('Unknown level.');
                    return deferred.promise;
            }

            $http.post(url, value).success(function(data, status, headers, config) {
                value.client_id = data.client_id;
                value.object_id = data.object_id;
                deferred.resolve(value);
            }).error(function(data, status, headers, config) {
                deferred.reject('An error  occurred while saving value');
            });

        } else {
            deferred.reject('An error  occurred while saving value');
        }

        return deferred.promise;
    };

    var addNewLexicalEntry = function(url) {
        var deferred = $q.defer();

        $http.post(url).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('An error occurred while creating a new lexical entry');
        });

        return deferred.promise;
    };

    var getConnectedWords = function(clientId, objectId) {
        var deferred = $q.defer();
        var url = '/lexical_entry/' + encodeURIComponent(clientId) + '/' + encodeURIComponent(objectId) + '/connected';
        $http.get(url).success(function(data, status, headers, config) {
            if (angular.isArray(data.words)) {
                deferred.resolve(data.words);
            } else {
                deferred.reject('An error  occurred while fetching connected words');
            }

        }).error(function(data, status, headers, config) {
            deferred.reject('An error  occurred while fetching connected words');
        });

        return deferred.promise;
    };

    var linkEntries = function(e1, e2, entityType) {
        var deferred = $q.defer();
        var linkObject = {
            'entity_type': entityType,
            'connections': [
                {
                    'client_id': e1.client_id,
                    'object_id': e1.object_id
                },
                {
                    'client_id': e2.client_id,
                    'object_id': e2.object_id
                }]
        };

        var url = '/group_entity';
        $http.post(url, linkObject).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('An error  occurred while connecting 2 entries');
        });

        return deferred.promise;
    };

    var search = function(query) {
        var deferred = $q.defer();
        var url = '/basic_search?leveloneentity=' + encodeURIComponent(query);
        $http.get(url).success(function(data, status, headers, config) {
            var urls = [];
            for (var i = 0; i < data.length; i++) {
                var entr = data[i];
                var getEntryUrl = '/dictionary/' + encodeURIComponent(entr.origin_dictionary_client_id) + '/' + encodeURIComponent(entr.origin_dictionary_object_id) + '/perspective/' + encodeURIComponent(entr.origin_perspective_client_id) + '/' + encodeURIComponent(entr.origin_perspective_object_id) + '/lexical_entry/' + encodeURIComponent(entr.client_id) + '/' + encodeURIComponent(entr.object_id);
                urls.push(getEntryUrl);
            }

            var uniqueUrls = urls.filter(function(item, pos) {
                return urls.indexOf(item) == pos;
            });

            var requests = [];
            for (var j = 0; j < uniqueUrls.length; j++) {
                var r = $http.get(uniqueUrls[j]);
                requests.push(r);
            }

            $q.all(requests).then(function(results) {
                var suggestedEntries = [];
                for (var k = 0; k < results.length; k++) {
                    if (results[k].data) {
                        suggestedEntries.push(results[k].data.lexical_entry);
                    }
                }
                deferred.resolve(suggestedEntries);
            });

        }).error(function(data, status, headers, config) {
            deferred.reject('An error  occurred while doing basic search');
        });

        return deferred.promise;
    };

    var approve = function(url, entity, status) {
        var deferred = $q.defer();

        if (status) {
            $http.patch(url, entity).success(function(data, status, headers, config) {
                deferred.resolve(data);
            }).error(function(data, status, headers, config) {
                deferred.reject('An error  occurred while trying to change approval status ');
            });
        } else {

            var config = {
                method: 'DELETE',
                url: url,
                data: entity,
                headers: {'Content-Type': 'application/json;charset=utf-8'}
            };
            $http(config).success(function(data, status, headers, config) {
                deferred.resolve(data);
            }).error(function(data, status, headers, config) {
                deferred.reject('An error  occurred while trying to change approval status ');
            });
        }
        return deferred.promise;
    };

    var approveAll = function(url) {
        var deferred = $q.defer();
        $http.patch(url).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('An error  occurred while trying to change approval status ');
        });

        return deferred.promise;
    };

    var getDictionaryProperties = function(url) {

        var deferred = $q.defer();
        $http.get(url).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('An error  occurred while trying to get dictionary properties');
        });

        return deferred.promise;
    };

    var setDictionaryProperties = function(url, properties) {

        var deferred = $q.defer();
        $http.put(url, properties).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('An error  occurred while trying to get dictionary properties');
        });

        return deferred.promise;
    };

    var getLanguages = function(url) {
        var deferred = $q.defer();
        var flatLanguages = function (languages) {
            var flat = [];
            for (var i = 0; i < languages.length; i++) {
                var language = languages[i];
                flat.push(languages[i]);
                if (language.contains && language.contains.length > 0) {
                    var childLangs = flatLanguages(language.contains);
                    flat = flat.concat(childLangs);
                }
            }
            return flat;
        };

        $http.get(url).success(function (data, status, headers, config) {
            deferred.resolve(flatLanguages(data.languages));
        }).error(function (data, status, headers, config) {
            deferred.reject('An error  occurred while trying to get languages');
        });

        return deferred.promise;
    };

    var setDictionaryStatus = function(dictionary, status) {
        var deferred = $q.defer();

        var url = '/dictionary/' + dictionary.client_id + '/' + dictionary.object_id + '/state';
        $http.put(url, {'status': status }).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('An error  occurred while trying to set dictionary status');
        });

        return deferred.promise;
    };

    var setPerspectiveStatus = function(dictionary, perspective, status) {
        var deferred = $q.defer();

        var url = '/dictionary/' + dictionary.client_id + '/' + dictionary.object_id +
            '/perspective/' + perspective.client_id + '/' + perspective.object_id + '/state';

        $http.put(url, {'status': status }).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('An error  occurred while trying to set perspective status');
        });

        return deferred.promise;
    };

    var setPerspectiveProperties = function(dictionary, perspective) {
        var deferred = $q.defer();
        var url = '/dictionary/' + dictionary.client_id + '/' + dictionary.object_id +
            '/perspective/' + perspective.client_id + '/' + perspective.object_id;
        $http.put(url, perspective).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to update perspective properties');
        });

        return deferred.promise;
    };

    var getPerspectiveFieldsNew = function(perspective) {
        var deferred = $q.defer();
        var url = '/dictionary/' + perspective.parent_client_id + '/' + perspective.parent_object_id + '/perspective/' + perspective.client_id + '/' + perspective.object_id + '/fields';
        $http.get(url).success(function(data, status, headers, config) {
            deferred.resolve(data.fields);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to load perspective fields');
        });

        return deferred.promise;
    };

    var getPerspectiveFields = function(url) {

        var deferred = $q.defer();
        $http.get(url).success(function(data, status, headers, config) {
            deferred.resolve(data.fields);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to load perspective fields');
        });

        return deferred.promise;
    };

    var setPerspectiveFields = function(url, fields) {

        var deferred = $q.defer();
        $http.post(url, fields).success(function(data, status, headers, config) {
            deferred.resolve(data.fields);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to save perspective fields');
        });

        return deferred.promise;
    };

    var getUserInfo = function(userId, clientId) {
        var deferred = $q.defer();
        var url = '/user' + '?client_id= ' + encodeURIComponent(clientId) + '&user_id= ' + encodeURIComponent(userId);

        $http.get(url).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to get user info');
        });

        return deferred.promise;
    };

    var setUserInfo = function(userId, clientId, userInfo) {

        var deferred = $q.defer();
        var url = '/user' + '?client_id= ' + encodeURIComponent(clientId) + '&user_id= ' + encodeURIComponent(userId);

        $http.post(url, userInfo).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to set user info');
        });

        return deferred.promise;
    };

    var getOrganizations = function() {
        var deferred = $q.defer();

        $http.get('/organization_list').success(function(data, status, headers, config) {
            deferred.resolve(data.organizations);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to fetch list of organizations');
        });

        return deferred.promise;
    };

    var createOrganization = function(org) {
        var deferred = $q.defer();

        $http.post('/organization', org).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to create organization');
        });

        return deferred.promise;
    };

    var getOrganization = function(orgId) {
        var deferred = $q.defer();
        var url = '/organization/' + encodeURIComponent(orgId) ;

        $http.get(url).success(function(data, status, headers, config) {

            var requests = [];
            var users = [];
            var promises = data.users.map(function(userId) {
                return $http.get('/user' + '?user_id= ' + encodeURIComponent(userId));
            });

            $q.all(promises).then(function(results) {

                angular.forEach(results, function(result) {
                    users.push(result.data);
                });
                data.users = users;
                deferred.resolve(data);
            });

        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to get information about organization');
        });

        return deferred.promise;
    };

    var editOrganization = function(org) {
        var deferred = $q.defer();

        var url = '/organization/' + encodeURIComponent(org.organization_id) ;

        $http.put(url, org).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to change information about organization');
        });

        return deferred.promise;
    };

    var searchUsers = function(query) {
        var deferred = $q.defer();
        $http.get('/users?search=' + encodeURIComponent(query)).success(function(data, status, headers, config) {
            deferred.resolve(data.users);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to search for users');
        });

        return deferred.promise;
    };

    var getDictionaries = function(query) {

        var deferred = $q.defer();
        var dictionaries = [];
        $http.post('/dictionaries', query).success(function (data, status, headers, config) {

            for (var i = 0; i < data.dictionaries.length; i++) {
                var dictionary = data.dictionaries[i];
                dictionaries.push(lingvodoc.Dictionary.fromJS(dictionary));
            }

            deferred.resolve(dictionaries);
        }).error(function (data, status, headers, config) {
            deferred.reject('Failed to fetch dictionaries list');
        });

        return deferred.promise;
    };

    var getPerspectiveById = function(client_id, object_id) {
        var deferred = $q.defer();
        var url = 'perspective/' + encodeURIComponent(client_id) + '/' + encodeURIComponent(object_id);
        $http.get(url).success(function(data, status, headers, config) {
            deferred.resolve(lingvodoc.Perspective.fromJS(data));
        }).error(function (data, status, headers, config) {
            deferred.reject('Failed to fetch perspective');

        });
        return deferred.promise;
    };

    var createPerspective = function(dictionary, perspective, fields) {
        var deferred = $q.defer();
        var createPerspectiveUrl = '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/' + 'perspective';
        $http.post(createPerspectiveUrl, perspective).success(function(data, status, headers, config) {
            if (data.object_id && data.client_id) {
                var perspective_client_id = data.client_id;
                var perspective_object_id = data.object_id;
                var setFieldsUrl = '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(data.client_id) + '/' + encodeURIComponent(data.object_id) + '/fields';
                $http.post(setFieldsUrl, fields).success(function(data, status, headers, config) {
                    getPerspectiveById(perspective_client_id, perspective_object_id).then(function(perspective) {
                        deferred.resolve(perspective);
                    }, function(reason) {
                        deferred.reject(reason);
                    });

                }).error(function(data, status, headers, config) {
                    deferred.reject('Failed to create perspective fields');
                });

            } else {
                deferred.reject('Failed to create perspective');
            }
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to create perspective');
        });
        return deferred.promise;
    };

    var getAllPerspectives = function() {
        var deferred = $q.defer();
        $http.get('/perspectives').success(function(data, status, headers, config) {
            deferred.resolve(data.perspectives.map(function(p) {
                return lingvodoc.Perspective.fromJS(p);
            }));
        }).error(function (data, status, headers, config) {
            deferred.reject('Failed to fetch perspectives list');

        });
        return deferred.promise;
    };

    var getDictionaryPerspectives = function(dictionary) {
        var deferred = $q.defer();
        var perspectives = [];
        var getPerspectivesUrl = '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspectives';
        $http.get(getPerspectivesUrl).success(function(data, status, headers, config) {
            angular.forEach(data.perspectives, function(jspers) {
                perspectives.push(lingvodoc.Perspective.fromJS(jspers));
            });

            deferred.resolve(perspectives);
        }).error(function (data, status, headers, config) {
            deferred.reject('Failed to fetch perspectives list');

        });
        return deferred.promise;
    };

    var getDictionariesWithPerspectives = function(query) {
        var deferred = $q.defer();

        getDictionaries(query).then(function(dictionaries) {

            var r = dictionaries.map(function(d) {
                return getDictionaryPerspectives(d);
            });

            $q.all(r).then(function(results) {
                angular.forEach(dictionaries, function(dictionary, index) {
                    dictionary.perspectives = results[index];
                });
                deferred.resolve(dictionaries);
            });

        }, function() {

        });


        return deferred.promise;
    };


    var mergeDictionaries = function(tranlation, translation_string, d1, d2) {

        var deferred = $q.defer();
        var req = {
            'translation': tranlation,
            'translation_string': translation_string,
            'language_client_id': d1.parent_client_id,
            'language_object_id': d1.parent_object_id,
            'dictionaries': [
                {'client_id': d1.client_id, 'object_id': d1.object_id},
                {'client_id': d2.client_id, 'object_id': d2.object_id}
            ]
        };
        $http.post('/merge/dictionaries', req).success(function(data, status, headers, config) {
            console.log(data);
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to merge dictionaries');
        });
        return deferred.promise;
    };

    var mergePerspectives = function(req) {
        var deferred = $q.defer();

        $http.post('/merge/perspectives', req).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to merge perspectives');
        });
        return deferred.promise;
    };


    var getSuggestionLexicalEntry = function(entry) {
        var deferred = $q.defer();
        getLexicalEntry(entry.suggestion[0].lexical_entry_client_id, entry.suggestion[0].lexical_entry_object_id).then(function (e1) {
            getLexicalEntry(entry.suggestion[1].lexical_entry_client_id, entry.suggestion[1].lexical_entry_object_id).then(function (e2) {
                deferred.resolve({ 'confidence': entry.confidence, 'suggestion': [e1, e2] });
            }, function (reason) {
                deferred.reject('Failed to fetch lexical entry: ' + reason);
            });

        }, function (reason) {
            deferred.reject('Failed to fetch lexical entry: ' + reason);
        });

        return deferred.promise;
    };


    var mergeSuggestions = function(perspective) {
        var deferred = $q.defer();

        var body = {
            'entity_type_primary': 'Word',
            'entity_type_secondary': 'Transcription',
            'threshold': 0.6,
            'levenstein' : 3,
            'client_id': perspective.client_id,
            'object_id': perspective.object_id
        };

        $http.post('/merge/suggestions', body).success(function(data, status, headers, config) {

            if (angular.isArray(data)) {
                var r = data.map(function (e) {
                    return getSuggestionLexicalEntry(e);
                });
                $q.all(r).then(function (results) {
                    deferred.resolve(results);
                });
            } else {
                deferred.resolve([]);
            }
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to fetch merge suggestions');
        });
        return deferred.promise;
    };

    var getLexicalEntry = function(clientId, objectId) {
        var deferred = $q.defer();
        $http.get('/lexical_entry/' + encodeURIComponent(clientId) + '/' + encodeURIComponent(objectId)).success(function(data, status, headers, config) {
            deferred.resolve(data.lexical_entry);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to fetch lexical entry');
        });
        return deferred.promise;
    };

    var moveLexicalEntry = function(clientId, objectId, toClientId, toObjectId) {
        var deferred = $q.defer();
        var req = {'client_id': toClientId, 'object_id': toObjectId};
        $http.patch('/lexical_entry/' + encodeURIComponent(clientId) + '/' + encodeURIComponent(objectId) + '/move', req).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to move lexical entry');
        });
        return deferred.promise;
    };

    var getDictionariesByLanguage = function(language) {

        var deferred = $q.defer();

        var req = {'languages': [
            {'client_id': language.client_id, 'object_id': language.object_id}
        ]};

        $http.post('/dictionaries', req).success(function(data, status, headers, config) {
            var dictionaries = [];
            if (angular.isArray(data.dictionaries)) {
                angular.forEach(data.dictionaries, function(jsdict) {
                    var dictionary = lingvodoc.Dictionary.fromJS(jsdict);
                    if (language.client_id == dictionary.parent_client_id && language.object_id == dictionary.parent_object_id) {
                        dictionaries.push(dictionary);
                    }
                });
            }
            deferred.resolve(dictionaries);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to move lexical entry');
        });
        return deferred.promise;
    };


    var getLanguagesFull = function() {
        var deferred = $q.defer();

        var flatLanguages = function (languages) {
            var flat = [];
            for (var i = 0; i < languages.length; i++) {
                var language = languages[i];
                flat.push(language);
                if (language.languages.length > 0) {
                    var childLangs = flatLanguages(language.languages);
                    flat = flat.concat(childLangs);
                }
            }
            return flat;
        };

        var setDictionaries = function(language, languages, dictionaries) {
            for (var i = 0; i < languages.length; ++i) {
                var lang = languages[i];
                if (language.equals(lang)) {
                    language.dictionaries = dictionaries;
                    return true;
                } else {
                    if (setDictionaries(language, lang.languages, dictionaries)) {
                        return true;
                    }
                }
            }
            return false;
        };


        var parseResponse = function(langs) {
            var responseLangs = [];
            angular.forEach(langs, function(lang) {
                var responseLang = lingvodoc.Language.fromJS(lang);
                if (angular.isArray(lang.contains)) {
                    responseLang.languages = parseResponse(lang.contains);
                }
                responseLangs.push(responseLang);
            });
            return responseLangs;
        };

        $http.get('/languages').success(function (data, status, headers, config) {
            var languages = [];
            if (angular.isArray(data.languages)) {
                languages = parseResponse(data.languages);
            }

            var flat = flatLanguages(languages);
            var reqs = flat.map(function(l) {
                return getDictionariesByLanguage(l);
            });

            $q.all(reqs).then(function(allLangsDictionaries) {
                angular.forEach(allLangsDictionaries, function(dictionaries, index) {
                    setDictionaries(flat[index], languages, dictionaries);
                });
                deferred.resolve(languages);
            }, function(reason) {
                deferred.reject(reason);
            });

        }).error(function (data, status, headers, config) {
            deferred.reject('An error occurred while trying to get languages');
        });

        return deferred.promise;
    };

    var getPublishedDictionaries = function() {

        var deferred = $q.defer();

        var req = {'group_by_lang': true, 'group_by_org': false};
        $http.post('/published_dictionaries', req).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to move lexical entry');
        });
        return deferred.promise;
    };


    var getUser = function(id) {
        var deferred = $q.defer();
        $http.get('/user' + '?user_id=' + encodeURIComponent(id)).success(function(data, status, headers, config) {
            deferred.resolve(lingvodoc.User.fromJS(data));
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to move lexical entry');
        });
        return deferred.promise;
    };

    var getRoles = function(url) {
        var deferred = $q.defer();
        $http.get(url).success(function(data, status, headers, config) {

            var userIds = [];
            angular.forEach(data.roles_users, function(role) {
                angular.forEach(role, function(userId) {
                    if (userIds.indexOf(userId) < 0) {
                        userIds.push(userId);
                    }
                });
            });

            var reqs = userIds.map(function(id) {
                return getUser(id);
            });

            $q.all(reqs).then(function(users) {
                var resultRoles = {};
                angular.forEach(data.roles_users, function(roleUsers, roleName) {
                    resultRoles[roleName] = roleUsers.map(function(userId) {
                        return users.filter(function(u) {
                            return u.id == userId;
                        })[0];
                    });
                });
                deferred.resolve(resultRoles);
            }, function(reason) {
                deferred.reject('An error occurred while trying to get dictionary roles');
            });

        }).error(function(data, status, headers, config) {
            deferred.reject('An error occurred while trying to get dictionary roles');
        });
        return deferred.promise;
    };

    var getDictionaryRoles = function(dictionary) {
        var url = '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/roles';
        return getRoles(url);
    };

    var addDictionaryRoles = function(dictionary, roles) {
        var deferred = $q.defer();
        var url = '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/roles';

        $http.post(url, roles).success(function(data, status, headers, config) {
            deferred.resolve();
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to add roles');
        });
        return deferred.promise;
    };

    var deleteDictionaryRoles = function(dictionary, roles) {
        var deferred = $q.defer();
        var url = '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/roles';

        var config = {
            method: 'DELETE',
            url: url,
            data: roles,
            headers: {'Content-Type': 'application/json;charset=utf-8'}
        };

        $http(config).success(function(data, status, headers, config) {
            deferred.resolve();
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to delete roles');
        });
        return deferred.promise;
    };

    var getPerspectiveRoles = function(dictionary, perspective, roles) {
        var url = '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(perspective.client_id) + '/' + encodeURIComponent(perspective.object_id) + '/roles';
        return getRoles(url);
    };


    var addPerspectiveRoles = function(dictionary, perspective, roles) {
        var deferred = $q.defer();
        var url = '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(perspective.client_id) + '/' + encodeURIComponent(perspective.object_id) + '/roles';
        $http.post(url, roles).success(function(data, status, headers, config) {
            deferred.resolve();
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to update roles');
        });
        return deferred.promise;
    };

    var deletePerspectiveRoles = function(dictionary, perspective, roles) {
        var deferred = $q.defer();
        var url = '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(perspective.client_id) + '/' + encodeURIComponent(perspective.object_id) + '/roles';
        var config = {
            method: 'DELETE',
            url: url,
            data: roles,
            headers: {'Content-Type': 'application/json;charset=utf-8'}
        };

        $http(config).success(function(data, status, headers, config) {
            deferred.resolve();
        }).error(function(data, status, headers, config) {
            deferred.reject('Failed to update roles');
        });
        return deferred.promise;
    };




    // Return public API.
    return ({
        'getLexicalEntries': getLexicalEntries,
        'getLexicalEntriesCount': getLexicalEntriesCount,
        'getPerspectiveDictionaryFields': getPerspectiveDictionaryFields,
        'addNewLexicalEntry': addNewLexicalEntry,
        'saveValue': saveValue,
        'removeValue': removeValue,
        'getConnectedWords': getConnectedWords,
        'linkEntries': linkEntries,
        'search': search,
        'approve': approve,
        'approveAll': approveAll,
        'getDictionaryProperties': getDictionaryProperties,
        'setDictionaryProperties': setDictionaryProperties,
        'getLanguages': getLanguages,
        'setDictionaryStatus': setDictionaryStatus,
        'setPerspectiveStatus': setPerspectiveStatus,
        'setPerspectiveProperties': setPerspectiveProperties,
        'getPerspectiveFields': getPerspectiveFields,
        'setPerspectiveFields': setPerspectiveFields,
        'getPerspectiveFieldsNew': getPerspectiveFieldsNew,
        'getUserInfo': getUserInfo,
        'setUserInfo': setUserInfo,
        'getOrganizations': getOrganizations,
        'createOrganization': createOrganization,
        'getOrganization': getOrganization,
        'editOrganization': editOrganization,
        'searchUsers': searchUsers,
        'getDictionaries': getDictionaries,
        'getAllPerspectives': getAllPerspectives,
        'getPerspectiveById': getPerspectiveById,
        'createPerspective': createPerspective,
        'getDictionaryPerspectives': getDictionaryPerspectives,
        'getDictionariesWithPerspectives': getDictionariesWithPerspectives,
        'mergeDictionaries': mergeDictionaries,
        'mergePerspectives': mergePerspectives,
        'mergeSuggestions': mergeSuggestions,
        'getLexicalEntry': getLexicalEntry,
        'moveLexicalEntry': moveLexicalEntry,
        'getLanguagesFull': getLanguagesFull,
        'getPublishedDictionaries': getPublishedDictionaries,
        'getDictionaryRoles': getDictionaryRoles,
        'addDictionaryRoles': addDictionaryRoles,
        'deleteDictionaryRoles': deleteDictionaryRoles,
        'getPerspectiveRoles': getPerspectiveRoles,
        'addPerspectiveRoles': addPerspectiveRoles,
        'deletePerspectiveRoles': deletePerspectiveRoles
    });
};
