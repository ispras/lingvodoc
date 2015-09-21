'use strict';

var app = angular.module('DashboardModule', ['ui.bootstrap']);

app.controller('DashboardController', ['$scope', '$http', '$interval', '$log', function ($scope, $http, $modal, $interval, $log) {

    var userId = $('#userId').data('lingvodoc');
    var languagesUrl = $('#languagesUrl').data('lingvodoc');
    var dictionariesUrl = $('#dictionariesUrl').data('lingvodoc');
    var getUserInfoUrl = $('#getUserInfoUrl').data('lingvodoc');

    $scope.dictionaries = [];


    var getObjectByCompositeKey = function (id, arr) {
        if (typeof id == 'string') {
            var ids = id.split('_');
            for (var i = 0; i < arr.length; i++) {
                if (arr[i].client_id == ids[0] && arr[i].object_id == ids[1])
                    return arr[i];
            }
        }
    };


    $scope.getActionDictionaryLink = function (dictionary, action) {
        if (dictionary.selectedPerspectiveId != -1) {
            var perspective = getObjectByCompositeKey(dictionary.selectedPerspectiveId, dictionary.perspectives);
            if (perspective) {
                var perspectiveClientId = perspective.client_id;
                var perspectiveObjectId = perspective.object_id;
            }
            return '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(perspectiveClientId) + '/' + encodeURIComponent(perspectiveObjectId) + '/' + action;
        }
    };


    $scope.test = function () {
        console.log($scope.dictionaries);
    };

    $scope.getCompositeKey = function (object) {
        if (object) {
            return object.client_id + '_' + object.object_id;
        }
    };


    var dictionaryQuery = {
        'user_created': [userId]
        //'user_participated': [userId]
    };


    $http.post(dictionariesUrl, dictionaryQuery).success(function (data, status, headers, config) {
        $scope.dictionaries = data.dictionaries;
        for (var i = 0; i < $scope.dictionaries.length; i++) {
            var dictionary = $scope.dictionaries[i];
            var getPerspectivesUrl = '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspectives';
            $http.get(getPerspectivesUrl).success((function (index) {
                return function (data, status, headers, config) {
                    $scope.dictionaries[index]['perspectives'] = data.perspectives;
                    $scope.dictionaries[index]['selectedPerspectiveId'] = -1;
                };
            })(i)).error(function (data, status, headers, config) {
                // error handling
            });
        }
    }).error(function (data, status, headers, config) {
        // error handling
    });


}]);



