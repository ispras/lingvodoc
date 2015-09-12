'use strict';

var app = angular.module('DashboardModule', ['ui.bootstrap']);

app.controller('DashboardController', ['$scope', '$http', '$modal', '$interval', function($scope, $http, $modal, $interval) {

    var dictionariesUrl = $('#dictionariesUrl').data('lingvodoc');

    $scope.dictionaries = [];
    
    $http.get(dictionariesUrl).success(function(data, status, headers, config) {
        $scope.dictionaries = data;

        $interval(function() {
            $http.get(dictionariesUrl).success(function(data, status, headers, config) {
                $scope.dictionaries = data;
            }).error(function(data, status, headers, config) {
                // error handling
            });

        }, 30000);
    }).error(function(data, status, headers, config) {
        // error handling
    });











}]);