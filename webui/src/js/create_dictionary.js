var app = angular.module('CreateDictionaryModule', ['ui.router', 'ngAnimate', 'ui.bootstrap', 'autocomplete']);

app.service('dictionaryService', lingvodocAPI);

app.config(function ($stateProvider, $urlRouterProvider) {

    $stateProvider

        .state('create', {
            url: '/create',
            templateUrl: 'createDictionary.html',
            controller: 'CreateDictionaryController'
        })

        .state('create.step1', {
            url: '/step1',
            templateUrl: 'createDictionaryStep1.html'
        })

        .state('create.step2', {
            url: '/step2',
            templateUrl: 'createDictionaryStep2.html'
        })

        .state('create.step3', {
            url: '/step3',
            templateUrl: 'createDictionaryStep3.html'
        });

    $urlRouterProvider.otherwise('/create/step1');
});

app.factory('responseHandler', ['$timeout', '$modal', responseHandler]);

app.controller('CreateDictionaryController', ['$scope', '$http', '$modal', '$interval', '$state', '$location', '$log', 'dictionaryService', 'responseHandler', function ($scope, $http, $modal, $interval, $state, $location, $log, dictionaryService, responseHandler) {

    var clientId = $('#clientId').data('lingvodoc');
    var userId = $('#userId').data('lingvodoc');
    var languagesUrl = $('#languagesUrl').data('lingvodoc');
    var createLanguageUrl = $('#createLanguageUrl').data('lingvodoc');
    var createDictionaryUrl = $('#createDictionaryUrl').data('lingvodoc');
    var allPerspectivesUrl = $('#allPerspectivesUrl').data('lingvodoc');
    var perspectiveFieldsUrl = '/dictionary';
    var listBlobsUrl = $('#listBlobsUrl').data('lingvodoc');

    $scope.wizard = {
        'mode': 'create',
        'importedDictionaryId': -1
    };

    $scope.users = [];
    $scope.userLogins = [];
    $scope.uploadedDictionaries = [];


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

    var getLanguageById = function (id) {
        if (typeof id == 'string') {
            var ids = id.split('_');
            for (var i = 0; i < $scope.languages.length; i++) {
                if ($scope.languages[i].client_id == ids[0] && $scope.languages[i].object_id == ids[1])

                    return $scope.languages[i];
            }
        }
    };

    // Data loaded from backend
    $scope.languages = [];
    $scope.perspectives = [];


    $scope.dictionaryData = {
        'languageId': -1,
        'perspectiveName': '',
        'perspectiveId': -1,
        'isTemplate': false

    };
    // current perspective
    $scope.perspective = {
        fields: []
    };

    $scope.controls = {
        'createDictionary': true,
        'createPerspective': true,
        'saveDictionary': true
    };

    // Event handlers

    $scope.getLanguageId = function (language) {
        if (language) {
            return language.client_id + '_' + language.object_id;
        }
    };

    $scope.newLanguage = function () {
        var modalInstance = $modal.open({
            animation: true,
            templateUrl: 'createLanguageModal.html',
            controller: 'CreateLanguageController',
            size: 'lg'
        });

        modalInstance.result.then(function (languageObj) {
            $http.post(createLanguageUrl, languageObj).success(function (data, status, headers, config) {
                loadLanguages();
            }).error(function (data, status, headers, config) {
                alert('Failed to save language!');
            });
        }, function () {
        });
    };

    $scope.addField = function () {
        $scope.perspective.fields.push({'entity_type': '', 'entity_type_translation': '', 'data_type': 'text', 'data_type_translation': 'text', 'status': 'enabled'});
    };

    $scope.enableGroup = function (fieldIndex) {
        if (typeof $scope.perspective.fields[fieldIndex].group === 'undefined') {
            $scope.perspective.fields[fieldIndex].group = '';
        } else {
            delete $scope.perspective.fields[fieldIndex].group;
        }
    };

    $scope.enableLinkedField = function (fieldIndex) {
        if (typeof $scope.perspective.fields[fieldIndex].contains === 'undefined') {
            $scope.perspective.fields[fieldIndex].contains = [{
                'entity_type': '',
                'entity_type_translation': '',
                'data_type': 'markup',
                'data_type_translation': 'markup',
                'status': 'enabled'
            }];
        } else {
            delete $scope.perspective.fields[fieldIndex].contains;
        }
    };

    // Save dictionary
    $scope.createDictionary = function() {

        var language = getLanguageById($scope.dictionaryData.languageId);
        if ((!$scope.dictionaryData.name && $scope.wizard.mode == 'create') || (typeof $scope.wizard.importedDictionaryId != 'string' && $scope.wizard.mode == 'import') || !language) {
            return;
        }

        if ($scope.wizard.mode == 'create') {

            var dictionaryObj = {
                'parent_client_id': language.client_id,
                'parent_object_id': language.object_id,
                'translation_string': $scope.dictionaryData.name,
                'translation': $scope.dictionaryData.name
            };

            $scope.controls.createDictionary = false;

            $http.post(createDictionaryUrl, dictionaryObj).success(function (data, status, headers, config) {

                if (data.object_id && data.client_id) {
                    $scope.dictionaryData.dictionary_client_id = data.client_id;
                    $scope.dictionaryData.dictionary_object_id = data.object_id;
                    $scope.controls.createDictionary = true;
                    $state.go('create.step2');
                } else {
                    responseHandler.error('Failed to create dictionary!');
                }
                $scope.controls.createDictionary = true;

            }).error(function (data, status, headers, config) {
                $scope.controls.createDictionary = true;
                responseHandler.error('Failed to create dictionary!');
            });
        }


        if ($scope.wizard.mode == 'import') {

            if (typeof $scope.wizard.importedDictionaryId == 'string') {

                $scope.controls.createDictionary = false;

                var ids = $scope.wizard.importedDictionaryId.split('_');
                var url = $('#convertUrl').data('lingvodoc');
                var convertObject = {
                    'blob_client_id': parseInt(ids[0]),
                    'blob_object_id': parseInt(ids[1]),
                    'parent_client_id': language.client_id,
                    'parent_object_id': language.object_id
                };

                $http.post(url, convertObject).success(function (data, status, headers, config) {
                    $scope.controls.createDictionary = true;
                    responseHandler.success(data.status);
                }).error(function (data, status, headers, config) {
                    $scope.controls.createDictionary = true;
                    responseHandler.error(data);
                });
            }
        }
    };

    // Save perspective
    $scope.createPerspective = function() {

        if (!$scope.dictionaryData.perspectiveName) {
            return;
        }

        var createPerspectiveUrl = '/dictionary/' + encodeURIComponent($scope.dictionaryData.dictionary_client_id) + '/' + encodeURIComponent($scope.dictionaryData.dictionary_object_id) + '/' + 'perspective';
        var perspectiveObj = {
            'translation_string': $scope.dictionaryData.perspectiveName,
            'translation': $scope.dictionaryData.perspectiveName,
            'is_template': $scope.dictionaryData.isTemplate
        };

        $scope.controls.createPerspective = false;

        $http.post(createPerspectiveUrl, perspectiveObj).success(function(data, status, headers, config) {

            if (data.object_id && data.client_id) {
                $scope.dictionaryData.perspective_client_id = data.client_id;
                $scope.dictionaryData.perspective_object_id = data.object_id;
                var setFieldsUrl = '/dictionary/' + encodeURIComponent($scope.dictionaryData.dictionary_client_id) + '/' + encodeURIComponent($scope.dictionaryData.dictionary_object_id) + '/perspective/' + encodeURIComponent($scope.dictionaryData.perspective_client_id) + '/' + encodeURIComponent($scope.dictionaryData.perspective_object_id) + '/fields';

                $http.post(setFieldsUrl, exportPerspective($scope.perspective)).success(function(data, status, headers, config) {
                    $scope.controls.createPerspective = true;
                    window.location = '/dashboard';
                }).error(function(data, status, headers, config) {
                    $scope.controls.createPerspective = true;
                    responseHandler.error('Failed to create perspective!');
                });

            } else {
                $scope.controls.createPerspective = true;
                responseHandler.error('Failed to create perspective!');
            }

        }).error(function(data, status, headers, config) {
            $scope.controls.createPerspective = true;
            responseHandler.error('Failed to create perspective!');
        });

    };


    $scope.searchUsers = function(query) {
        var promise = $http.get('/users?search=' + encodeURIComponent(query)).then(function (response) {
            return response.data;
        });
        promise.then(function(data){
            var userLogins = [];
            if (data.users) {
                for (var i = 0; i < data.users.length; i++) {
                    var user = data.users[i];
                    userLogins.push(user.login);
                }

                $scope.userLogins = userLogins;
                $scope.users = data.users;
            }
        });
    };


    $scope.addUser = function(userLogin) {

    };

    // Load data from backend

    // Load list of languages
    var loadLanguages = function() {
        $http.get(languagesUrl).success(function (data, status, headers, config) {
            $scope.languages = flatLanguages(data.languages);
        }).error(function (data, status, headers, config) {
            // error handling
        });
    };


    var loadBlobs = function() {
        $http.get(listBlobsUrl).success(function (data, status, headers, config) {
            $scope.uploadedDictionaries = [];


            for (var i = 0; i < data.length; i++) {
                if (data[i].data_type='dialeqt_dictionary') {
                    var id = data[i].client_id + '_' + data[i].object_id;

                    $scope.uploadedDictionaries.push({
                        'id': id,
                        'data': data[i]
                    });
                }
            }


        }).error(function (data, status, headers, config) {
        });
    };


    $scope.$watch('dictionaryData.perspectiveId', function (id) {
        if (typeof id == 'string') {
            for (var i = 0; i < $scope.perspectives.length; i++) {
                if ($scope.perspectives[i].getId() == id) {
                    $scope.perspective = $scope.perspectives[i];

                    dictionaryService.getPerspectiveFieldsNew($scope.perspective).then(function(fields) {
                        $scope.perspective.fields = fields;
                    }, function(reason) {
                        responseHandler.error(reason);
                    });
                    break;
                }
            }
        }
    });

    dictionaryService.getAllPerspectives().then(function(perspectives) {
        $scope.perspectives = perspectives;
    }, function(reason) {
        responseHandler.error(reason);
    });


    loadLanguages();
    loadBlobs();
}]);


app.controller('CreateLanguageController', ['$scope', '$http', '$interval', '$modalInstance', 'responseHandler', function ($scope, $http, $interval, $modalInstance, responseHandler) {

    var clientId = $('#clientId').data('lingvodoc');
    var userId = $('#userId').data('lingvodoc');
    var languagesUrl = $('#languagesUrl').data('lingvodoc');
    var createLanguageUrl = $('#createLanguageUrl').data('lingvodoc');

    $scope.languages = [];
    $scope.parentLanguageId = -1;
    $scope.translation = '';
    $scope.translationString = '';

    var getLanguageById = function (id) {
        var ids = id.split('_');
        for (var i = 0; i < $scope.languages.length; i++) {
            if ($scope.languages[i].client_id == ids[0] && $scope.languages[i].object_id == ids[1])
                return $scope.languages[i];
        }
    };

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

    $scope.getLanguageId = function (language) {
        if (language) {
            return language.client_id + '_' + language.object_id;
        }
    };

    $scope.ok = function () {

        if (!$scope.translation) {
            return;
        }

        var languageObj = {
            'translation': $scope.translation,
            'translation_string': $scope.translation
        };

        if ($scope.parentLanguageId != '-1') {
            var parentLanguage = getLanguageById($scope.parentLanguageId);
            if (parentLanguage) {
                languageObj['parent_client_id'] = parentLanguage.client_id;
                languageObj['parent_object_id'] = parentLanguage.object_id;
            }
        }

        $modalInstance.close(languageObj);
    };

    $scope.cancel = function () {
        $modalInstance.dismiss('cancel');
    };

    $http.get(languagesUrl).success(function (data, status, headers, config) {
        $scope.languages = flatLanguages(data.languages);
    }).error(function (data, status, headers, config) {
        // error handling
    });
}]);