'use strict';

var app = angular.module('DashboardModule', ['ui.router', 'ngAnimate', 'ui.bootstrap']);

app.controller('DashboardController', ['$scope', '$http', '$modal', '$interval', '$log', function($scope, $http, $modal, $interval, $log) {

    var userId = $('#userId').data('lingvodoc');
    var languagesUrl = $('#languagesUrl').data('lingvodoc');
    var dictionariesUrl = $('#dictionariesUrl').data('lingvodoc');
    var createDictionaryUrl = $('#createDictionaryUrl').data('lingvodoc');
    var getUserInfoUrl = $('#getUserInfoUrl').data('lingvodoc');

    $scope.dictionaries = [];

    $scope.createDictionary = function() {
        var modalInstance = $modal.open({
            animation  : true,
            templateUrl: 'createDictionaryModal.html',
            controller : 'CreateDictionaryController',
            size       : 'lg'
        });

        modalInstance.result.then(function (dictionaryObj) {

            $http.post(createDictionaryUrl, dictionaryObj).success(function(data, status, headers, config) {

                $log.info(dictionaryObj);

            }).error(function(data, status, headers, config) {
                // error handling
            });


        }, function () {
            $log.info('Modal dismissed at: ' + new Date());
        });
    };

    $scope.getEditDictionaryLink = function(dictionary) {
        return '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/{perspective_client_id}/{perspective_id}/edit';
    };

    $scope.getViewDictionaryLink = function(dictionary) {
        return '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/{perspective_client_id}/{perspective_id}/view';
    };

    var dictionaryQuery = {
        'user_created': [userId],
        'user_participated': [userId]
    };

    $http.post(dictionariesUrl, dictionaryQuery).success(function(data, status, headers, config) {
        $scope.dictionaries = data.dictionaries;

        $interval(function() {
            $http.post(dictionariesUrl, dictionaryQuery).success(function(data, status, headers, config) {
                $scope.dictionaries = data.dictionaries;
            }).error(function(data, status, headers, config) {
                // error handling
            });

        }, 30000);
    }).error(function(data, status, headers, config) {
        // error handling
    });
}]);


app.controller('CreateDictionaryControllerOld', ['$scope', '$http', '$interval', '$modalInstance', function($scope, $http, $interval, $modalInstance) {

    var userId = $('#userId').data('lingvodoc');
    var languagesUrl = $('#languagesUrl').data('lingvodoc');
    var dictionariesUrl = $('#dictionariesUrl').data('lingvodoc');
    var createDictionaryUrl = $('#createDictionaryUrl').data('lingvodoc');

    $scope.languages = [];
    $scope.languageId = -1;
    $scope.name = '';
    $scope.translation = '';

    var getLanguageById = function(id) {
        for (var i = 0; i < $scope.languages.length; i++) {
            if ($scope.languages[i].object_id == id)
                return $scope.languages[i];
        }
    };

    $http.get(languagesUrl).success(function(data, status, headers, config) {
        $scope.languages = data.languages;

        $interval(function() {
            $http.get(languagesUrl).success(function(data, status, headers, config) {
                $scope.languages = data.languages;

            }).error(function(data, status, headers, config) {
                // error handling
            });
        }, 30000);
    }).error(function(data, status, headers, config) {
        // error handling
    });

    $scope.ok = function () {

        var language = getLanguageById($scope.languageId);
        if ($scope.translation == '' || $scope.name == '' || !language) {
            return;
        }

        var dictionaryObj = {
            'parent_client_id': language.client_id,
            'parent_object_id': language.object_id,
            'name': $scope.name,
            'translation': $scope.translation
        };

        $modalInstance.close(dictionaryObj);
    };

    $scope.cancel = function () {
        $modalInstance.dismiss('cancel');
    };

}]);

