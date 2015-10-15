'use strict';

angular.module('HomeModule', ['ui.bootstrap'], function($rootScopeProvider) {
    $rootScopeProvider.digestTtl(1000);
})
    .service('dictionaryService', lingvodocAPI)

    .controller('HomeController', ['$scope', '$http', '$modal', '$q', '$log', 'dictionaryService', function($scope, $http, $modal, $q, $log, dictionaryService) {

    var languagesUrl = $('#languagesUrl').data('lingvodoc');
    var dictionariesUrl = $('#dictionariesUrl').data('lingvodoc');
    var getUserInfoUrl = $('#getUserInfoUrl').data('lingvodoc');

    $scope.languages = [];

    $scope.getPerspectiveLink = function (dictionary, perspective) {
        return '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(perspective.client_id) + '/' + encodeURIComponent(perspective.object_id) + '/view';
    };

    var getPublishedPerspectives = function(dictionary) {
        dictionaryService.getDictionaryPerspectives(dictionary).then(function(perspectives) {

            var published = [];
            angular.forEach(perspectives, function(perspective) {
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
            angular.forEach(lang.dicts, function(dict) {
                getPublishedPerspectives(dict);
            });
            if (angular.isArray(lang.contains)) {
                setPerspectives(lang.contains);
            }
        }
    };

    dictionaryService.getPublishedDictionaries().then(function(languages) {
        $scope.languages = languages;
        setPerspectives($scope.languages);




    });

}]);




