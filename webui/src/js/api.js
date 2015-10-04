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

    var getPerspectiveFields = function(url) {
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
            deferred.reject('An error  occurred while connecting 2 entries')
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
                deferred.reject('An error  occurred while trying to change approval status ')
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
                deferred.reject('An error  occurred while trying to change approval status ')
            });
        }
        return deferred.promise;
    };

    var approveAll = function(url) {
        var deferred = $q.defer();
        $http.patch(url).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('An error  occurred while trying to change approval status ')
        });

        return deferred.promise;
    };

    var getDictionaryProperties = function(url) {

        var deferred = $q.defer();
        $http.get(url).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('An error  occurred while trying to get dictionary properties')
        });

        return deferred.promise;
    };

    var setDictionaryProperties = function(url, properties) {

        var deferred = $q.defer();
        $http.put(url, properties).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('An error  occurred while trying to get dictionary properties')
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
            deferred.reject('An error  occurred while trying to get languages')
        });

        return deferred.promise;
    };

    var setDictionaryStatus = function(url, status) {
        var deferred = $q.defer();
        $http.put(url, {'status': status }).success(function(data, status, headers, config) {
            deferred.resolve(data);
        }).error(function(data, status, headers, config) {
            deferred.reject('An error  occurred while trying to set dictionary status')
        });

        return deferred.promise;
    };



    // Return public API.
    return ({
        'getLexicalEntries': getLexicalEntries,
        'getLexicalEntriesCount': getLexicalEntriesCount,
        'getPerspectiveFields': getPerspectiveFields,
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
        'setDictionaryStatus': setDictionaryStatus
    });
};
