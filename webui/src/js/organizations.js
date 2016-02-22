'use strict';

var app = angular.module('OrganizationsModule', ['ui.bootstrap']);

app.service('dictionaryService', lingvodocAPI);

app.factory('responseHandler', ['$timeout', '$modal', responseHandler]);

app.directive('translatable', ['dictionaryService', getTranslation]);


app.controller('OrganizationsController', ['$scope', '$http', '$q', '$modal', '$log', 'dictionaryService', 'responseHandler', function ($scope, $http, $q, $modal, $log, dictionaryService, responseHandler) {

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

    dictionaryService.getOrganizations().then(function(organizations) {
        $scope.organizations = organizations;
    }, function(reason) {
        responseHandler.error(reason);
    });

}]);


app.controller('createOrganizationController', ['$scope', '$http', '$modalInstance', '$log', 'dictionaryService', 'responseHandler', 'params', function($scope, $http, $modalInstance, $log, dictionaryService, responseHandler, params) {

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

app.controller('editOrganizationController', ['$scope', '$http', '$modalInstance', '$log', 'dictionaryService', 'responseHandler', 'params', function($scope, $http, $modalInstance, $log, dictionaryService, responseHandler, params) {

    $scope.organization = {};

    $scope.searchQuery = '';

    $scope.users = [];
    $scope.suggestedUsers = [];

    var addedUsers = [];
    var removedUsers = [];

    $scope.ok = function() {

        var orgObj = {
            'organization_id': params.organization.organization_id,
            'name': $scope.organization.name,
            'about': $scope.organization.about,
            'add_users': addedUsers.map(function(u) { return u.id }),
            'delete_users': removedUsers.map(function(u) { return u.id })
        };

        dictionaryService.editOrganization(orgObj).then(function(data) {
            $modalInstance.close();
        }, function(reason) {
            $modalInstance.close();
        });

    };


    $scope.add = function(user) {

        var m = $scope.organization.users.filter(function(u) {
            return u.id === user.id;
        });

        if (m.length > 0) {
            return;
        }

        var cuser = cloneObject(user);
        cuser['added'] = true;
        $scope.organization.users.push(cuser);
        addedUsers.push(user);
    };

    $scope.remove = function(user) {
        removedUsers.push(user);
        addedUsers = addedUsers.filter(function(obj) {
            return obj.id !== user.id;
        });

        $scope.organization.users = $scope.organization.users.filter(function(obj) {
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
        $scope.organization = data;
    }, function(reason) {

    });

}]);

app.run(function ($rootScope) {
    $rootScope.setLocale = function(locale_id) {
        setCookie("locale_id", locale_id);
    };
});