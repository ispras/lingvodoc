'use strict';

var app = angular.module('LanguagesModule', ['ui.bootstrap']);

app.controller('LanguagesController', ['$scope', '$http', '$modal', '$interval', '$log', function($scope, $http, $modal, $interval, $log) {

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



app.controller('CreateLanguageController', ['$scope', '$http', '$interval', '$modalInstance', function($scope, $http, $interval, $modalInstance) {

    var userId = $('#userId').data('lingvodoc');
    var languagesUrl = $('#languagesUrl').data('lingvodoc');

    $scope.languages = [];
    $scope.parentLanguageId = -1;
    $scope.translation = '';
    $scope.translationString = '';

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

}]);