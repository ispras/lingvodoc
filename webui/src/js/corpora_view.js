angular.module('CorporaViewModule', ['ui.bootstrap'])

    .factory('dictionaryService', ['$http', '$q', lingvodocAPI])

    .factory('responseHandler', ['$timeout', '$modal', responseHandler])

    .directive('onSelected', [function() {

        function getSelected() {
            var text = "";
            if (window.getSelection
                && window.getSelection().toString()
                && angular.element(window.getSelection()).attr('type') != "Caret") {
                text = window.getSelection();
                return text;
            }
            else if (document.getSelection
                && document.getSelection().toString()
                && angular.element(document.getSelection()).attr('type') != "Caret") {
                text = document.getSelection();
                return text;
            }
            else {
                var selection = document.selection && document.selection.createRange();

                if (!(typeof selection === "undefined")
                    && selection.text
                    && selection.text.toString()) {
                    text = selection.text;
                    return text;
                }
            }

            return false;
        }

        return {
            restrict: 'A',

            replace: false,

            link: function(scope, element, attrs) {
                element.bind('mouseup', function() {
                    if (angular.isFunction(scope.onSelected)) {

                        var selected = getSelected();
                        scope.onSelected.apply(this, [selected.toString(), selected]);
                    }
                });

            },
            scope: {
                onSelected: '='
            }
        };
    }])

    .controller('CorporaViewController', ['$scope', '$http', '$q', '$modal', '$location', '$log', 'dictionaryService', 'responseHandler', function($scope, $http, $q, $modal, $location, $log, dictionaryService, responseHandler) {

        var dictionaryClientId = $('#dictionaryClientId').data('lingvodoc');
        var dictionaryObjectId = $('#dictionaryObjectId').data('lingvodoc');
        var perspectiveClientId = $('#perspectiveClientId').data('lingvodoc');
        var perspectiveId = $('#perspectiveId').data('lingvodoc');

        $scope.dictionaries = [];
        $scope.parseResults = {};

        $scope.getPhraseValue = function(phrase, type) {

            var val = _.find(phrase, function(p) {
                return p.type == type;
            });

            if (val) {
                return val.text;
            }
        };


        $scope.getmtxt = function(morphems) {
            var v = _.find(morphems, function(m) {
                return m.lang != 'ru';
            });

            if (v) {
                return v.text;
            }
        };

        $scope.getmgls = function(morphems) {
            var v = _.find(morphems, function(m) {
                return m.lang == 'ru';
            });

            if (v) {
                return v.text;
            }
        };

        $scope.getWordsText = function(words) {
            return _.map(words, function(w) {
                return w.text;
            }).join(' ');
        };

        $scope.selectedWord = function(selectedText, selection) {
            //$log.info(word);
            //$log.info(selection);
            selectedText = 'хайдаң килген';

            var normalize = (function() {
                var translate_re = /[aceiopxyöÿҷ]/g;
                var translate = {
                    'a': 'а', 'c': 'с', 'e': 'е', 'i': '\u0456', 'o': 'о', 'p': 'р', 'x': 'х', 'y': 'у', 'ö': '\u04E7', 'ÿ': '\u04F1', 'ҷ': 'ӌ'
                };
                return function(s) {
                    return s.toLowerCase().replace(translate_re, function(match) {
                        return translate[match];
                    });
                }
            })();

            function parse_word(word, callback_data, callback) {
                $http.get('/suddenly/' + '?parse=' + word).success(function(data, status, headers, config) {

                    var omonyms = [];
                    var i, j, k;
                    while ((i = data.indexOf('FOUND STEM:')) >= 0) {
                        var omonym = {};
                        data = data.substr(i + 12);
                        j = data.indexOf(' ');
                        i = data.indexOf('\n');
                        omonym['form'] = data.substr(0, j);
                        omonym['affixes'] = data.substring(j + 1, i);
                        data = data.substr(i + 1);
                        omonym['p_o_s'] = data[0];
                        i = data.indexOf('\n');
                        var dict = data.substring(2, i);
                        j = dict.indexOf(' ‛');
                        omonym['headword'] = dict.substr(0, j);
                        k = dict.indexOf('’');
                        omonym['meaning'] = dict.substring(j + 1, k + 1);
                        if (dict.length > k + 1) {
                            omonym['stem'] = dict.substr(k + 2);
                        }
                        omonyms.push(omonym);
                    }
                    callback(callback_data, omonyms);

                }).error(function(data, status, headers, config) {
                    responseHandler.error(data);
                });
            }

            var results = [];
            var text = normalize(selectedText);
            var re = /[а-я\u0456\u04E7\u04F1\u0493\u04A3\u04CC]+/g;
            var matched;
            var n = 1;
            while (matched = re.exec(text)) {
                var word = matched[0];
                var a = {
                    'word': word,
                    'omonyms': []
                };
                parse_word(word, a, function(a, omonyms) {
                    a['omonyms'] = omonyms;
                });
                results.push(a);
            }

            $modal.open({
                animation: true,
                templateUrl: 'viewParseModal.html',
                controller: 'ViewParseController',
                size: 'lg',
                backdrop: 'static',
                keyboard: false,
                resolve: {
                    'params': function() {
                        return {
                            'parseResults': results
                        };
                    }
                }
            });
        };

        $scope.showEntry = function(word) {

            dictionaryService.getLexicalEntry(word.client_id, word.object_id).then(function(entry) {

                $modal.open({
                    animation: true,
                    templateUrl: 'viewEntryModal.html',
                    controller: 'ViewEntryController',
                    size: 'lg',
                    backdrop: 'static',
                    keyboard: false,
                    resolve: {
                        'params': function() {
                            return {
                                'entry': entry,
                                'perspective': $scope.corporaPerspective,
                                'dictionary': $scope.corporaDictionary
                            };
                        }
                    }
                });

            }, function(reason) {
                responseHandler.error(reason);
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

                    var corporaDictionary = _.find($scope.dictionaries, function(d) {
                        return (d.client_id == dictionaryClientId && d.object_id == dictionaryObjectId);
                    });

                    var corporaPerspective = _.find(corporaDictionary.perspectives, function(p) {
                        return (p.client_id == perspectiveClientId && p.object_id == perspectiveId);
                    });

                    if (_.isObject(corporaPerspective) && _.isObject(corporaDictionary)) {
                        $scope.corporaDictionary = corporaDictionary;
                        $scope.corporaPerspective = corporaPerspective;
                        var meta = corporaPerspective.additional_metadata;
                        if (_.isString(meta)) {
                            meta = JSON.parse(meta);
                        }
                        $scope.corpora = meta.corpora.content;
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

    }])

    .controller('ViewEntryController', ['$scope', '$modal', '$modalInstance', '$log', 'dictionaryService', 'responseHandler', 'params', function($scope, $modal, $modalInstance, $log, dictionaryService, responseHandler, params) {

        $scope.lexicalEntries = [];
        $scope.dictionaryTable = [];

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

        $scope.ok = function() {
            $modalInstance.close($scope.entries);
        };

        $scope.$watch('entries', function(updatedEntries) {
            $scope.mapFieldValues(updatedEntries, $scope.fields);
        }, true);


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

            $scope.fields = params.perspective.fields;
            $scope.dictionaryTable = mapFieldValues(updatedEntries, params.perspective.fields);

        }, true);

        $scope.lexicalEntries = [params.entry];

    }])

    .controller('viewGroupController', ['$scope', '$http', '$modalInstance', '$log', 'dictionaryService', 'responseHandler', 'groupParams', function($scope, $http, $modalInstance, $log, dictionaryService, responseHandler, groupParams) {

        $scope.title = groupParams.field.entity_type;
        $scope.fields = groupParams.field.contains;
        $scope.parentEntry = groupParams.entry;

        var createVirtualEntries = function(values) {
            var virtualEntries = [];

            var addValue = function(value, entries) {

                if (value.additional_metadata) {
                    for (var entryIndex = 0; entryIndex < entries.length; entryIndex++) {

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

        $scope.ok = function() {
            $modalInstance.close($scope.entries);
        };

        $scope.$watch('entries', function(updatedEntries) {
            $scope.mapFieldValues(updatedEntries, $scope.fields);
        }, true);

    }])

    .controller('ViewParseController', ['$scope', '$sce', '$http', '$modalInstance', '$log', 'dictionaryService', 'responseHandler', 'params', function($scope, $sce, $http, $modalInstance, $log, dictionaryService, responseHandler, params) {

        $scope.parseResults = params.parseResults;
        $scope.selectedWord = {};

        $scope.wrapOmonym = function(omonym) {
            return $sce.trustAsHtml(omonym.form.replace(/([^-]+)/g, '<span class="sc">$1</span>'));
        };

        $scope.selectWord = function(r) {
            $scope.selectedWord = r;
        };

        $scope.ok = function() {
            $modalInstance.close($scope.entries);
        };

    }]);









