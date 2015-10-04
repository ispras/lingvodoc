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

        modalInstance.result.then(function(entries) {
            if (angular.isArray(entries)) {
                angular.forEach(entries, function(e) {
                    for (var i = 0; i < $scope.lexicalEntries.length; i++) {
                        if ($scope.lexicalEntries[i].client_id == e.client_id &&
                            $scope.lexicalEntries[i].object_id == e.object_id) {

                            angular.forEach(e.contains, function(value) {
                                var newValue = true;
                                angular.forEach($scope.lexicalEntries[i].contains, function(checkValue) {
                                    if (value.client_id == checkValue.client_id && value.object_id == checkValue.object_id) {
                                        newValue = false;
                                    }
                                });

                                if (newValue) {
                                    $scope.lexicalEntries[i].contains.push(value);
                                }
                            });
                            break;
                        }
                    }
                });
            }

        }, function() {

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
        dictionaryService.setDictionaryStatus(url, 'published');
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






