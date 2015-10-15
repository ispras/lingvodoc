'use strict';

angular.module('HomeModule', ['ui.bootstrap'], function($rootScopeProvider) {
    $rootScopeProvider.digestTtl(1000);
})
    .service('dictionaryService', lingvodocAPI)

    .controller('HomeController', ['$scope', '$http', '$modal', '$q', '$log', 'dictionaryService', function($scope, $http, $modal, $q, $log, dictionaryService) {

    var languagesUrl = $('#languagesUrl').data('lingvodoc');
    var dictionariesUrl = $('#dictionariesUrl').data('lingvodoc');
    var getUserInfoUrl = $('#getUserInfoUrl').data('lingvodoc');


    var dictionaryQuery = {
        'published': true
    };

    $scope.languages = [];
    $scope.dictionaries = [];
    $scope.groupDictionaries = [];
    $scope.count = 0;


    var flatLanguages = function (languages) {
        var flat = [];
        for (var i = 0; i < languages.length; i++) {
            var language = languages[i];
            flat.push(languages[i]);
            if (language.contains && language.contains.length > 0) {
                var childLangs = flatLanguages(language.contains);
                flat = flat.concat(childLangs);
            }
        }
        return flat;
    };

    var getLanguage = function(client_id, object_id) {
        for (var i = 0; i < $scope.languages.length; i++) {
            if ($scope.languages[i].client_id == client_id && $scope.languages[i].object_id == object_id) {
                return $scope.languages[i];
            }
        }
    };

    var createGroupDictionaries = function(languages, dictionaries) {

        var group = [];
        for (var i = 0; i < dictionaries.length; i++) {

            dictionaries[i].links = $scope.getViewDictionaryLinks(dictionaries[i]);

            if (!dictionaries[i].parent_client_id || !dictionaries[i].parent_object_id) {
                continue;
            }

            var language = getLanguage(dictionaries[i].parent_client_id, dictionaries[i].parent_object_id);
            var createNewGroup = true;
            for (var j = 0; j < group.length; j++) {
                if (group[j].client_id == language.client_id && group[j].object_id == language.object_id) {
                    group[j].dicts.push(dictionaries[i]);
                    createNewGroup = false;
                }
            }

            if (createNewGroup) {
                group.push({
                    'client_id': language.client_id,
                    'object_id': language.object_id,
                    'name': language.translation_string,
                    'dicts': [dictionaries[i]]
                });
            }
        }

        return group;
    };


    $scope.getViewDictionaryLinks = function (dictionary) {

        if (!dictionary.perspectives) {
            return [];
        }

        var links = [];
        for (var i = 0; i < dictionary.perspectives.length; i++) {
            var perspective = dictionary.perspectives[i];
            var perspectiveClientId = perspective.client_id;
            var perspectiveObjectId = perspective.object_id;
            links.push({
                'name': perspective.name,
                'link': '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(perspectiveClientId) + '/' + encodeURIComponent(perspectiveObjectId) + '/view'
            });
        }
        return links;
    };

    $http.get(languagesUrl).success(function(data, status, headers, config) {
        $scope.languages = flatLanguages(data.languages);

        $http.post(dictionariesUrl, dictionaryQuery).success(function (data, status, headers, config) {
            var requests = [];
            $scope.dictionaries = data.dictionaries;
            for (var i = 0; i < $scope.dictionaries.length; i++) {
                var dictionary = $scope.dictionaries[i];
                var getPerspectivesUrl = '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspectives';
                var r = $http.get(getPerspectivesUrl);
                requests.push(r);
            }

            $q.all(requests).then(function(results) {
                for (var k = 0; k < results.length; k++) {
                    if (results[k].data) {
                        for (var perspectiveIdx = 0; perspectiveIdx < results[k].data.perspectives.length; perspectiveIdx++) {
                            for (var dictionaryIdx = 0; dictionaryIdx < $scope.dictionaries.length; dictionaryIdx++) {
                                if (results[k].data.perspectives[perspectiveIdx].parent_client_id == $scope.dictionaries[dictionaryIdx].client_id &&
                                    results[k].data.perspectives[perspectiveIdx].parent_object_id == $scope.dictionaries[dictionaryIdx].object_id) {
                                    $scope.dictionaries[dictionaryIdx]['perspectives'] = results[k].data.perspectives;
                                    break;
                                }
                            }
                        }
                    }
                }

                $scope.groupDictionaries = createGroupDictionaries($scope.languages, $scope.dictionaries);

            });

        }).error(function (data, status, headers, config) {
            // error handling
        });
    }).error(function(data, status, headers, config) {
        // error handling
    });



    dictionaryService.getPublishedDictionaries().then(function(results) {
        $log.info(results);
    });

}]);




