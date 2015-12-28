angular.module('CorporaModule', ['ui.bootstrap'])

    .factory('dictionaryService', ['$http', '$q', lingvodocAPI])

    .factory('responseHandler', ['$timeout', '$modal', responseHandler])

    .controller('CorporaController', ['$scope', '$http', '$q', '$modal', '$location', '$log', 'dictionaryService', 'responseHandler', function($scope, $http, $q, $modal, $location, $log, dictionaryService, responseHandler) {

        $scope.dictionaries = [];


        $scope.getActionLink = function (dictionary, perspective, action) {
            return '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(perspective.client_id) + '/' + encodeURIComponent(perspective.object_id) + '/' + action;
        };

        $scope.getViewCorporaLink = function (dictionary, perspective) {
            return '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(perspective.client_id) + '/' + encodeURIComponent(perspective.object_id) + '/corpora';
        };

        $scope.getViewAudioCorporaLink = function (dictionary, perspective) {
            return '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(perspective.client_id) + '/' + encodeURIComponent(perspective.object_id) + '/audio_corpora';
        };


        $scope.getCorporaPerspectives = function(dictionary, type) {
            return _.filter(dictionary.perspectives, function(p) {
                var meta = {};
                if (_.isString(p.additional_metadata)) {
                    meta = JSON.parse(p.additional_metadata);
                } else {
                    meta = p.additional_metadata;
                }
                return _.has(meta, type);
            });
        };

        $scope.getCorporaDictionaries = function(dictionaries, type) {
            return _.filter(dictionaries, function(d) {
                return !_.isEmpty($scope.getCorporaPerspectives(d, type));
            });
        };

        dictionaryService.getDictionaries({}).then(function(dictionaries) {

            dictionaryService.getAllPerspectives().then(function(perspectives) {

                var corporaPerspectives = _.filter(perspectives, function(perspective) {
                    if (_.has(perspective, 'additional_metadata')) {

                        var meta = {};
                        if (typeof perspective.additional_metadata == 'string') {
                            meta = JSON.parse(perspective.additional_metadata);
                        } else {
                            meta = perspective.additional_metadata;
                        }

                        return _.has(meta, 'corpora') || _.has(meta, 'audio_corpora');
                    }
                    return false;
                });

                var reqs = _.map(corporaPerspectives, function(p) {
                    return dictionaryService.getPerspectiveDictionaryFieldsNew(p);
                });

                $q.all(reqs).then(function(allFields) {

                    _.forEach(corporaPerspectives, function(p, i) {
                        p.fields = allFields[i];
                    });

                    _.forEach(corporaPerspectives, function(corporaPerspective) {
                        _.forEach(dictionaries, function(d) {
                            if (corporaPerspective.parent_client_id === d.client_id &&
                                corporaPerspective.parent_object_id === d.object_id) {
                                d.perspectives.push(corporaPerspective);
                                $scope.dictionaries.push(d);
                            }
                        });
                    });

                }, function(reason) {
                    responseHandler.error(reason);
                });

            }, function(reason) {
                responseHandler.error(reason);
            });

        }, function(reason) {
            responseHandler.error(reason);
        });

    }]);








