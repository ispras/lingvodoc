'use strict';

var app = angular.module('LanguagesModule', ['ui.bootstrap']);

app.controller('LanguagesController', ['$scope', '$http', '$modal', '$interval', '$log', function($scope, $http, $modal, $interval, $log) {

    var clientId = $('#clientId').data('lingvodoc');
    var userId = $('#userId').data('lingvodoc');
    var languagesUrl = $('#languagesUrl').data('lingvodoc');
    var createLanguageUrl = $('#createLanguageUrl').data('lingvodoc');

    var createLanguage = function(lang) {
        $http.post(createLanguageUrl, lang).success(function(data, status, headers, config) {

        }).error(function(data, status, headers, config) {
            // error handling
        });
    };

    $scope.languages = [];
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

    $scope.createLanguage = function() {
        var modalInstance = $modal.open({
            animation  : true,
            templateUrl: 'createLanguageModal.html',
            controller : 'CreateLanguageController',
            size       : 'lg'
        });

        modalInstance.result.then(function (languageObj) {
            createLanguage(languageObj);
        }, function () {
            $log.info('Modal dismissed at: ' + new Date());
        });
    };
}]);



