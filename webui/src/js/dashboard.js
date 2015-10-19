'use strict';

var app = angular.module('DashboardModule', ['ui.bootstrap']);

app.service('dictionaryService', lingvodocAPI);

app.controller('DashboardController', ['$scope', '$http', '$q', '$modal', '$log', 'dictionaryService', function ($scope, $http, $q, $modal, $log, dictionaryService) {

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

    $scope.getActionLink = function (dictionary, perspective, action) {
        return '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(perspective.client_id) + '/' + encodeURIComponent(perspective.object_id) + '/' + action;
    };


    $scope.editDictionaryProperties = function(dictionary) {
        var modalInstance = $modal.open({
            animation: true,
            templateUrl: 'editDictionaryPropertiesModal.html',
            controller: 'editDictionaryPropertiesController',
            size: 'lg',
            backdrop: 'static',
            keyboard: false,
            resolve: {
                'params': function() {
                    return {
                        'dictionary': dictionary
                    };
                }
            }
        });
    };


    $scope.editPerspectiveProperties = function(dictionary, perspective) {

        $modal.open({
            animation: true,
            templateUrl: 'editPerspectivePropertiesModal.html',
            controller: 'editPerspectivePropertiesController',
            size: 'lg',
            backdrop: 'static',
            keyboard: false,
            resolve: {
                'params': function() {
                    return {
                        'dictionary': dictionary,
                        'perspective': perspective
                    };
                }
            }
        });
    };

    $scope.editDictionaryRoles = function(dictionary) {

        $modal.open({
            animation: true,
            templateUrl: 'editDictionaryRolesModal.html',
            controller: 'editDictionaryRolesController',
            size: 'lg',
            backdrop: 'static',
            keyboard: false,
            resolve: {
                'params': function() {
                    return {
                        'dictionary': dictionary
                    };
                }
            }
        });
    };


    $scope.follow = function(link) {
        if (!link) {
            alert('Please, select perspective first.');
            return;
        }
        window.location = link;
    };

    $scope.getCompositeKey = function (object) {
        if (object) {
            return object.client_id + '_' + object.object_id;
        }
    };

    $scope.setPerspectiveStatus = function(dictionary, perspective, status) {
        dictionaryService.setPerspectiveStatus(dictionary, perspective, status).then(function(data) {
            perspective.status = status;
        }, function(reason) {
            $log.error(reason);
        });
    };

    $scope.setDictionaryStatus = function(dictionary, status) {
        dictionaryService.setDictionaryStatus(dictionary, status).then(function(data) {
            dictionary.status = status;
        }, function(reason) {
            $log.error(reason);
        });
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
                    $scope.dictionaries[index]['selectedPerspectiveId'] =  -1;
                };
            })(i)).error(function (data, status, headers, config) {
                // error handling
            });
        }
    }).error(function (data, status, headers, config) {
        // error handling
    });
}]);

app.controller('editDictionaryPropertiesController', ['$scope', '$http', '$q', '$modalInstance', '$log', 'dictionaryService', 'params', function ($scope, $http, $q, $modalInstance, $log, dictionaryService, params) {

    $scope.data = {};
    $scope.dictionaryProperties = {};
    $scope.languages = [];

    var getCompositeKey = function (obj, key1, key2) {
        if (obj) {
            return obj[key1] + '_' + obj[key2];
        }
    };

    dictionaryService.getLanguages($('#languagesUrl').data('lingvodoc')).then(function(languages) {

        var langs = [];
        angular.forEach(languages, function(language) {
            language['compositeId'] = getCompositeKey(language, 'client_id', 'object_id');
            langs.push(language);
        });
        $scope.languages = langs;

        var url = '/dictionary/' + encodeURIComponent(params.dictionary.client_id) + '/' + encodeURIComponent(params.dictionary.object_id);
        dictionaryService.getDictionaryProperties(url).then(function(dictionaryProperties) {
            var selectedLanguageCompositeId = getCompositeKey(dictionaryProperties, 'parent_client_id', 'parent_object_id');
            $scope.dictionaryProperties = dictionaryProperties;
            $scope.data.selectedLanguage = selectedLanguageCompositeId;
        }, function(reason) {
            $log.error(reason);
        });
    }, function(reason) {
        $log.error(reason);
    });


    var getSelectedLanguage = function() {
        for (var i = 0; i < $scope.languages.length; i++) {
            var language = $scope.languages[i];
            if ($scope.data.selectedLanguage == getCompositeKey(language, 'client_id', 'object_id')) {
                return language;
            }
        }
    };

    $scope.publish = function() {
        var url = '/dictionary/' + encodeURIComponent(params.dictionary.client_id) + '/' + encodeURIComponent(params.dictionary.object_id) + '/state';
        dictionaryService.setDictionaryStatus(url, 'Published');
    };

    $scope.ok = function() {
        var language = getSelectedLanguage();
        if (language) {
            $scope.dictionaryProperties['parent_client_id'] = language['client_id'];
            $scope.dictionaryProperties['parent_object_id'] = language['object_id'];
        } else {
            $scope.dictionaryProperties['parent_client_id'] = null;
            $scope.dictionaryProperties['parent_object_id'] = null;
        }

        var url = '/dictionary/' + encodeURIComponent(params.dictionary.client_id) + '/' + encodeURIComponent(params.dictionary.object_id);
        dictionaryService.setDictionaryProperties(url, $scope.dictionaryProperties).then(function() {
            $modalInstance.close();
        });
    };

    $scope.cancel = function() {
        $modalInstance.dismiss('cancel');
    };

}]);


app.controller('editPerspectivePropertiesController', ['$scope', '$http', '$q', '$modalInstance', '$log', 'dictionaryService', 'params', function ($scope, $http, $q, $modalInstance, $log, dictionaryService, params) {

    $scope.perspective = {};

    $scope.addField = function () {
        $scope.perspective.fields.push({'entity_type': '', 'data_type': 'text', 'status': 'enabled'});
    };

    $scope.removeField = function(field) {
        $scope.perspective.fields

        for(var i = $scope.perspective.fields.length-1; i >= 0; i--) {
            if($scope.perspective.fields[i].client_id == field.client_id &&
                $scope.perspective.fields[i].object_id == field.object_id) {
                $scope.perspective.fields.splice(i, 1);
            }
        }
    };

    $scope.publish = function() {
        dictionaryService.setPerspectiveStatus(params.dictionary, $scope.perspective, 'Published');
    };

    $scope.ok = function() {
        var url = '/dictionary/' + encodeURIComponent(params.dictionary.client_id) + '/' + encodeURIComponent(params.dictionary.object_id) + '/perspective/' + encodeURIComponent(params.perspective.client_id) + '/' + encodeURIComponent(params.perspective.object_id) + '/fields';
        dictionaryService.setPerspectiveFields(url, exportPerspective($scope.perspective)).then(function(fields) {
            $modalInstance.close();
        }, function(reason) {
            $log.error(reason);
        });
    };

    $scope.cancel = function() {
        $modalInstance.dismiss('cancel');
    };

    var url = '/dictionary/' + params.perspective.parent_client_id + '/' + params.perspective.parent_object_id + '/perspective/' + params.perspective.client_id + '/' + params.perspective.object_id + '/fields';
    dictionaryService.getPerspectiveFields(url).then(function(fields) {
        params.perspective['fields'] = fields;
        $scope.perspective = wrapPerspective(params.perspective);
    }, function(reason) {
        $log.error(reason);
    });
}]);


app.controller('editDictionaryRolesController', ['$scope', '$http', '$q', '$modalInstance', '$log', 'dictionaryService', 'params', function ($scope, $http, $q, $modalInstance, $log, dictionaryService, params) {

    $scope.dictionary = params.dictionary;
    $scope.roles = {};
    $scope.userTable = [];

    $scope.ok = function() {

        var result = { 'roles_users': {} };
        var roles = getRoles();
        angular.forEach(roles, function(role) {
            angular.forEach($scope.userTable, function(u) {
                if (u.roles.indexOf(role) >= 0) {
                    if (typeof result[role] != 'undefined') {
                        result.roles_users[role].push(u.id);
                    } else {
                        result.roles_users[role] = [u.id];
                    }
                }
            });
        });

        dictionaryService.setDictionaryRoles($scope.dictionary, result).then(function() {
            $modalInstance.close();
        }, function(reason) {
            $log.error(reason);
        });
    };

    $scope.cancel = function() {
        $modalInstance.dismiss('cancel');
    };

    $scope.userHasRole = function(user, role) {

        var result = false;
        angular.forEach($scope.userTable, function(u) {
            if (u.equals(user)) {
                if (u.roles.indexOf(role) >= 0) {
                    result = true;
                }
            }
        });
        return result;
    };


    var updateSelected = function(action, user, role) {
        if (action === 'add' && user.roles.indexOf(role) === -1) {
            user.roles.push(role);
        }
        if (action === 'remove' && user.roles.indexOf(role) !== -1) {
            user.roles.splice(user.roles.indexOf(role), 1);
        }
    };

    $scope.toggleRole = function($event, user, role) {
        var checkbox = $event.target;
        var action = (checkbox.checked ? 'add' : 'remove');
        updateSelected(action, user, role);
    };


    var getRoles = function() {
        var roles = [];
        angular.forEach($scope.userTable, function(u) {
            angular.forEach(u.roles, function(role) {
                if (roles.indexOf(role) < 0) {
                    roles.push(role);
                }
            });
        });
        return roles;
    };


    var createUsersTable = function(roles) {

        var usersTable = [];
        angular.forEach(roles, function(users, role) {

            angular.forEach(users, function(user) {

                var m = usersTable.filter(function(u) {
                    return u.id == user.id;
                });

                if (m.length > 0) {
                    m[0].roles.push(role);
                } else {
                    user.roles = [role];
                    usersTable.push(user);
                }
            });
        });

        return usersTable;
    };

    dictionaryService.getDictionaryRoles($scope.dictionary).then(function(roles) {
        $scope.roles = roles;
        $scope.userTable = createUsersTable(roles);
        $log.info($scope.userTable);
    });
}]);




















