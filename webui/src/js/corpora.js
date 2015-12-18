angular.module('CorporaModule', ['ui.bootstrap'])

    .factory('dictionaryService', ['$http', '$q', lingvodocAPI])

    .factory('responseHandler', ['$timeout', '$modal', responseHandler])

    .controller('CorporaController', ['$scope', '$http', '$q', '$modal', '$location', '$log', 'dictionaryService', 'responseHandler', function($scope, $http, $q, $modal, $location, $log, dictionaryService, responseHandler) {

        $scope.dictionaries = [];


        $scope.getActionLink = function (dictionary, perspective, action) {
            return '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(perspective.client_id) + '/' + encodeURIComponent(perspective.object_id) + '/' + action;
        };

        $scope.getViewCorpusLink = function (dictionary, perspective) {
            return '/dictionary/' + encodeURIComponent(dictionary.client_id) + '/' + encodeURIComponent(dictionary.object_id) + '/perspective/' + encodeURIComponent(perspective.client_id) + '/' + encodeURIComponent(perspective.object_id) + '/corpora';
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

                        return _.has(meta, 'corpora');
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


        //var props = {
        //    'xml_path': '/home/steve/glotext1.xml',
        //    'dictionary_translation_string': 'Name for new dict 2',
        //    'perspective_translation_string': 'name for new persp 2', 'parent_client_id': 1, 'parent_object_id': 1
        //};
        //
        //$http.post('/convert/xml', props).success(function(data, status, headers, config) {
        //
        //}).error(function(data, status, headers, config) {
        //
        //});
    }]);



