angular.module('ViewDictionaryModule', ['ui.bootstrap'])

    .service('dictionaryService', lingvodocAPI)

    .factory('responseHandler', ['$timeout', '$modal', responseHandler])

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

    .directive('onReadFile', function($parse) {
        return {
            restrict: 'A',
            scope: false,
            link: function(scope, element, attrs) {
                var fn = $parse(attrs.onReadFile);

                element.on('change', function(onChangeEvent) {
                    var reader = new FileReader();
                    var file = (onChangeEvent.srcElement || onChangeEvent.target).files[0];

                    reader.onload = function(onLoadEvent) {
                        scope.$apply(function() {
                            var b64file = btoa(onLoadEvent.target.result);
                            fn(scope, {
                                $fileName: file.name,
                                $fileType: file.type,
                                $fileContent: b64file
                            });
                        });
                    };
                    reader.readAsBinaryString(file);
                });
            }
        };
    })

    .controller('ViewDictionaryController', ['$scope', '$window', '$http', '$modal', '$log', 'dictionaryService', 'responseHandler', function($scope, $window, $http, $modal, $log, dictionaryService, responseHandler) {


        var dictionaryClientId = $('#dictionaryClientId').data('lingvodoc');
        var dictionaryObjectId = $('#dictionaryObjectId').data('lingvodoc');
        var perspectiveClientId = $('#perspectiveClientId').data('lingvodoc');
        var perspectiveId = $('#perspectiveId').data('lingvodoc');

        WaveSurferController.call(this, $scope);

        $scope.perspectiveFields = [];
        $scope.lexicalEntries = [];

        $scope.fields = [];
        $scope.dictionaryTable = [];

        // pagination
        $scope.pageIndex = 1;
        $scope.pageSize = 20;
        $scope.pageCount = 1;

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

        $scope.getPage = function(pageNumber) {
            if (pageNumber > 0 && pageNumber <= $scope.pageCount) {
                $scope.pageIndex = pageNumber;
                dictionaryService.getLexicalEntries($('#allPublishedEntriesUrl').data('lingvodoc'), (pageNumber - 1) * $scope.pageSize, $scope.pageSize).then(function(lexicalEntries) {
                    $scope.lexicalEntries = lexicalEntries;
                }, function(reason) {
                    responseHandler.error(reason);
                });
            }
        };

        $scope.range = function(min, max, step) {
            step = step || 1;
            var input = [];
            for (var i = min; i <= max; i += step) {
                input.push(i);
            }
            return input;
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

        $scope.annotate = function(soundEntity, markupEntity) {

            var modalInstance = $modal.open({
                animation: true,
                templateUrl: 'annotationModal.html',
                controller: 'AnnotationController',
                size: 'lg',
                resolve: {
                    soundUrl: function() {
                        return soundEntity.content;
                    },
                    annotationUrl: function() {
                        return markupEntity.content;
                    }
                }
            });
        };


        $scope.$watch('lexicalEntries', function(updatedEntries) {

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

        dictionaryService.getPerspectiveDictionaryFields($('#getPerspectiveFieldsUrl').data('lingvodoc')).then(function(fields) {

            $scope.fields = fields;
            dictionaryService.getLexicalEntries($('#allPublishedEntriesUrl').data('lingvodoc'), ($scope.pageIndex - 1) * $scope.pageSize, $scope.pageSize).then(function(lexicalEntries) {
                $scope.lexicalEntries = lexicalEntries;
            }, function(reason) {
                responseHandler.error(reason);
            });

        }, function(reason) {
            responseHandler.error(reason);
        });

        dictionaryService.getLexicalEntriesCount($('#allPublishedEntriesCountUrl').data('lingvodoc')).then(function(totalEntriesCount) {
            $scope.pageCount = Math.ceil(totalEntriesCount / $scope.pageSize);
        }, function(reason) {
            responseHandler.error(reason);
        });


        dictionaryService.getPerspectiveOriginById(perspectiveClientId, perspectiveId).then(function(path) {
            $scope.path = path;
        }, function(reason) {
            responseHandler.error(reason);
        });
    }])


    .controller('AnnotationController', ['$scope', '$http', 'soundUrl', 'annotationUrl', 'responseHandler', function($scope, $http, soundUrl, annotationUrl, responseHandler) {

        var activeUrl = null;

        var createRegions = function(annotaion) {
            if (annotaion instanceof elan.Document) {
                annotaion.tiers.forEach(function(tier) {

                    tier.annotations.forEach(function(a) {

                        var offset1 = annotaion.timeSlotRefToSeconds(a.timeslotRef1);
                        var offset2 = annotaion.timeSlotRefToSeconds(a.timeslotRef2);

                        var r = $scope.wavesurfer.addRegion({
                            id: a.id,
                            start: offset1,
                            end: offset2,
                            color: 'rgba(0, 255, 0, 0.1)'
                        });
                    });
                });
            }
        };

        var loadAnnotation = function(url) {
            // load annotation
            $http.get(url).success(function(data, status, headers, config) {

                try {
                    var xml = (new DOMParser()).parseFromString(data, 'application/xml');
                    var annotation = new elan.Document();
                    annotation.importXML(xml);
                    $scope.annotation = annotation;

                    createRegions(annotation);

                } catch (e) {
                    responseHandler.error('Failed to parse ELAN annotation: ' + e);
                }

            }).error(function(data, status, headers, config) {
                responseHandler.error(data);
            });
        };

        $scope.paused = true;
        $scope.annotation = null;

        $scope.playPause = function() {
            if ($scope.wavesurfer) {
                $scope.wavesurfer.playPause();
            }
        };

        $scope.playAnnotation = function(a) {
            if ($scope.wavesurfer && $scope.annotation) {
                var offset1 = $scope.annotation.timeSlotRefToSeconds(a.timeslotRef1);
                var offset2 = $scope.annotation.timeSlotRefToSeconds(a.timeslotRef2);
                $scope.wavesurfer.play(offset1, offset2);
            }
        };

        $scope.selectRegion = function() {

        };

        // signal handlers
        $scope.$on('wavesurferInit', function(e, wavesurfer) {

            $scope.wavesurfer = wavesurfer;


            if ($scope.wavesurfer.enableDragSelection) {
                $scope.wavesurfer.enableDragSelection({
                    color: 'rgba(0, 255, 0, 0.1)'
                });
            }

            $scope.wavesurfer.on('play', function() {
                $scope.paused = false;
            });

            $scope.wavesurfer.on('pause', function() {
                $scope.paused = true;
            });

            $scope.wavesurfer.on('finish', function() {
                $scope.paused = true;
                $scope.wavesurfer.seekTo(0);
                $scope.$apply();
            });

            // regions events
            $scope.wavesurfer.on('region-click', function(region, event) {

            });

            $scope.wavesurfer.on('region-dblclick', function(region, event) {
                region.remove(region);
            });


            $scope.wavesurfer.once('ready', function() {
                // load annotation once file is loaded
                loadAnnotation(annotationUrl);
                $scope.$apply();
            });

            // load file once wavesurfer is ready
            $scope.wavesurfer.load(soundUrl);
        });

        $scope.$on('modal.closing', function(e) {
            $scope.wavesurfer.stop();
            $scope.wavesurfer.destroy();
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

    }]);
