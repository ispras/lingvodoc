'use strict';

angular.module('HomeModule', ['ui.bootstrap'], function($rootScopeProvider) {
    $rootScopeProvider.digestTtl(1000);
})
    .factory('dictionaryService', ['$http', '$q', lingvodocAPI])

    .factory('responseHandler', ['$timeout', '$modal', responseHandler])

    .directive('translatable', ['dictionaryService', getTranslation])

    .controller('HomeController', ['$scope', '$http', '$log', 'dictionaryService', 'responseHandler', function($scope, $http, $log, dictionaryService, responseHandler) {

        $scope.languages = [];

        $scope.getPerspectiveLink = function(dictionary, perspective) {
            return '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(perspective.client_id) + '/' + encodeURIComponent(perspective.object_id) + '/view';
        };

        $scope.getPerspectiveAuthors = function(perspective) {
            var meta = JSON.parse(perspective.additional_metadata);
            if (_.has(meta, 'authors') && _.has(meta.authors, 'content') && _.isString(meta.authors.content)) {
                return meta.authors.content;
            }
        };

        var getPublishedPerspectives = function(dictionary) {
            dictionaryService.getDictionaryPerspectives(dictionary).then(function(perspectives) {

                var published = [];
                _.forEach(perspectives, function(perspective) {
                    if (perspective.status.toUpperCase() == 'published'.toUpperCase()) {
                        published.push(perspective);
                    }
                });
                dictionary.perspectives = published;
            }, function() {

            });
        };

        var setPerspectives = function(languages) {
            for (var i = 0; i < languages.length; ++i) {
                var lang = languages[i];
                _.forEach(lang.dicts, function(dict) {
                    getPublishedPerspectives(dict);
                });
                if (_.isArray(lang.contains)) {
                    setPerspectives(lang.contains);
                }
            }
        };

        dictionaryService.getPublishedDictionaries().then(function(languages) {
            $scope.languages = languages;
            setPerspectives($scope.languages);
        }, function(reason) {
            responseHandler.error(reason);
        });
    }])
    .run(function ($rootScope, $window) {
        $rootScope.setLocale = function(locale_id) {
            setCookie("locale_id", locale_id);
            $window.location.reload();
        };
    });




