angular.module('ViewDictionaryModule', ['ui.bootstrap'])

    .service('dictionaryService', function($http, $q) {

        var addUrlParameter = function(url, key, value) {
            return url + (url.indexOf('?') >= 0 ? '&' : '?') + encodeURIComponent(key) + '=' + encodeURIComponent(value);
        };

        // merges group fields like Paradigm (-translation, -transcription, -sound, etc) into single cell
        var perspectiveToDictionaryFields = function(perspectiveFields) {
            var fields = [];
            angular.forEach(perspectiveFields, function(field, index) {
                if (typeof field.group == 'string') {

                    var createNewGroup = true;
                    for (var j = 0; j < fields.length; j++) {
                        if (fields[j].entity_type == field.group && fields[j].isGroup) {
                            fields[j].contains.push(field);
                            createNewGroup = false;
                            break;
                        }
                    }

                    if (createNewGroup) {
                        fields.push({
                            'entity_type': field.group,
                            'isGroup': true,
                            'contains': [field]
                        });
                    }

                } else {
                    fields.push(field);
                }
            });
            return fields;
        };

        var getLexicalEntries = function(url, offset, count) {

            var deferred = $q.defer();

            var allLexicalEntriesUrl = url;
            allLexicalEntriesUrl = addUrlParameter(allLexicalEntriesUrl, 'start_from', offset);
            allLexicalEntriesUrl = addUrlParameter(allLexicalEntriesUrl, 'count', count);

            $http.get(allLexicalEntriesUrl).success(function(data, status, headers, config) {
                if (data.lexical_entries && angular.isArray(data.lexical_entries)) {
                    deferred.resolve(data.lexical_entries);
                } else {
                    deferred.reject('An error occured while fetching lexical entries!');
                }
            }).error(function() {
                deferred.reject('An error occured while fetching lexical entries!');
            });
            return deferred.promise;
        };

        var getLexicalEntriesCount = function(url) {
            var deferred = $q.defer();
            $http.get(url).success(function(data, status, headers, config) {
                var totalEntries = parseInt(data.count);
                if (!isNaN(totalEntries)) {
                    deferred.resolve(totalEntries);
                } else {
                    deferred.reject('An error occurred while fetching dictionary stats');
                }
            }).error(function(data, status, headers, config) {
                deferred.reject('An error occurred while fetching dictionary stats');
            });

            return deferred.promise;
        };

        var getPerspectiveFields = function(url) {
            var deferred = $q.defer();
            $http.get(url).success(function(data, status, headers, config) {
                if (angular.isArray(data.fields)) {
                    var fields = perspectiveToDictionaryFields(data.fields);
                    deferred.resolve(fields);
                } else {
                    deferred.reject('An error occurred while fetching perspective fields');
                }
            }).error(function(data, status, headers, config) {
                deferred.reject('An error occurred while fetching perspective fields');
            });

            return deferred.promise;
        };

        var removeValue = function(entry, field, fieldValue, parent) {

            var deferred = $q.defer();
            var url;
            if (field.level) {
                switch (field.level) {
                    case  'leveloneentity':
                        url =
                            '/dictionary/' + encodeURIComponent(dictionaryClientId) + '/' + encodeURIComponent(dictionaryObjectId) + '/perspective/' + encodeURIComponent(perspectiveClientId) + '/' + encodeURIComponent(perspectiveId) + '/lexical_entry/' + encodeURIComponent(entry.client_id) + '/' + encodeURIComponent(entry.object_id) + '/leveloneentity/' + encodeURIComponent(fieldValue.client_id) + '/' + encodeURIComponent(fieldValue.object_id);
                        break;
                    case 'leveltwoentity':
                        if (parentClientId && parentObjectId) {
                            url =
                                '/dictionary/' + encodeURIComponent(dictionaryClientId) + '/' + encodeURIComponent(dictionaryObjectId) + '/perspective/' + encodeURIComponent(perspectiveClientId) + '/' + encodeURIComponent(perspectiveId) + '/lexical_entry/' + encodeURIComponent(fieldValue.client_id) + '/' + encodeURIComponent(fieldValue.object_id) + '/leveloneentity/' + encodeURIComponent(parent.client_id) + '/' + encodeURIComponent(parent.object_id) + '/leveltwoentity/' + encodeURIComponent(fieldValue.client_id) + '/' + encodeURIComponent(fieldValue.object_id);
                        } else {
                            deferred.reject('Attempting to delete Level2 entry with no Level1 entry.');
                            return deferred.promise;
                        }
                        break;
                    default:
                        deferred.reject('Unknown level.');
                        return deferred.promise;
                }

                $http.delete(url).success(function(data, status, headers, config) {
                    deferred.resolve(data);
                }).error(function(data, status, headers, config) {
                    deferred.reject('An error  occurred while removing value');
                });

            } else {
                deferred.reject('An error  occurred while removing value');
            }

            return deferred.promise;
        };


        var saveValue = function(dictionaryClientId, dictionaryObjectId, perspectiveClientId, perspectiveObjectId, entry, field, value, parent) {

            var deferred = $q.defer();
            var url;
            if (field.level) {
                switch (field.level) {
                    case  'leveloneentity':
                        url =
                            '/dictionary/' + encodeURIComponent(dictionaryClientId) + '/' + encodeURIComponent(dictionaryObjectId) + '/perspective/' + encodeURIComponent(perspectiveClientId) + '/' + encodeURIComponent(perspectiveObjectId) + '/lexical_entry/' + encodeURIComponent(entry.client_id) + '/' + encodeURIComponent(entry.object_id) + '/leveloneentity';
                        break;
                    case 'leveltwoentity':
                        if (parent.client_id && parent.object_id) {
                            url =
                                '/dictionary/' + encodeURIComponent(dictionaryClientId) + '/' + encodeURIComponent(dictionaryObjectId) + '/perspective/' + encodeURIComponent(perspectiveClientId) + '/' + encodeURIComponent(perspectiveObjectId) + '/lexical_entry/' + encodeURIComponent(entry.client_id) + '/' + encodeURIComponent(entry.object_id) + '/leveloneentity/' + encodeURIComponent(parent.client_id) + '/' + encodeURIComponent(parent.object_id) + '/leveltwoentity';
                        } else {
                            deferred.reject('Attempting to save Level2 entry with no Level1 entry.');
                            return deferred.promise;
                        }
                        break;
                    default:
                        deferred.reject('Unknown level.');
                        return deferred.promise;
                }

                $http.post(url, value).success(function(data, status, headers, config) {
                    value.client_id = data.client_id;
                    value.object_id = data.object_id;
                    deferred.resolve(value);
                }).error(function(data, status, headers, config) {
                    deferred.reject('An error  occurred while saving value');
                });

            } else {
                deferred.reject('An error  occurred while saving value');
            }

            return deferred.promise;
        };

        var addNewLexicalEntry = function(url) {
            var deferred = $q.defer();

            $http.post(url).success(function(data, status, headers, config) {
                deferred.resolve(data);
            }).error(function(data, status, headers, config) {
                deferred.reject('An error occurred while creating a new lexical entry');
            });

            return deferred.promise;
        };

        var getConnectedWords = function(clientId, objectId) {
            var deferred = $q.defer();
            var url = '/lexical_entry/' + encodeURIComponent(clientId) + '/' + encodeURIComponent(objectId) + '/connected';
            $http.get(url).success(function(data, status, headers, config) {
                if (angular.isArray(data.words)) {
                    deferred.resolve(data.words);
                } else {
                    deferred.reject('An error  occurred while fetching connected words');
                }

            }).error(function(data, status, headers, config) {
                deferred.reject('An error  occurred while fetching connected words');
            });

            return deferred.promise;
        };

        var linkEntries = function(e1, e2, entityType) {
            var deferred = $q.defer();
            var linkObject = {
                'entity_type': entityType,
                'connections': [
                    {
                        'client_id': e1.client_id,
                        'object_id': e1.object_id
                    },
                    {
                        'client_id': e2.client_id,
                        'object_id': e2.object_id
                    }]
            };

            var url = '/group_entity';
            $http.post(url, linkObject).success(function(data, status, headers, config) {
                deferred.resolve(data);
            }).error(function(data, status, headers, config) {
                deferred.reject('An error  occurred while connecting 2 entries')
            });

            return deferred.promise;
        };

        var search = function(query) {
            var deferred = $q.defer();
            var url = '/basic_search?leveloneentity=' + encodeURIComponent(query);
            $http.get(url).success(function(data, status, headers, config) {
                var urls = [];
                for (var i = 0; i < data.length; i++) {
                    var entr = data[i];
                    var getEntryUrl = '/dictionary/' + encodeURIComponent(entr.origin_dictionary_client_id) + '/' + encodeURIComponent(entr.origin_dictionary_object_id) + '/perspective/' + encodeURIComponent(entr.origin_perspective_client_id) + '/' + encodeURIComponent(entr.origin_perspective_object_id) + '/lexical_entry/' + encodeURIComponent(entr.client_id) + '/' + encodeURIComponent(entr.object_id);
                    urls.push(getEntryUrl);
                }

                var uniqueUrls = urls.filter(function(item, pos) {
                    return urls.indexOf(item) == pos;
                });

                var requests = [];
                for (var j = 0; j < uniqueUrls.length; j++) {
                    var r = $http.get(uniqueUrls[j]);
                    requests.push(r);
                }

                $q.all(requests).then(function(results) {
                    var suggestedEntries = [];
                    for (var k = 0; k < results.length; k++) {
                        if (results[k].data) {
                            suggestedEntries.push(results[k].data.lexical_entry);
                        }
                    }
                    deferred.resolve(suggestedEntries);
                });

            }).error(function(data, status, headers, config) {
                deferred.reject('An error  occurred while doing basic search');
            });

            return deferred.promise;
        };

        var approve = function(url, entity, status) {
            var deferred = $q.defer();

            if (status) {
                $http.patch(url, entity).success(function(data, status, headers, config) {
                    deferred.resolve(data);
                }).error(function(data, status, headers, config) {
                    deferred.reject('An error  occurred while trying to change approval status ')
                });
            } else {

                var config = {
                    method: 'DELETE',
                    url: url,
                    data: entity,
                    headers: {'Content-Type': 'application/json;charset=utf-8'}
                };
                $http(config).success(function(data, status, headers, config) {
                    deferred.resolve(data);
                }).error(function(data, status, headers, config) {
                    deferred.reject('An error  occurred while trying to change approval status ')
                });
            }
            return deferred.promise;
        };

        var approveAll = function(url) {
            var deferred = $q.defer();
            $http.patch(url).success(function(data, status, headers, config) {
                deferred.resolve(data);
            }).error(function(data, status, headers, config) {
                deferred.reject('An error  occurred while trying to change approval status ')
            });

            return deferred.promise;
        };


        // Return public API.
        return ({
            'getLexicalEntries': getLexicalEntries,
            'getLexicalEntriesCount': getLexicalEntriesCount,
            'getPerspectiveFields': getPerspectiveFields,
            'addNewLexicalEntry': addNewLexicalEntry,
            'saveValue': saveValue,
            'removeValue': removeValue,
            'getConnectedWords': getConnectedWords,
            'linkEntries': linkEntries,
            'search': search,
            'approve': approve,
            'approveAll': approveAll
        });
    })

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

    .controller('ViewDictionaryController', ['$scope', '$window', '$http', '$modal', '$log', 'dictionaryService', function($scope, $window, $http, $modal, $log, dictionaryService) {


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
                    $log.error(reason);
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

        dictionaryService.getPerspectiveFields($('#getPerspectiveFieldsUrl').data('lingvodoc')).then(function(fields) {

            $scope.fields = fields;
            dictionaryService.getLexicalEntries($('#allPublishedEntriesUrl').data('lingvodoc'), ($scope.pageIndex - 1) * $scope.pageSize, $scope.pageSize).then(function(lexicalEntries) {
                $scope.lexicalEntries = lexicalEntries;
            }, function(reason) {
                $log.error(reason);
            });

        }, function(reason) {
            $log.error(reason);
        });

        dictionaryService.getLexicalEntriesCount($('#allPublishedEntriesCountUrl').data('lingvodoc')).then(function(totalEntriesCount) {
            $scope.pageCount = Math.ceil(totalEntriesCount / $scope.pageSize);
        }, function(reason) {
            $log.error(reason);
        });

    }])


    .controller('AnnotationController', ['$scope', '$http', 'soundUrl', 'annotationUrl', function($scope, $http, soundUrl, annotationUrl) {

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
                    alert('Failed to parse ELAN annotation: ' + e);
                }

            }).error(function(data, status, headers, config) {
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


    .controller('viewGroupController', ['$scope', '$http', '$modalInstance', '$log', 'dictionaryService', 'groupParams', function($scope, $http, $modalInstance, $log, dictionaryService, groupParams) {

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
                $log.error(reason);
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

    .controller('viewGroupingTagController', ['$scope', '$http', '$modalInstance', '$q', '$log', 'dictionaryService', 'groupParams', function($scope, $http, $modalInstance, $q, $log, dictionaryService, groupParams) {

        var dictionaryClientId = $('#dictionaryClientId').data('lingvodoc');
        var dictionaryObjectId = $('#dictionaryObjectId').data('lingvodoc');
        var perspectiveClientId = $('#perspectiveClientId').data('lingvodoc');
        var perspectiveId = $('#perspectiveId').data('lingvodoc');

        WaveSurferController.call(this, $scope);

        $scope.fields = groupParams.fields;
        $scope.connectedEntries = [];
        $scope.suggestedEntries = [];

        $scope.searchQuery = '';

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

        $scope.linkEntries = function(entry) {

            dictionaryService.linkEntries(groupParams.entry, entry, 'Etymology').then(function(data) {
                $scope.connectedEntries.push(entry);
            }, function(reason) {
                $log.error(reason);
            });
        };


        $scope.unlinkEntry = function(index) {
            $scope.connectedEntries.splice(index);
        };


        $scope.ok = function() {
            $modalInstance.close();
        };

        $scope.$watch('connectedEntries', function(updatedEntries) {
            $scope.fieldsValues = $scope.mapFieldValues(updatedEntries, $scope.fields);
        }, true);

        dictionaryService.getConnectedWords(groupParams.entry.client_id, groupParams.entry.object_id).then(function(entries) {

            angular.forEach(entries, function(entry) {
                $scope.connectedEntries.push(entry.lexical_entry);
            });

        }, function(reason) {

        });

    }]);
