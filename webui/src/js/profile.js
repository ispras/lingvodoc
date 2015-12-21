'use strict';

var app = angular.module('ProfileModule', ['ui.bootstrap']);

app.service('dictionaryService', lingvodocAPI);

app.factory('responseHandler', ['$timeout', '$modal', responseHandler]);

app.controller('ProfileController', ['$scope', '$http', '$q', '$modal', '$log', 'dictionaryService', 'responseHandler', function ($scope, $http, $q, $modal, $log, dictionaryService, responseHandler) {

    var userId = $('#userId').data('lingvodoc');
    var clientId = $('#clientId').data('lingvodoc');
    $scope.userInfo = {};


    $scope.save = function() {
        dictionaryService.setUserInfo(userId, clientId, $scope.userInfo).then(function(userInfo) {

        }, function(reason) {

        });
    };

    dictionaryService.getUserInfo(userId, clientId).then(function(userInfo) {
        $scope.userInfo = userInfo;
        var dateSplit = userInfo.birthday.split('-');
        if (dateSplit.length > 1) {

            $scope.birthdayYear = dateSplit[0];
            $scope.birthdayMonth = dateSplit[1];
            $scope.birthdayDay = dateSplit[2]
        }

    }, function(reason) {
        responseHandler.error(reason);
    });
}]);



