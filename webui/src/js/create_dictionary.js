var app = angular.module('CreateDictionaryModule', ['ui.router', 'ngAnimate', 'ui.bootstrap', 'autocomplete']);

app.config(function ($stateProvider, $urlRouterProvider) {

    $stateProvider

        .state('create', {
            url: '/create',
            templateUrl: 'createDictionary.html',
            controller: 'CreateDictionaryController'
        })

        .state('create.step1', {
            url: '/step1',
            templateUrl: 'createDictionaryStep1.html',
        })

        .state('create.step2', {
            url: '/step2',
            templateUrl: 'createDictionaryStep2.html',
        })

        .state('create.step3', {
            url: '/step3',
            templateUrl: 'createDictionaryStep3.html'
        });

    $urlRouterProvider.otherwise('/create/step1');
});

app.controller('CreateDictionaryController', ['$scope', '$http', '$modal', '$interval', '$state', '$log', function ($scope, $http, $modal, $interval, $state, $log) {

    var clientId = $('#clientId').data('lingvodoc');
    var userId = $('#userId').data('lingvodoc');
    var languagesUrl = $('#languagesUrl').data('lingvodoc');
    var createLanguageUrl = $('#createLanguageUrl').data('lingvodoc');
    var createDictionaryUrl = $('#createDictionaryUrl').data('lingvodoc');
    var allPerspectivesUrl = $('#allPerspectivesUrl').data('lingvodoc');
    var perspectiveFieldsUrl = '/dictionary';



    $scope.users = [];
    $scope.userLogins = [];

    var wrapPerspective = function (perspective) {

        if (typeof perspective.fields == 'undefined') {
            return;
        }

        for (var i = 0; i < perspective.fields.length; i++) {
            if (typeof perspective.fields[i].group !== 'undefined') {
                perspective.fields[i]._groupEnabled = true;
            }

            if (typeof perspective.fields[i].contains !== 'undefined') {
                perspective.fields[i]._containsEnabled = true;
            }
        }

        return perspective;
    };

    var exportPerpective = function(perspective) {
      var jsPerspective = {
          'fields': []
      };

        var positionCount = 1;
        for (var i = 0; i < perspective.fields.length; i++) {

            var field = JSON.parse(JSON.stringify(perspective.fields[i]));

            field['position'] = positionCount;
            positionCount += 1;

            if (field.data_type !== 'grouping_tag') {
                field['level'] = 'L1E';
            } else {
                field['level'] = 'GE';
            }

            if (field._groupEnabled) {
                delete field._groupEnabled;
            }


            if (field._containsEnabled) {
                delete field._containsEnabled;
            }

            if (field.contains) {
                for (var j = 0; j < field.contains.length; j++) {
                    field.contains[j].level = 'L2E';
                    field.contains[j].position = positionCount;
                    positionCount += 1;
                }
            }
            jsPerspective.fields.push(field);
        }

        console.log(jsPerspective);
        return jsPerspective;
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
        'perspectiveId': -1

    };
    // current perspective
    $scope.perspective = {
        fields: []
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
            $log.info('Modal dismissed at: ' + new Date());
        });
    };

    $scope.addField = function () {
        $scope.perspective.fields.push({'entity_type': '', 'data_type': 'text', 'status': 'enabled'});
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
                'data_type': 'markup',
                'status': 'enabled'
            }];
        } else {
            delete $scope.perspective.fields[fieldIndex].contains;
        }
    };

    // Save dictionary
    $scope.createDictionary = function() {

        var language = getLanguageById($scope.dictionaryData.languageId);
        if (!$scope.dictionaryData.name) {
            return;
        }

        var dictionaryObj = {
            'parent_client_id': language.client_id,
            'parent_object_id': language.object_id,
            'name': $scope.dictionaryData.name,
            'translation': $scope.dictionaryData.name
        };

        $http.post(createDictionaryUrl, dictionaryObj).success(function(data, status, headers, config) {

            if (data.object_id && data.client_id) {
                $scope.dictionaryData.dictionary_client_id = data.client_id;
                $scope.dictionaryData.dictionary_object_id = data.object_id;
                $state.go('create.step2');
            } else {
                alert('Failed to create dictionary!');
            }

        }).error(function(data, status, headers, config) {
            alert('Failed to create dictionary!');
        });
    };


    // Save perspective
    $scope.createPerspective = function() {

        if (!$scope.dictionaryData.perspectiveName) {
            return;
        }

        var createPerspectiveUrl = '/dictionary/' + encodeURIComponent($scope.dictionaryData.dictionary_client_id) + '/' + encodeURIComponent($scope.dictionaryData.dictionary_object_id) + '/' + 'perspective';
        var perspectiveObj = {
            'name': $scope.dictionaryData.perspectiveName,
            'translation': $scope.dictionaryData.perspectiveName
        };

        $http.post(createPerspectiveUrl, perspectiveObj).success(function(data, status, headers, config) {

            if (data.object_id && data.client_id) {
                $scope.dictionaryData.perspective_client_id = data.client_id;
                $scope.dictionaryData.perspective_object_id = data.object_id;
                var setFieldsUrl = '/dictionary/' + encodeURIComponent($scope.dictionaryData.dictionary_client_id) + '/' + encodeURIComponent($scope.dictionaryData.dictionary_object_id) + '/perspective/' + encodeURIComponent($scope.dictionaryData.perspective_client_id) + '/' + encodeURIComponent($scope.dictionaryData.perspective_object_id) + '/fields';

                $http.post(setFieldsUrl, exportPerpective($scope.perspective)).success(function(data, status, headers, config) {
                    $state.go('create.step2');
                }).error(function(data, status, headers, config) {
                    alert('Failed to create perspective!');
                });

            } else {
                alert('Failed to create perspective!');
            }

        }).error(function(data, status, headers, config) {
            alert('Failed to create perspective!');
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
    // Reload list every 3 seconds
    var loadLanguages = function() {
        $http.get(languagesUrl).success(function (data, status, headers, config) {
            $scope.languages = flatLanguages(data.languages);
        }).error(function (data, status, headers, config) {
            // error handling
        });
    };

    var loadPerspectives = function() {
        var perspectives = [];
        $http.get(allPerspectivesUrl).success(function(data, status, headers, config) {
            for (var i = 0; i < data.perspectives.length; i++) {

                var perspective = data.perspectives[i];
                var url = '/dictionary/' + perspective.parent_client_id + '/' + perspective.parent_object_id + '/perspective/' + perspective.client_id + '/' + perspective.object_id + '/fields';

                $http.get(url).success((function (perspective) {
                    return function(data, status, headers, config) {
                        var p = { };
                        p.name = perspective.name;
                        p.object_id = perspective.object_id;
                        p.client_id = perspective.client_id;
                        p.fields = data.fields;

                        var wrappedPerspective = wrapPerspective(p);
                        if (wrappedPerspective) {
                            $scope.perspectives.push(wrappedPerspective);
                        }
                        console.log(wrappedPerspective);
                    }
                })(perspective)).error(function(data, status, headers, config) {
                    $log.error('Failed to load perspectives!');
                });
            }
        }).error(function(data, status, headers, config) {
            $log.error('Failed to load perspectives!');
        });
    };

    $scope.$watch('dictionaryData.perspectiveId', function (id) {

        console.log("Change!");
        console.log($scope.dictionaryData);

        if (typeof id == 'string') {
            var ids = id.split('_');
            for (var i = 0; i < $scope.perspectives.length; i++) {
                if ($scope.perspectives[i].client_id == ids[0] && $scope.perspectives[i].object_id == ids[1]) {
                    $scope.perspective = $scope.perspectives[i];
                    console.log('Found!');
                    break;
                }
            }

            console.log($scope.perspective);
        }
    });

    loadLanguages();
    loadPerspectives();
}]);


app.controller('CreateLanguageController', ['$scope', '$http', '$interval', '$modalInstance', function ($scope, $http, $interval, $modalInstance) {

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
        $interval(function () {
            $http.get(languagesUrl).success(function (data, status, headers, config) {
                $scope.languages = flatLanguages(data.languages);
            }).error(function (data, status, headers, config) {
                // error handling
            });
        }, 3000);
    }).error(function (data, status, headers, config) {
        // error handling
    });


}]);