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

app.controller('CreateDictionaryController', ['$scope', '$http', '$modal', '$interval', '$log', function ($scope, $http, $modal, $interval, $log) {

    var clientId = $('#clientId').data('lingvodoc');
    var userId = $('#userId').data('lingvodoc');
    var languagesUrl = $('#languagesUrl').data('lingvodoc');
    var createLanguageUrl = $('#createLanguageUrl').data('lingvodoc');

    var examplePerspective = {
        'fields': [{'entity_type': 'protoform', 'data_type': 'text', 'status': 'enabled'},
            {'entity_type': 'transcription', 'data_type': 'text', 'status': 'enabled'},
            {'entity_type': 'translation', 'data_type': 'text', 'status': 'enabled'},
            {
                'entity_type': 'sound',
                'data_type': 'sound',
                'status': 'enabled',
                'contains': [{'entity_type': 'praat', 'data_type': 'markup', 'status': 'enabled'}]
            },
            {'entity_type': 'paradigm_protoform', 'data_type': 'text', 'status': 'enabled', 'group': 'paradigm'},
            {'entity_type': 'paradigm_transcription', 'data_type': 'text', 'status': 'enabled', 'group': 'paradigm'},
            {'entity_type': 'paradigm_translation', 'data_type': 'text', 'status': 'enabled', 'group': 'paradigm'},
            {
                'entity_type': 'paradigm_sound',
                'data_type': 'sound',
                'status': 'enabled',
                'contains': [{'entity_type': 'paradigm_praat', 'data_type': 'markup', 'status': 'enabled'}]
            },
            {'entity_type': 'etymology', 'data_type': 'grouping_tag', 'status': 'enabled'}
        ],
        'name': 'perspective_name',
        'object_id': 'object_id',
        'client_id': 'client_id'
    };

    $scope.users = [];

    var wrapPerspective = function (perspective) {

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
        var ids = id.split('_');
        for (var i = 0; i < $scope.languages.length; i++) {
            if ($scope.languages[i].client_id == ids[0] && $scope.languages[i].object_id == ids[1])
                return $scope.languages[i];
        }
    };


    // Data loaded from backend
    $scope.languages = [];
    $scope.perspectives = [wrapPerspective(examplePerspective)];


    $scope.dictionaryData = {
        'languageId': -1
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
    $scope.saveDictionary = function () {
        console.log($scope.perspective);
    };


    $scope.searchUsers = function(query) {
        var promise = $http.get('').then(function (response) {
            return response.data;
        });
        promise.then(function(data){
            $scope.users = data;
        });
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

    $scope.$watch('dictionaryData.perspectiveId', function (id) {
        for (var i = 0; i < $scope.perspectives.length; i++) {
            if ($scope.perspectives[i].object_id == id) {
                $scope.perspective = $scope.perspectives[i];
                break;
            }
        }
    });


    // Load list of perspectives
    //$http.get(languagesUrl).success(function(data, status, headers, config) {
    //
    //    $scope.languages = data.languages;
    //
    //    // Reload list every 3 seconds
    //    $interval(function() {
    //        $http.get(languagesUrl).success(function(data, status, headers, config) {
    //            $scope.languages = data.languages;
    //        }).error(function(data, status, headers, config) {
    //            // error handling
    //        });
    //
    //    }, 3000);
    //}).error(function(data, status, headers, config) {
    //    // error handling
    //});

    loadLanguages();

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