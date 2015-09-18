var app = angular.module('CreateDictionaryModule', ['ui.router', 'ngAnimate', 'ui.bootstrap']);

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
            controller: 'CreateDictionaryController'
        })

        .state('create.step2', {
            url: '/step2',
            templateUrl: 'createDictionaryStep2.html',
            controller: 'CreateDictionaryController'
        })

        .state('create.step3', {
            url: '/step3',
            templateUrl: 'createDictionaryStep3.html'
        });

    $urlRouterProvider.otherwise('/create/step1');
});

app.controller('CreateDictionaryController', ['$scope', '$http', '$interval', function ($scope, $http, $interval) {

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


    var wrapPerspective = function(perspective) {

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


    // Data loaded from backend
    $scope.languages = [];
    $scope.perspectives = [ wrapPerspective(examplePerspective) ];



    $scope.dictionaryData = {};
    // current perspective
    $scope.perspective =  {};


    // Event handlers

    $scope.enableGroup = function(fieldIndex) {
        if (typeof $scope.perspective.fields[fieldIndex].group === 'undefined') {
            $scope.perspective.fields[fieldIndex].group = '';
        } else {
            delete $scope.perspective.fields[fieldIndex].group;
        }
    };

    $scope.enableLinkedField = function(fieldIndex) {
        if (typeof $scope.perspective.fields[fieldIndex].contains === 'undefined') {
            console.log('enabled');
            $scope.perspective.fields[fieldIndex].contains = [{'entity_type': '', 'data_type': 'markup', 'status': 'enabled'}];
        } else {
            console.log('disabled');
            delete $scope.perspective.fields[fieldIndex].contains;
        }
    };

    // Save dictionary
    $scope.saveDictionary = function() {
        console.log($scope.perspective);
    };

    // Load data from backend

    // Load list of languages
    $http.get(languagesUrl).success(function(data, status, headers, config) {

        $scope.languages = data.languages;

        // Reload list every 3 seconds
        $interval(function() {
            $http.get(languagesUrl).success(function(data, status, headers, config) {
                $scope.languages = data.languages;
            }).error(function(data, status, headers, config) {
                // error handling
            });

        }, 3000);
    }).error(function(data, status, headers, config) {
        // error handling
    });

    $scope.$watch('dictionaryData.perspectiveId', function(id){
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


}]);