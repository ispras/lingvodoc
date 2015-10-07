'use strict';

var app = angular.module('OrganizationsModule', ['ui.bootstrap']);

app.service('dictionaryService', lingvodocAPI);

app.controller('OrganizationsController', ['$scope', '$http', '$q', '$modal', '$log', 'dictionaryService', function ($scope, $http, $q, $modal, $log, dictionaryService) {

    var userId = $('#userId').data('lingvodoc');
    var clientId = $('#clientId').data('lingvodoc');



    $scope.create = function() {
        $modal.open({
            animation: true,
            templateUrl: 'createOrganization.html',
            controller: 'createOrganizationController',
            size: 'lg',
            backdrop: 'static',
            keyboard: false,
            resolve: {
                'params': function() {
                    return {};
                }
            }
        }).result.then(function(result) {

        }, function() {

        });
    };

    $scope.edit = function(org) {
        $modal.open({
            animation: true,
            templateUrl: 'editOrganization.html',
            controller: 'editOrganizationController',
            size: 'lg',
            backdrop: 'static',
            keyboard: false,
            resolve: {
                'params': function() {
                    return {
                        'organization': org
                    };
                }
            }
        }).result.then(function(result) {

            }, function() {

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
        $log.error(reason);
    });



}]);


app.controller('createOrganizationController', ['$scope', '$http', '$modalInstance', '$log', 'dictionaryService', 'params', function($scope, $http, $modalInstance, $log, dictionaryService, params) {

    $scope.name = '';
    $scope.about = '';

    $scope.ok = function() {

        var orgObj = {
            'name': $scope.name,
            'about': $scope.about
        };

        dictionaryService.createOrganization(orgObj).then(function(data) {
            $modalInstance.close();
        }, function(reason) {
            $modalInstance.close();
        });

    };

    $scope.cancel = function() {
        $modalInstance.dismiss('cancel');
    };

}]);

app.controller('editOrganizationController', ['$scope', '$http', '$modalInstance', '$log', 'dictionaryService', 'params', function($scope, $http, $modalInstance, $log, dictionaryService, params) {

    $scope.name = '';
    $scope.about = '';
    $scope.searchQuery = '';

    $scope.users = [];
    $scope.suggestedUsers = [];

    var addedUsers = [];
    var removedUsers = [];

    $scope.ok = function() {

        var orgObj = {
            'name': $scope.name,
            'about': $scope.about,
            'add_users': addedUsers,
            'delete_users': removedUsers
        };

        dictionaryService.editOrganization(orgObj).then(function(data) {
            $modalInstance.close();
        }, function(reason) {
            $modalInstance.close();
        });

    };


    $scope.add = function(user) {

        var m = $scope.users.filter(function(u) {
            return u.id === user.id;
        });

        if (m.length > 0) {
            return;
        }

        var cuser = cloneObject(user);
        cuser['added'] = true;
        $scope.users.push(cuser);
        addedUsers.push(user);
    };

    $scope.remove = function(user) {
        removedUsers.push(user);
        addedUsers = addedUsers.filter(function(obj) {
            return obj.id !== user.id;
        });
        $scope.users = $scope.users.filter(function(obj) {
            return obj.id !== user.id;
        });
    };

    $scope.cancel = function() {
        $modalInstance.dismiss('cancel');
    };

    $scope.$watch('searchQuery', function(updatedQuery) {

        if (!updatedQuery || updatedQuery.length < 3) {
            return;
        }

        $scope.suggestedUsers = [];
        dictionaryService.searchUsers(updatedQuery).then(function(users) {
            $scope.suggestedUsers = users;
        }, function(reason) {

        });

    }, true);


    dictionaryService.getOrganization(params.organization.organization_id).then(function(data) {
        $scope.name = data.name;
        $scope.about = data.about;
    }, function(reason) {

    });

}]);
