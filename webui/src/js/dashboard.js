'use strict';

var app = angular.module('DashboardModule', ['ui.router', 'ui.bootstrap']);

app.controller('DashboardController', ['$scope', '$http', '$interval', '$log', function($scope, $http, $modal, $interval, $log) {

    var userId = $('#userId').data('lingvodoc');
    var languagesUrl = $('#languagesUrl').data('lingvodoc');
    var dictionariesUrl = $('#dictionariesUrl').data('lingvodoc');
    var getUserInfoUrl = $('#getUserInfoUrl').data('lingvodoc');

    $scope.dictionaries = [];

    $scope.getEditDictionaryLink = function(dictionary) {
        return '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/{perspective_client_id}/{perspective_id}/edit';
    };

    $scope.getViewDictionaryLink = function(dictionary) {
        return '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/{perspective_client_id}/{perspective_id}/view';
    };

    var dictionaryQuery = {
        'user_created': [userId]
        //'user_participated': [userId]
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



