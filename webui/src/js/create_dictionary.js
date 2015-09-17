var app = angular.module('CreateDictionaryModule', ['ui.router', 'ngAnimate', 'ui.bootstrap', 'ngDraggable']);

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

app.controller('CreateDictionaryController', ['$scope', '$http', '$interval', function ($scope, $http, $interval) {

    var clientId = $('#clientId').data('lingvodoc');
    var userId = $('#userId').data('lingvodoc');
    var languagesUrl = $('#languagesUrl').data('lingvodoc');
    var createLanguageUrl = $('#createLanguageUrl').data('lingvodoc');


    $scope.dictionaryData = {};
    $scope.draggableObjects = [{name: 'one', type: 'text'}, {name: 'two'}, {name: 'three'}];




    $scope.fieldTypes = [
        {
            'type':  'text',
            'description': 'Simple text field'
        },
        {
            'type':  'group',
            'description': 'Groupping field'
        }
    ];


    $scope.droppedObjects = [];

    $scope.onDropComplete=function(data, evt){
        console.log('drop success!');
        var index = $scope.droppedObjects.indexOf(data);
        if (index == -1) {
            $scope.droppedObjects.push(data);
        }
    };

    $scope.onDragSuccess=function(data, evt){
        var index = $scope.droppedObjects.indexOf(data);
        if (index > -1) {
            $scope.droppedObjects.splice(index, 1);
        }
    };

    $scope.onDragStop=function(data, evt){



    };


    // Save dictionary
    $scope.saveDictionary = function() {
        console.log($scope.dictionaryData);
    };




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




}]);