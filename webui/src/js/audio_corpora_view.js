'use strict';

angular.module('AudioCorporaViewModule', ['ui.bootstrap'])

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

                $scope.$emit('wavesurferInit', wavesurfer, $element);
            }
        };
    })

    .controller('AudioCorporaViewController', ['$scope', '$http', '$q', '$modal', '$log', 'dictionaryService', 'responseHandler', function($scope, $http, $q, $modal, $log, dictionaryService, responseHandler) {

        var dictionaryClientId = $('#dictionaryClientId').data('lingvodoc');
        var dictionaryObjectId = $('#dictionaryObjectId').data('lingvodoc');
        var perspectiveClientId = $('#perspectiveClientId').data('lingvodoc');
        var perspectiveId = $('#perspectiveId').data('lingvodoc');

        WaveSurferController.call(this, $scope);

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

        $scope.annotationTable = {};
        $scope.paused = true;
        $scope.annotation = null;
        $scope.audioReady = false;

        $scope.getAlignableTiers = function(doc) {
            if (!doc) {
                return [];
            }

            return _.filter(doc.tiers, function(t) {
                var a = _.find(t.annotations, function(a) {
                    return a instanceof elan.Annotation;
                });
                return !!a;
            });
        };

        $scope.getRefTiers = function(doc, tier) {

            if (!doc || !tier) {
                return [];
            }

            return _.filter(doc.tiers, function(t) {
                var b = _.find(t.annotations, function(a) {
                    var hasReferencedAnnotations = false;
                    _.forEach(tier.annotations, function(ra) {
                        if (a.ref == ra.id) {
                            hasReferencedAnnotations = true;
                        }
                    });
                    return hasReferencedAnnotations;
                });
                return !!b;
            });
        };

        $scope.getAnnotationTableEntries = function(tier) {
            var r = _.filter($scope.annotationTable, function(annotations, key) {
                return !!_.find(annotations, function(value) {
                    return tier.id == value.tier;
                });
            });

            return _.sortBy(r, function(a) {
                var alignAnnotation = _.find(a, function(ann) {
                    return ann.annotation instanceof elan.Annotation;
                });
                return $scope.annotation.timeSlotRefToSeconds(alignAnnotation.annotation.timeslotRef1);
            });
        };

        $scope.getAnnotation = function(tableEntry, tier) {
            var entry = _.find(tableEntry, function(e) {
                return tier.id == e.tier;
            });
            if (entry) {
                return entry.annotation;
            }

        };

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
                $scope.audioReady = true;
                createRegions($scope.annotation);
                $scope.$apply();
            });
        });

        $scope.$on('modal.closing', function(e) {
            $scope.wavesurfer.stop();
            $scope.wavesurfer.destroy();
        });

        dictionaryService.getDictionary(dictionaryClientId, dictionaryObjectId).then(function(dictionary) {
            dictionaryService.getPerspectiveById(perspectiveClientId, perspectiveId).then(function(perspective) {
                dictionaryService.getPerspectiveMeta(dictionary, perspective).then(function(meta) {
                    if (_.has(meta, 'audio_corpora')) {

                        dictionaryService.getUserBlob(meta.audio_corpora.markup.client_id, meta.audio_corpora.markup.object_id).then(function(blob) {

                            $http.get(blob.url).success(function(data, status, headers, config) {
                                try {
                                    var xml = (new DOMParser()).parseFromString(data, 'application/xml');
                                    var annotation = new elan.Document();
                                    annotation.importXML(xml);
                                    $scope.annotation = annotation;
                                    $scope.annotationTable = annotation.render();
                                } catch (e) {
                                    responseHandler.error('Failed to parse ELAN annotation: ' + e);
                                }
                            }).error(function(data, status, headers, config) {
                                responseHandler.error(status);
                            });

                        }, function(reason) {
                            responseHandler.error(reason);
                        });

                        dictionaryService.getUserBlob(meta.audio_corpora.audio.client_id, meta.audio_corpora.audio.object_id).then(function(blob) {
                            $scope.wavesurfer.load(blob.url);
                        }, function(reason) {
                            responseHandler.error(reason);
                        });
                    }

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
