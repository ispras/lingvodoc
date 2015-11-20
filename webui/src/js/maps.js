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

    .directive('indeterminate', [function() {
        return {
            require: '?ngModel',
            link: function(scope, el, attrs, ctrl) {
                ctrl.$formatters = [];
                ctrl.$parsers = [];
                ctrl.$render = function() {
                    var d = ctrl.$viewValue;
                    el.data('checked', d);
                    switch(d){
                        case true:
                            el.prop('indeterminate', false);
                            el.prop('checked', true);
                            break;
                        case false:
                            el.prop('indeterminate', false);
                            el.prop('checked', false);
                            break;
                        default:
                            el.prop('indeterminate', true);
                    }
                };
                el.bind('click', function() {
                    var d;
                    switch(el.data('checked')){
                        case false:
                            d = true;
                            break;
                        case true:
                            d = null;
                            break;
                        default:
                            d = false;
                    }
                    ctrl.$setViewValue(d);
                    scope.$apply(ctrl.$render);
                });
            }
        };
    }])

    .controller('MapsController', ['$scope', '$http', '$log', '$modal', 'NgMap', 'dictionaryService', 'responseHandler', function($scope, $http, $log, $modal, NgMap, dictionaryService, responseHandler) {

        WaveSurferController.call(this, $scope);

        var key = 'AIzaSyB6l1ciVMcP1pIUkqvSx8vmuRJL14lbPXk';
        $scope.googleMapsUrl = 'http://maps.google.com/maps/api/js?v=3.20&key=' + encodeURIComponent(key);

        $scope.perspectives = [];
        $scope.activePerspectives = [];

        $scope.query = '';
        $scope.searchMode = null;

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
            var self = this;
            $scope.selectedPerspective = perspective;
            NgMap.getMap().then(function(map) {
                map.showInfoWindow('bar', self);
            });
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

        $scope.showBlob = function(blob) {
            $modal.open({
                animation: true,
                templateUrl: 'blobModal.html',
                controller: 'BlobController',
                size: 'lg',
                backdrop: 'static',
                keyboard: false,
                resolve: {
                    'params': function() {
                        return {
                            'blob': blob
                        };
                    }
                }
            }).result.then(function(req) {

                }, function() {

                });
        };

        $scope.viewGroup = function(entry, field, values) {

            $modal.open({
                animation: true,
                templateUrl: 'viewGroupModal.html',
                controller: 'viewGroupController',
                size: 'lg',
                backdrop: 'static',
                keyboard: false,
                resolve: {
                    'groupParams': function() {
                        return {
                            'entry': entry,
                            'field': field,
                            'values': values
                        };
                    }
                }
            });
        };

        $scope.viewGroupingTag = function(entry, field, values) {

            $modal.open({
                animation: true,
                templateUrl: 'viewGroupingTagModal.html',
                controller: 'viewGroupingTagController',
                size: 'lg',
                resolve: {
                    'groupParams': function() {
                        return {
                            'entry': entry,
                            'fields': $scope.fields
                        };
                    }
                }
            });
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

            dictionaryService.advancedSearch(q, 'Translation', $scope.activePerspectives, $scope.searchMode).then(function(entries) {

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
    }])

    .controller('viewGroupController', ['$scope', '$http', '$modalInstance', '$log', 'dictionaryService', 'responseHandler', 'groupParams', function($scope, $http, $modalInstance, $log, dictionaryService, responseHandler, groupParams) {

        var dictionaryClientId = $('#dictionaryClientId').data('lingvodoc');
        var dictionaryObjectId = $('#dictionaryObjectId').data('lingvodoc');
        var perspectiveClientId = $('#perspectiveClientId').data('lingvodoc');
        var perspectiveId = $('#perspectiveId').data('lingvodoc');

        WaveSurferController.call(this, $scope);

        $scope.title = groupParams.field.entity_type;
        $scope.fields = groupParams.field.contains;
        $scope.parentEntry = groupParams.entry;

        var createVirtualEntries = function(values) {
            var virtualEntries = [];

            var addValue = function(value, entries) {

                var createNewEntry = true;
                if (value.additional_metadata) {
                    for (var entryIndex = 0; entryIndex < entries.length; entryIndex++) {
                        var currentEntry = entries[entryIndex];

                        if (entries[entryIndex].client_id == value.client_id &&
                            entries[entryIndex].row_id == value.additional_metadata.row_id) {
                            entries[entryIndex].contains.push(value);
                            return;
                        }
                    }

                    entries.push(
                        {
                            'client_id': $scope.parentEntry.client_id,
                            'object_id': $scope.parentEntry.object_id,
                            'row_id': value.additional_metadata.row_id,
                            'contains': [value]
                        }
                    );
                }
            };

            for (var i = 0; i < values.length; i++) {
                var value = values[i];
                addValue(value, virtualEntries);
            }

            return virtualEntries;
        };

        $scope.entries = createVirtualEntries(groupParams.values);

        $scope.fieldsIdx = [];
        $scope.fieldsValues = [];
        $scope.mapFieldValues = function(allEntries, allFields) {
            $scope.fieldsValues = [];
            $scope.fieldsIdx = [];

            for (var i = 0; i < allEntries.length; i++) {
                var entryRow = [];
                for (var j = 0; j < allFields.length; j++) {
                    entryRow.push($scope.getFieldValues(allEntries[i], allFields[j]));
                }
                $scope.fieldsValues.push(entryRow);
            }

            for (var k = 0; k < allFields.length; k++) {
                $scope.fieldsIdx.push(allFields[k]);
            }
        };

        $scope.getFieldValues = function(entry, field) {

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

        $scope.approve = function(lexicalEntry, field, fieldValue, approved) {

            var url = $('#approveEntityUrl').data('lingvodoc');

            var obj = {
                'type': field.level,
                'client_id': fieldValue.client_id,
                'object_id': fieldValue.object_id
            };

            dictionaryService.approve(url, { 'entities': [obj] }, approved).then(function(data) {
                fieldValue['published'] = approved;
            }, function(reason) {
                responseHandler.error(reason);
            });
        };

        $scope.approved = function(lexicalEntry, field, fieldValue) {

            if (!fieldValue.published) {
                return false;
            }

            return !!fieldValue.published;
        };

        $scope.ok = function() {
            $modalInstance.close($scope.entries);
        };

        $scope.$watch('entries', function(updatedEntries) {
            $scope.mapFieldValues(updatedEntries, $scope.fields);
        }, true);

    }])

    .controller('viewGroupingTagController', ['$scope', '$http', '$modalInstance', '$q', '$log', 'dictionaryService', 'responseHandler', 'groupParams', function($scope, $http, $modalInstance, $q, $log, dictionaryService, responseHandler, groupParams) {

        var dictionaryClientId = $('#dictionaryClientId').data('lingvodoc');
        var dictionaryObjectId = $('#dictionaryObjectId').data('lingvodoc');
        var perspectiveClientId = $('#perspectiveClientId').data('lingvodoc');
        var perspectiveId = $('#perspectiveId').data('lingvodoc');

        WaveSurferController.call(this, $scope);

        $scope.fields = groupParams.fields;
        $scope.connectedEntries = [];
        $scope.suggestedEntries = [];

        $scope.fieldsIdx = [];
        for (var k = 0; k < $scope.fields.length; k++) {
            $scope.fieldsIdx.push($scope.fields[k]);
        }

        $scope.fieldsValues = [];
        $scope.suggestedFieldsValues = [];
        $scope.mapFieldValues = function(allEntries, allFields) {

            var result = [];
            for (var i = 0; i < allEntries.length; i++) {
                var entryRow = [];
                for (var j = 0; j < allFields.length; j++) {
                    entryRow.push($scope.getFieldValues(allEntries[i], allFields[j]));
                }
                result.push(entryRow);
            }
            return result;
        };

        $scope.getFieldValues = function(entry, field) {

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

        $scope.getPerspectiveLink = function(p) {
            return '/dictionary/' + encodeURIComponent(p.parent_client_id) + '/' + encodeURIComponent(p.parent_object_id) + '/perspective/' + encodeURIComponent(p.client_id) + '/' + encodeURIComponent(p.object_id) + '/view';
        };

        $scope.ok = function() {
            $modalInstance.close();
        };

        $scope.$watch('connectedEntries', function(updatedEntries) {
            $scope.fieldsValues = $scope.mapFieldValues(updatedEntries, $scope.fields);
        }, true);

        dictionaryService.getConnectedWords(groupParams.entry.client_id, groupParams.entry.object_id).then(function(entries) {

            var r = entries.map(function(entry) {
                var lexicalEntry = entry.lexical_entry;
                return dictionaryService.getPerspectiveOriginById(lexicalEntry.parent_client_id, lexicalEntry.parent_object_id);
            });

            $q.all(r).then(function(paths) {
                angular.forEach(entries, function(entry, i) {
                    entry.lexical_entry['origin'] = paths[i];
                    $scope.connectedEntries.push(entry.lexical_entry);
                });
            }, function(reason) {
                responseHandler.error(reason);
            });

        }, function(reason) {
            responseHandler.error(reason);
        });

    }])


    .controller('BlobController', ['$scope', '$http', '$log', '$modal', '$modalInstance', 'NgMap', 'dictionaryService', 'responseHandler', 'params', function($scope, $http, $log, $modal, $modalInstance, NgMap, dictionaryService, responseHandler, params) {

        $scope.blob = params.blob;

        $scope.ok = function() {
            $modalInstance.close();
        };


    }]);



