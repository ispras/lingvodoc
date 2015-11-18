'use strict';

angular.module('MapsModule', ['ui.bootstrap', 'ngMap'])

    .factory('responseHandler', ['$timeout', '$modal', responseHandler])

    .factory('dictionaryService', ['$http', '$q', lingvodocAPI])

    .directive('wavesurfer', function() {
        return {
            restrict: 'E',

            link: function($scope, $element, $attrs) {
                $element.css('display', 'block');

                var options = angular.extend({container: $element[0]}, $attrs);
                var wavesurfer = WaveSurfer.create(options);

                if ($attrs.url) {
                    wavesurfer.load($attrs.url, $attrs.data || null);
                }

                $scope.$emit('wavesurferInit', wavesurfer);
            }
        };
    })

    .controller('MapsController', ['$scope', '$http', '$log', 'dictionaryService', 'responseHandler', function($scope, $http, $log, dictionaryService, responseHandler) {

        WaveSurferController.call(this, $scope);

        var key = 'AIzaSyB6l1ciVMcP1pIUkqvSx8vmuRJL14lbPXk';
        $scope.googleMapsUrl = 'http://maps.google.com/maps/api/js?v=3.20&key=' + encodeURIComponent(key);

        $scope.perspectives = [];
        $scope.activePerspectives = [];

        $scope.query = '';

        $scope.entries = [];
        $scope.fields = [];

        $scope.fieldsIdx = [];
        $scope.fieldsValues = [];


        $scope.getPerspectivesWithLocation = function() {
            return _.filter($scope.perspectives, function(p) {
                return _.has(p, 'location') && !_.isEmpty(p, 'location') && _.has(p.location, 'lat') && _.has(p.location, 'lng');
            });
        };

        $scope.isPerspectiveActive = function(perspective) {
            return !!_.find($scope.activePerspectives, function(p) {
                return p.equals(perspective);
            });
        };

        $scope.info = function(event, perspective) {
            
        };

        $scope.toggle = function(event, perspective) {
            if (!_.find($scope.activePerspectives, function(p) { return p.equals(perspective); })) {
                $scope.activePerspectives.push(perspective);
            } else {
                _.remove($scope.activePerspectives, function(p) {
                    return p.equals(perspective);
                });
            }
        };

        $scope.$watch('entries', function(updatedEntries) {

            var getFieldValues = function(entry, field) {

                var value;
                var values = [];
                if (entry && entry.contains) {

                    if (field.isGroup) {

                        for (var fieldIndex = 0; fieldIndex < field.contains.length; fieldIndex++) {
                            var subField = field.contains[fieldIndex];

                            for (var valueIndex = 0; valueIndex < entry.contains.length; valueIndex++) {
                                value = entry.contains[valueIndex];
                                if (value.entity_type == subField.entity_type) {
                                    values.push(value);
                                }
                            }
                        }
                    } else {
                        for (var i = 0; i < entry.contains.length; i++) {
                            value = entry.contains[i];
                            if (value.entity_type == field.entity_type) {
                                values.push(value);
                            }
                        }
                    }
                }
                return values;
            };

            var mapFieldValues = function(allEntries, allFields) {
                var result = [];
                for (var i = 0; i < allEntries.length; i++) {
                    var entryRow = [];
                    for (var j = 0; j < allFields.length; j++) {
                        entryRow.push(getFieldValues(allEntries[i], allFields[j]));
                    }
                    result.push(entryRow);
                }
                return result;
            };

            $scope.dictionaryTable = mapFieldValues(updatedEntries, $scope.fields);

        }, true);

        $scope.$watch('query', function(q) {
            if (!q || q.length < 3) {
                return;
            }

            dictionaryService.advancedSearch(q, '', $scope.activePerspectives).then(function(entries) {

                if (!_.isEmpty(entries)) {

                    var p = _.find(_.first(entries)['origin'], function(o) {
                        return o.type == 'perspective';
                    });

                    dictionaryService.getPerspectiveDictionaryFieldsNew(p).then(function(fields) {
                        $scope.fields = fields;
                        $scope.entries = entries;
                    }, function(reason) {
                        responseHandler.error(reason);
                    });

                } else {
                    $scope.fields = [];
                    $scope.entries = [];
                }

            }, function(reason) {
                responseHandler.error(reason);
            });
        }, false);

        dictionaryService.getAllPerspectives().then(function(perspectives) {
            $scope.perspectives = _.clone(perspectives);
            $scope.activePerspectives = _.clone($scope.getPerspectivesWithLocation());
        }, function(reason) {

        });
    }]);



