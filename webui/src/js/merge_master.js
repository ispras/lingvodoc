var app = angular.module('MergeMasterModule', ['ui.router', 'ui.bootstrap']);

app.config(function ($stateProvider, $urlRouterProvider) {

    $stateProvider
        .state('merge', {
            url: '/merge',
            templateUrl: 'mergeMaster.html',
            controller: 'MergeMasterController'
        })
        .state('merge.intro', {
            url: '/intro',
            templateUrl: 'mergeMasterIntro.html'
        })
        .state('merge.mode', {
            url: '/mode',
            templateUrl: 'mergeMasterMode.html'
        }).state('merge.selectDictionaries', {
            url: '/source-dictionaries',
            templateUrl: 'mergeMasterSelectDictionaries.html'
        }).state('merge.selectPerspectives', {
            url: '/source-perspectives',
            templateUrl: 'mergeMasterSourcePerspectives.html'
        }).state('merge.perspectives', {
            url: '/merge-perspectives',
            templateUrl: 'mergePerspectives.html'
        }).state('merge.entries', {
            url: '/entries',
            templateUrl: 'mergeEntries.html'
        }).state('merge.perspectiveFinished', {
            url: '/entries/finished',
            templateUrl: 'mergeEntriesFinished.html'
        });



    $urlRouterProvider.otherwise('/merge/intro');
});

app.service('dictionaryService', lingvodocAPI);

app.factory('responseHandler', ['$timeout', '$modal', responseHandler]);

app.directive('translatable', ['dictionaryService', getTranslation]);


app.controller('MergeMasterController', ['$scope', '$http', '$modal', '$interval', '$state', '$log', 'dictionaryService', 'responseHandler', function ($scope, $http, $modal, $interval, $state, $log, dictionaryService, responseHandler) {

    var clientId = $('#clientId').data('lingvodoc');
    var userId = $('#userId').data('lingvodoc');

    $scope.master = {
        'mergeMode': 'dictionaries',
        'dictionaries':  [],

        'languagesTree': [],
        'suggestedDictionaries': [],
        'selectedSourceDictionaryId1': 'None',
        'selectedSourceDictionaryId2': 'None',
        'selectedSourceDictionary1': {},
        'selectedSourceDictionary2': {},
        'mergedDictionaryName': '',

        'selectedSourceDictionaryId': 'None',
        'selectedSourceDictionary': {},
        'perspectiveId1': '',
        'perspectiveId2': '',
        'perspective1': {},
        'perspective2': {},
        'perspectiveName': '',
        'perspectivePreview': [],
        'dictionaryTable': [],
        'mergedPerspectiveFields': [],
        'suggestions': [],
        'suggestedLexicalEntries': []
    };

    $scope.master.controls = {
        'startMergeDictionaries': true,
        'startMergePerspectives': true,
        'commitPerspective': true
    };


    var wrapFields = function(fields) {
        angular.forEach(fields, function(field) {
            field._statusEnabled = (field.status == 'enabled');
            field._newEntityType = field.entity_type;
        });
        return fields;
    };

    var unwrapFields = function(fields) {
        var exportFields = cloneObject(fields);
        angular.forEach(exportFields, function(field) {
            if(field._statusEnabled) {
                field.status = 'enabled';
            } else {
                field.status = 'disabled';
            }
            delete field._statusEnabled;


            if (field._newEntityType != field.entity_type) {
                field.new_type_name = field._newEntityType;
            }
            delete field._newEntityType;
        });

        return exportFields;
    };

    var findMatchedFields = function() {
        var matches = [];
        angular.forEach($scope.master.fields1, function(field1) {
            angular.forEach($scope.master.fields2, function(field2) {
                if (field1._statusEnabled && field2._statusEnabled) {
                    if (field1._newEntityType == field2._newEntityType) {
                        matches.push({
                            'first': field1,
                            'second': field2
                        });
                    }
                }
            });
        });
        return matches;
    };

    var createPreview = function(fields1, fields2) {
        $scope.master.perspectivePreview = [];

        angular.forEach(fields1, function(field) {
            if (field._statusEnabled) {
                $scope.master.perspectivePreview.push(field);
            }

        });
        angular.forEach(fields2, function(field) {
            if (field._statusEnabled) {
                $scope.master.perspectivePreview.push(field);
            }
        });
    };


    var removeFieldFromPreview = function(field) {

        var index = -1;
        for (var i = 0; i < $scope.master.perspectivePreview.length; i++) {
            if ($scope.master.perspectivePreview[i]._newEntityType == field._newEntityType) {
                index = i;
            }
        }
        if (index >= 0) {
            $scope.master.perspectivePreview.splice(index, 1);
        }
    };

    var updatePreview = function() {

        var matches = findMatchedFields();
        $scope.master.perspectivePreview = [];

        angular.forEach($scope.master.fields1, function(field) {
            if (field._statusEnabled) {
                $scope.master.perspectivePreview.push(field);
            }
        });
        angular.forEach($scope.master.fields2, function(field) {
            if (field._statusEnabled) {
                $scope.master.perspectivePreview.push(field);
            }
        });

        // remove duplicates
        angular.forEach(matches, function(m) {
           removeFieldFromPreview(m.second);
        });
    };


    $scope.selectSource = function() {
        if ($scope.master.mergeMode == 'dictionaries') {
            $state.go('merge.selectDictionaries');
        }

        if ($scope.master.mergeMode == 'perspectives') {
            $state.go('merge.selectPerspectives');
        }
    };

    $scope.startMergeDictionaries = function() {

        if (!$scope.master.mergedDictionaryName) {
            alert('Please, specify new dictionary name!');
            return;
        }

        $scope.master.controls.startMergeDictionaries = false;

        if ($scope.master.selectedSourceDictionary1 instanceof lingvodoc.Dictionary &&
            $scope.master.selectedSourceDictionary2 instanceof lingvodoc.Dictionary) {

            dictionaryService.mergeDictionaries($scope.master.mergedDictionaryName,
                $scope.master.mergedDictionaryName,
                $scope.master.selectedSourceDictionary1,
                $scope.master.selectedSourceDictionary2
            ).then(function(result) {
                    $scope.master.controls.startMergeDictionaries = true;
                    $state.go('merge.perspectiveFinished');
                }, function(reason) {
                    $scope.master.controls.startMergeDictionaries = true;
                    responseHandler.error(reason);
                });

        }
    };

    $scope.startMergePerspectives = function() {
        if ($scope.master.perspective1 instanceof lingvodoc.Perspective &&
            $scope.master.perspective2 instanceof lingvodoc.Perspective) {

            if ($scope.master.perspective1.equals($scope.master.perspective2)) {
                alert('Please, select 2 different perspectives');
                return;
            }

            $scope.master.controls.startMergePerspectives = false;

            var p1 = $scope.master.perspective1;
            var url1 = '/dictionary/' + p1.parent_client_id + '/' + p1.parent_object_id + '/perspective/' + p1.client_id + '/' + p1.object_id + '/fields';
            var p2 = $scope.master.perspective2;
            var url2 = '/dictionary/' + p2.parent_client_id + '/' + p2.parent_object_id + '/perspective/' + p2.client_id + '/' + p2.object_id + '/fields';

            dictionaryService.getPerspectiveFields(url1).then(function(fields1) {

                dictionaryService.getPerspectiveFields(url2).then(function(fields2) {

                    $scope.master.controls.startMergePerspectives = true;

                    $scope.master.fields1 = wrapFields(fields1);
                    $scope.master.fields2 = wrapFields(fields2);

                    createPreview($scope.master.fields1, $scope.master.fields2);

                    $state.go('merge.perspectives');

                }, function(reason) {
                    responseHandler.error(reason);
                    $scope.master.controls.startMergePerspectives = true;
                });

            }, function(reason) {
                responseHandler.error(reason);
                $scope.master.controls.startMergePerspectives = true;
            });


        } else {
            $log.error('');
        }
    };

    $scope.commitPerspective = function() {

        if (!$scope.master.perspectiveName) {
            alert('Please, specify perspective name.');
            return;
        }

        $scope.master.controls.commitPerspective = false;

        var updateFields1 = unwrapFields($scope.master.fields1);
        var updateFields2 = unwrapFields($scope.master.fields2);

        var req = {
            'dictionary_client_id' : $scope.master.selectedSourceDictionary.client_id,
            'dictionary_object_id': $scope.master.selectedSourceDictionary.object_id,
            'translation_string': $scope.master.perspectiveName,
            'translation': $scope.master.perspectiveName,
            'perspectives':[
                {
                    'client_id': $scope.master.perspective1.client_id,
                    'object_id': $scope.master.perspective1.object_id,
                    'fields' : updateFields1
                },
                {
                    'client_id': $scope.master.perspective2.client_id,
                    'object_id': $scope.master.perspective2.object_id,
                    'fields' : updateFields2
                }
            ]
        };

        $scope.master.controls.commitPerspective = false;

        dictionaryService.mergePerspectives(req).then(function(obj) {
            $scope.master.mergedPerspectiveObject = obj;

            var url = '/dictionary/' + $scope.master.selectedSourceDictionary.client_id + '/' + $scope.master.selectedSourceDictionary.object_id + '/perspective/' + obj.client_id + '/' + obj.object_id + '/fields';
            dictionaryService.getPerspectiveDictionaryFields(url).then(function(fields) {
                $scope.master.mergedPerspectiveFields = fields;

                dictionaryService.mergeSuggestions(obj).then(function(suggestions) {

                    $scope.master.controls.commitPerspective = true;

                    if (suggestions.length > 0) {
                        $scope.master.suggestions = suggestions;
                        $scope.master.suggestedLexicalEntries = $scope.master.suggestions[0].suggestion;
                        $scope.master.suggestions.splice(0, 1);
                        $state.go('merge.entries');
                    } else {
                        $state.go('merge.perspectiveFinished');
                    }

                }, function(reason) {
                    $scope.master.controls.commitPerspective = true;
                    responseHandler.error(reason);
                });

            }, function(reason) {
                $scope.master.controls.commitPerspective = true;
                responseHandler.error(reason);
            });

        }, function(reason) {
            $scope.master.controls.commitPerspective = true;
            responseHandler.error(reason);
        });
    };


    var nextSuggestedEntries = function() {
        if ($scope.master.suggestions.length > 0) {
            $scope.master.suggestedLexicalEntries = $scope.master.suggestions[0].suggestion;
            $scope.master.suggestions.splice(0, 1);
            $state.go('merge.entries');
        } else {
            $state.go('merge.perspectiveFinished');
        }
    };

    $scope.approveSuggestion = function () {

        var entry1 = $scope.master.suggestedLexicalEntries[0];
        var entry2 = $scope.master.suggestedLexicalEntries[1];

        dictionaryService.moveLexicalEntry(entry1.client_id, entry1.object_id, entry2.client_id, entry2.object_id)
            .then(function (r) {
                nextSuggestedEntries();
            }, function (reason) {
                responseHandler.error(reason);
            });
    };

    $scope.skipSuggestion = function() {
        nextSuggestedEntries();
    };

    dictionaryService.getDictionariesWithPerspectives({'user_created': [userId]}).then(function(dictionaries) {
        $scope.master.dictionaries = dictionaries;
    }, function(reason) {
        responseHandler.error(reason);
    });

    dictionaryService.getLanguagesFull().then(function(langs) {
        $scope.master.languagesTree = langs;
    }, function(reason) {
        responseHandler.error(reason);
    });

    $scope.$watch('master.selectedSourceDictionaryId', function (id) {

        $scope.master.selectedSourceDictionary = {};
        for (var i = 0; i < $scope.master.dictionaries.length; ++i) {
            if ($scope.master.dictionaries[i].getId() == id) {
                $scope.master.selectedSourceDictionary = $scope.master.dictionaries[i];
                break;
            }
        }
    });


    $scope.$watch('master.selectedSourceDictionaryId1', function (id) {

        $scope.master.selectedSourceDictionary1 = {};
        for (var i = 0; i < $scope.master.dictionaries.length; ++i) {
            if ($scope.master.dictionaries[i].getId() == id) {
                $scope.master.selectedSourceDictionary1 = $scope.master.dictionaries[i];
                break;
            }
        }
    });

    var findLanguage = function(dictionary, languages) {

        for (var i = 0; i < languages.length; ++i) {
            var lang = languages[i];
            for (var j = 0; j < lang.dictionaries.length; ++j) {
                var dict = lang.dictionaries[j];
                if (dictionary.equals(dict)) {
                    return lang;
                }
            }

            var language = findLanguage(dictionary, lang.languages);
            if (language instanceof lingvodoc.Language) {
                return language;
            }
        }

        return null;
    };


    $scope.$watch('master.selectedSourceDictionary1', function(dict) {

        var language = findLanguage(dict, $scope.master.languagesTree);

        if (language) {
            $scope.master.suggestedDictionaries = language.dictionaries;
        }
    }, true);


    $scope.$watch('master.selectedSourceDictionaryId2', function (id) {

        $scope.master.selectedSourceDictionary2 = {};
        for (var i = 0; i < $scope.master.suggestedDictionaries.length; ++i) {
            if ($scope.master.suggestedDictionaries[i].getId() == id) {
                $scope.master.selectedSourceDictionary2 = $scope.master.suggestedDictionaries[i];
                break;
            }
        }
    });


    $scope.$watch('master.perspectiveId1', function (id) {
        if (!$scope.master.selectedSourceDictionary.perspectives) {
            return;
        }
        $scope.master.perspective1 = {};
        for (var i = 0; i < $scope.master.selectedSourceDictionary.perspectives.length; ++i) {
            if ($scope.master.selectedSourceDictionary.perspectives[i].getId() == id) {
                $scope.master.perspective1 = $scope.master.selectedSourceDictionary.perspectives[i];
                break;
            }
        }
    });

    $scope.$watch('master.perspectiveId2', function (id) {
        if (!$scope.master.selectedSourceDictionary.perspectives) {
            return;
        }
        $scope.master.perspective2 = {};
        for (var i = 0; i < $scope.master.selectedSourceDictionary.perspectives.length; ++i) {
            if ($scope.master.selectedSourceDictionary.perspectives[i].getId() == id) {
                $scope.master.perspective2 = $scope.master.selectedSourceDictionary.perspectives[i];
                break;
            }
        }
    });

    $scope.$watch('master.fields1', function(fields) {
        updatePreview();
    }, true);

    $scope.$watch('master.fields2', function(fields) {
        updatePreview();
    }, true);

    $scope.$watch('master.suggestedLexicalEntries', function(updatedEntries) {

        var getFieldValues = function(entry, field) {

            var value;
            var values = [];
            if (entry && entry.contains) {

                if (field.isGroup) {

                    for (var fieldIndex = 0; fieldIndex < field.contains.length; fieldIndex++) {
                        var subField = field.contains[fieldIndex];

                        for (var valueIndex = 0; valueIndex < entry.contains.length; valueIndex++) {
                            value = entry.contains[valueIndex];
                            if (value.entity_type == subField.entity_type) {
                                values.push(value);
                            }
                        }
                    }
                } else {
                    for (var i = 0; i < entry.contains.length; i++) {
                        value = entry.contains[i];
                        if (value.entity_type == field.entity_type) {
                            values.push(value);
                        }
                    }
                }
            }
            return values;
        };

        var mapFieldValues = function(allEntries, allFields) {
            var result = [];
            for (var i = 0; i < allEntries.length; i++) {
                var entryRow = [];
                for (var j = 0; j < allFields.length; j++) {
                    entryRow.push(getFieldValues(allEntries[i], allFields[j]));
                }
                result.push(entryRow);
            }
            return result;
        };

        $scope.master.dictionaryTable = mapFieldValues(updatedEntries, $scope.master.mergedPerspectiveFields);

    }, true);

}]);