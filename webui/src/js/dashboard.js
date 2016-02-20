'use strict';

var app = angular.module('DashboardModule', ['ui.bootstrap', 'ngMap']);

app.service('dictionaryService', lingvodocAPI);

app.factory('responseHandler', ['$timeout', '$modal', responseHandler]);

app.directive('translatable', ['dictionaryService', getTranslation]);

app.controller('DashboardController', ['$scope', '$http', '$q', '$modal', '$log', 'dictionaryService', 'responseHandler', function ($scope, $http, $q, $modal, $log, dictionaryService, responseHandler) {

    var userId = $('#userId').data('lingvodoc');
    var languagesUrl = $('#languagesUrl').data('lingvodoc');

    $scope.dictionaries = [];

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

    $scope.createPerspective = function(dictionary) {

        var modalInstance = $modal.open({
            animation: true,
            templateUrl: 'createPerspectiveModal.html',
            controller: 'createPerspectiveController',
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

        modalInstance.result.then(function(createdPerspective) {
            dictionary.perspectives.push(createdPerspective);
        }, function() {

        });
    };


    $scope.editDictionaryRoles = function(dictionary) {

        $modal.open({
            animation: true,
            templateUrl: 'editRolesModal.html',
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

    $scope.editPerspectiveRoles = function(dictionary, perspective) {

        $modal.open({
            animation: true,
            templateUrl: 'editRolesModal.html',
            controller: 'editPerspectiveRolesController',
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

    $scope.setPerspectiveStatus = function(dictionary, perspective, status) {
        dictionaryService.setPerspectiveStatus(dictionary, perspective, status).then(function(data) {
            perspective.status = status;
        }, function(reason) {
            responseHandler.error(reason);
        });
    };

    $scope.setDictionaryStatus = function(dictionary, status) {
        dictionaryService.setDictionaryStatus(dictionary, status).then(function(data) {
            dictionary.status = status;
        }, function(reason) {
            responseHandler.error(reason);
        });
    };


    $scope.removeDictionary = function(dictionary) {
        responseHandler.yesno('', 'Do you really want to remove dictionary?', function(confirmed) {
            if (confirmed) {
                dictionaryService.removeDictionary(dictionary).then(function() {
                    _.remove($scope.dictionaries, function(d) {
                        return d.equals(dictionary);
                    });
                }, function(reason) {
                    responseHandler.error(reason);
                });
            }
        });
    };

    $scope.removePerspective = function(dictionary, perspective) {
        responseHandler.yesno('', 'Do you really want to remove perspective?', function(confirmed) {
            if (confirmed) {
                dictionaryService.removePerspective(perspective).then(function() {
                    _.remove(dictionary.perspectives, function(p) {
                        return p.equals(perspective);
                    });
                }, function(reason) {
                    responseHandler.error(reason);
                });
            }
        });
    };

    $scope.loadMyDictionaries = function() {

        var dictionaryQuery = {
            'user_created': [userId]
        };

        dictionaryService.getDictionariesWithPerspectives(dictionaryQuery).then(function(dictionaries) {
            $scope.dictionaries = dictionaries;
        }, function(reason) {
            responseHandler.error(reason);
        });
    };

    $scope.loadAvailableDictionaries = function() {

        var dictionaryQuery = {
            'author': userId
        };

        dictionaryService.getDictionariesWithPerspectives(dictionaryQuery).then(function(dictionaries) {
            $scope.dictionaries = dictionaries;
        }, function(reason) {
            responseHandler.error(reason);
        });
    };

    var dictionaryQuery = {
        'author': userId
    };

    dictionaryService.getDictionariesWithPerspectives(dictionaryQuery).then(function(dictionaries) {
        $scope.dictionaries = dictionaries;
    }, function(reason) {
        responseHandler.error(reason);
    });
}]);



app.controller('createPerspectiveController', ['$scope', '$http', '$q', '$modalInstance', '$log', 'dictionaryService', 'responseHandler', 'params', function ($scope, $http, $q, $modalInstance, $log, dictionaryService, responseHandler, params) {

    $scope.dictionary = params.dictionary;
    $scope.perspectives = [];
    $scope.perspective = { 'fields': [] };
    $scope.isTemplate = false;

    $scope.controls = {
        'ok': true,
        'cancel': true
    };


    $scope.addField = function () {
        $scope.perspective.fields.push({'entity_type': '', 'entity_type_translation': '', 'data_type': 'text', 'data_type_translation': 'text', 'status': 'enabled'});
    };

    $scope.enableGroup = function (fieldIndex) {
        if (typeof $scope.perspective.fields[fieldIndex].group === 'undefined') {
            $scope.perspective.fields[fieldIndex].group = '';
        } else {
            delete $scope.perspective.fields[fieldIndex].group;
        }
    };

    $scope.enableLinkedField = function (fieldIndex) {
        if (typeof $scope.perspective.fields[fieldIndex].contains === 'undefined') {
            $scope.perspective.fields[fieldIndex].contains = [{
                'entity_type': '',
                'entity_type_translation': '',
                'data_type': 'markup',
                'data_type_translation': 'markup',
                'status': 'enabled'
            }];
        } else {
            delete $scope.perspective.fields[fieldIndex].contains;
        }
    };

    $scope.ok = function() {

        if (!$scope.perspectiveName) {
            return;
        }

        var perspectiveObj = {
            'translation_string': $scope.perspectiveName,
            'translation': $scope.perspectiveName,
            'is_template': $scope.isTemplate
        };

        enableControls($scope.controls, false);
        var fields = exportPerspective($scope.perspective);
        dictionaryService.createPerspective($scope.dictionary, perspectiveObj, fields).then(function(perspective) {
            enableControls($scope.controls, true);
            $modalInstance.close(perspective);
        }, function(reason) {
            enableControls($scope.controls, true);
            responseHandler.error(reason);
        });
    };

    $scope.cancel = function() {
        $modalInstance.dismiss('cancel');
    };

    $scope.$watch('perspectiveId', function (id) {
        if (typeof id == 'string') {
            for (var i = 0; i < $scope.perspectives.length; i++) {
                if ($scope.perspectives[i].getId() == id) {
                    $scope.perspective = $scope.perspectives[i];

                    dictionaryService.getPerspectiveFieldsNew($scope.perspective).then(function(fields) {
                        $scope.perspective.fields = fields;
                    }, function(reason) {
                        responseHandler.error(reason);
                    });
                    break;
                }
            }
        }
    });

    dictionaryService.getAllPerspectives().then(function(perspectives) {
        $scope.perspectives = perspectives;
    }, function(reason) {
        responseHandler.error(reason);
    });
}]);

app.controller('editDictionaryPropertiesController', ['$scope', '$http', '$q', '$modalInstance', '$log', 'dictionaryService', 'responseHandler', 'params', function ($scope, $http, $q, $modalInstance, $log, dictionaryService, responseHandler, params) {

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

        //var url = '/dictionary/' + encodeURIComponent(params.dictionary.client_id) + '/' + encodeURIComponent(params.dictionary.object_id);
        dictionaryService.getDictionaryProperties(params.dictionary).then(function(dictionaryProperties) {
            var selectedLanguageCompositeId = getCompositeKey(dictionaryProperties, 'parent_client_id', 'parent_object_id');
            $scope.dictionaryProperties = dictionaryProperties;
            $scope.data.selectedLanguage = selectedLanguageCompositeId;
        }, function(reason) {
            responseHandler.error(reason);
        });
    }, function(reason) {
        responseHandler.error(reason);
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

        //var url = '/dictionary/' + encodeURIComponent(params.dictionary.client_id) + '/' + encodeURIComponent(params.dictionary.object_id);
        dictionaryService.setDictionaryProperties(params.dictionary, $scope.dictionaryProperties).then(function() {
            $modalInstance.close();
        });
    };

    $scope.cancel = function() {
        $modalInstance.dismiss('cancel');
    };

}]);


app.controller('editPerspectivePropertiesController', ['$scope', '$http', '$q', '$modal', '$modalInstance', '$log', 'dictionaryService', 'responseHandler', 'params', function ($scope, $http, $q, $modal, $modalInstance, $log, dictionaryService, responseHandler, params) {

    $scope.dictionary = params.dictionary;
    $scope.perspective = {};
    $scope.blobs = [];
    $scope.blobId = '';

    $scope.controls = {
        'ok': true,
        'cancel': true
    };

    $scope.authors = '';

    $scope.addField = function () {
        $scope.perspective.fields.push({'entity_type': '', 'data_type': 'text', 'status': 'enabled'});
    };

    $scope.removeField = function(field) {

        for(var i = $scope.perspective.fields.length-1; i >= 0; i--) {
            if($scope.perspective.fields[i].client_id == field.client_id &&
                $scope.perspective.fields[i].object_id == field.object_id) {
                $scope.perspective.fields.splice(i, 1);
            }
        }
    };

    $scope.editGeoLabels = function() {

        $modal.open({
            animation: true,
            templateUrl: 'perspectiveGeoLabelsModal.html',
            controller: 'perspectiveGeoLabelsController',
            size: 'lg',
            backdrop: 'static',
            keyboard: false,
            resolve: {
                'params': function() {
                    return {
                        'dictionary': params.dictionary,
                        'perspective': params.perspective
                    };
                }
            }
        });
    };

    $scope.addBlob = function() {

        var b1 = _.find($scope.perspective.blobs, function(b) { return b.getId() == $scope.blobId; });
        $log.info(b1);
        if (!!b1) {
            return;
        }

        var blob = _.find($scope.blobs, function(b) {
            return b.getId() == $scope.blobId;
        });

        if (blob) {
            // already existing blobs
            var blobs = $scope.perspective.blobs.map(function(b) {
                return {
                    'info': {
                        'type': 'blob',
                        'content': {
                            'client_id': b.client_id,
                            'object_id': b.object_id
                        }
                    }
                }
            });

            // add new blob
            blobs.push({
                'info': {
                    'type': 'blob',
                    'content': {
                        'client_id': blob.client_id,
                        'object_id': blob.object_id
                    }
                }
            });

            var meta = {
                'info': {
                    'type': 'list',
                    'content': blobs
                }
            };

            dictionaryService.setPerspectiveMeta(params.dictionary, params.perspective, meta).then(function(response) {
                $scope.perspective.blobs.push(blob);
            }, function(reason) {
                responseHandler.error(reason);
            });
        }
    };

    $scope.removeBlob = function(blob) {

        var blobs = _.filter($scope.perspective.blobs, function(b) {
            return !b.equals(blob);
        });

        var blobsMeta = blobs.map(function(b) {
            return {
                'info': {
                    'type': 'blob',
                    'content': {
                        'client_id': b.client_id,
                        'object_id': b.object_id
                    }
                }
            }
        });

        var meta = {
            'info': {
                'type': 'list',
                'content': blobsMeta
            }
        };

        dictionaryService.setPerspectiveMeta(params.dictionary, params.perspective, meta).then(function(response) {
            _.remove($scope.perspective.blobs, function(b) {
                return b.equals(blob);
            });
        }, function(reason) {
            responseHandler.error(reason);
        });

    };

    $scope.ok = function() {
        enableControls($scope.controls, false);

        var meta = {
            'authors': {
                'type': 'authors',
                'content': $scope.authors
            }
        };

        dictionaryService.setPerspectiveMeta($scope.dictionary, $scope.perspective, meta).then(function(response) {
            dictionaryService.setPerspectiveProperties($scope.dictionary, $scope.perspective).then(function(data) {
                var url = '/dictionary/' + encodeURIComponent(params.dictionary.client_id) + '/' + encodeURIComponent(params.dictionary.object_id) + '/perspective/' + encodeURIComponent(params.perspective.client_id) + '/' + encodeURIComponent(params.perspective.object_id) + '/fields';
                dictionaryService.setPerspectiveFields(url, exportPerspective($scope.perspective)).then(function(fields) {
                    enableControls($scope.controls, true);
                    $modalInstance.close();
                }, function(reason) {
                    enableControls($scope.controls, true);
                    responseHandler.error(reason);
                });
            }, function(reason) {
                enableControls($scope.controls, true);
                responseHandler.error(reason);
            });
        }, function(reason) {
            enableControls($scope.controls, true);
            responseHandler.error(reason);
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
        responseHandler.error(reason);
    });

    dictionaryService.getUserBlobs().then(function(blobs) {
        $scope.blobs = blobs.filter(function(b) {
            return b.data_type != 'dialeqt_dictionary';
        });

    }, function(reason) {
        responseHandler.error(reason);
    });

    dictionaryService.getPerspectiveMeta(params.dictionary, params.perspective).then(function(meta) {

        if (_.has(meta, 'authors') && _.has(meta.authors, 'content') && _.isString(meta.authors.content)) {
            $scope.authors = meta.authors.content;
        }

    }, function(reason) {
        responseHandler.error(reason);
    });
}]);


app.controller('editDictionaryRolesController', ['$scope', '$http', '$q', '$modalInstance', '$log', 'dictionaryService', 'responseHandler', 'params', function ($scope, $http, $q, $modalInstance, $log, dictionaryService, responseHandler, params) {

    $scope.dictionary = params.dictionary;
    $scope.roles = {};
    $scope.userTable = [];

    $scope.ok = function() {
        var result = { 'roles_users': {} };
        var addRoles = { 'roles_users': {} };
        var deleteRoles = { 'roles_users': {} };
        var roles = getRoles();

        angular.forEach(roles, function(role) {
            result.roles_users[role] = [];
            angular.forEach($scope.userTable, function(u) {
                if (u.roles.indexOf(role) >= 0) {
                    result.roles_users[role].push(u);
                }
            });
        });

        angular.forEach(result.roles_users, function(v, role) {

            var newUsers = result.roles_users[role].map(function(u) {
                return u.id;
            });

            var oldUsers = $scope.roles[role].map(function(u) {
                return u.id;
            });

            addRoles.roles_users[role] = [];
            angular.forEach(newUsers, function(id) {
                if (oldUsers.indexOf(id) < 0) {
                    addRoles.roles_users[role].push(id);
                }
            });

            deleteRoles.roles_users[role] = [];
            angular.forEach(oldUsers, function(id) {
                if (newUsers.indexOf(id) < 0) {
                    deleteRoles.roles_users[role].push(id);
                }
            });
        });

        var promises = [];
        if (Object.keys(addRoles.roles_users).length > 0) {
            promises.push(dictionaryService.addDictionaryRoles($scope.dictionary, addRoles));
        }

        if (Object.keys(deleteRoles.roles_users).length > 0) {
            promises.push(dictionaryService.deleteDictionaryRoles($scope.dictionary, deleteRoles));
        }

        $q.all(promises).then(function() {
            $modalInstance.close();
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

    $scope.addUser = function(user) {

        user['roles'] = [];
        var m = $scope.userTable.filter(function(u) {
            return u.id == user.id;
        });
        if (m.length == 0) {
            $scope.userTable.push(user);
        }
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
        return Object.keys($scope.roles);
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

    $scope.$watch('searchQuery', function(query) {
        if (query && query.length >= 3) {
            $scope.suggestedUsers = [];
            dictionaryService.searchUsers(query).then(function(users) {
                $scope.suggestedUsers = users.map(function(u) {
                    return lingvodoc.User.fromJS(u);
                });
            }, function(reason) {

            });
        }
    });

    dictionaryService.getDictionaryRoles($scope.dictionary).then(function(roles) {
        $scope.roles = roles;
        $scope.userTable = createUsersTable(roles);
    }, function(reason) {
        responseHandler.error(reason);
    });
}]);


app.controller('editPerspectiveRolesController', ['$scope', '$http', '$q', '$modalInstance', '$log', 'dictionaryService', 'responseHandler', 'params', function ($scope, $http, $q, $modalInstance, $log, dictionaryService, responseHandler, params) {

    $scope.roles = {};
    $scope.userTable = [];
    $scope.searchQuery = '';
    $scope.suggestedUsers = [];

    $scope.ok = function() {
        var result = { 'roles_users': {} };
        var addRoles = { 'roles_users': {} };
        var deleteRoles = { 'roles_users': {} };
        var roles = getRoles();

        angular.forEach(roles, function(role) {
            result.roles_users[role] = [];
            angular.forEach($scope.userTable, function(u) {
                if (u.roles.indexOf(role) >= 0) {
                    result.roles_users[role].push(u);
                }
            });
        });

        angular.forEach(result.roles_users, function(v, role) {

            var newUsers = result.roles_users[role].map(function(u) {
                return u.id;
            });

            var oldUsers = $scope.roles[role].map(function(u) {
                return u.id;
            });

            addRoles.roles_users[role] = [];
            angular.forEach(newUsers, function(id) {
                if (oldUsers.indexOf(id) < 0) {
                    addRoles.roles_users[role].push(id);
                }
            });

            deleteRoles.roles_users[role] = [];
            angular.forEach(oldUsers, function(id) {
                if (newUsers.indexOf(id) < 0) {
                    deleteRoles.roles_users[role].push(id);
                }
            });
        });

        var promises = [];
        if (Object.keys(addRoles.roles_users).length > 0) {
            promises.push(dictionaryService.addPerspectiveRoles(params.dictionary, params.perspective, addRoles));
        }

        if (Object.keys(deleteRoles.roles_users).length > 0) {
            promises.push(dictionaryService.deletePerspectiveRoles(params.dictionary, params.perspective, deleteRoles));
        }

        $q.all(promises).then(function() {
            $modalInstance.close();
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

    $scope.addUser = function(user) {

        user['roles'] = [];
        var m = $scope.userTable.filter(function(u) {
            return u.id == user.id;
        });
        if (m.length == 0) {
            $scope.userTable.push(user);
        }
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

    $scope.$watch('searchQuery', function(query) {
        if (query.length >= 3) {
            $scope.suggestedUsers = [];
            dictionaryService.searchUsers(query).then(function(users) {
                $scope.suggestedUsers = users.map(function(u) {
                    return lingvodoc.User.fromJS(u);
                });
            }, function(reason) {

            });
        }
    });

    dictionaryService.getPerspectiveRoles(params.dictionary, params.perspective).then(function(roles) {
        $scope.roles = roles;
        $scope.userTable = createUsersTable(roles);
    }, function(reason) {
        responseHandler.error(reason);
    });
}]);

app.controller('perspectiveGeoLabelsController', ['$scope', '$http', '$q', '$modalInstance', '$log', 'NgMap', 'dictionaryService', 'responseHandler', 'params', function ($scope, $http, $q, $modalInstance, $log, NgMap, dictionaryService, responseHandler, params) {

    var key = 'AIzaSyB6l1ciVMcP1pIUkqvSx8vmuRJL14lbPXk';
    $scope.googleMapsUrl = 'http://maps.google.com/maps/api/js?v=3.20&key=' + encodeURIComponent(key);
    $scope.positions = [];

    // resize map to match parent modal's size
    $modalInstance.opened.then(function() {
        NgMap.getMap().then(function(map) {
            google.maps.event.trigger(map, 'resize');
        });
    });

    $scope.addMarker = function(event) {
        if ($scope.positions.length > 0) {
            return;
        }
        var latLng = event.latLng;

        var meta = {
            'location': {
                'type': 'location',
                'content': {
                    'lat': latLng.lat(),
                    'lng': latLng.lng()
                }
            }
        };

        dictionaryService.setPerspectiveMeta(params.dictionary, params.perspective, meta).then(function(response) {
            $scope.positions.push({'lat': latLng.lat(), 'lng': latLng.lng()});
        }, function(reason) {
            responseHandler.error(reason);
        });
    };

    $scope.removeMarker = function(marker) {

        var meta = {
            'location': {
                'type': 'location',
                'content': {
                    'lat': marker.latLng.lat(),
                    'lng': marker.latLng.lng()
                }
            }
        };

        dictionaryService.removePerspectiveMeta(params.dictionary, params.perspective, meta).then(function(response) {
            _.remove($scope.positions, function(e) {
                var p = new google.maps.LatLng(e.lat, e.lng);
                return p.equals(marker.latLng);
            });
        }, function(reason) {
            responseHandler.error(reason);
        });
    };

    $scope.ok = function() {
        $modalInstance.close();
    };

    dictionaryService.getPerspectiveMeta(params.dictionary, params.perspective).then(function(data) {
        $scope.positions = [];
        if (!_.isEmpty(data) && _.has(data, 'location')) {
            $scope.positions.push(data.location.content);
        }
    });

}]);
