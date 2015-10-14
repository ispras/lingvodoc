var app = angular.module('MergeMasterModule', ['ui.router', 'ui.bootstrap']);

app.config(function ($stateProvider, $urlRouterProvider) {

    $stateProvider
        .state('merge', {
            url: '/merge',
            templateUrl: 'mergeMaster.html',
            controller: 'MergeMasterController'
        })
        .state('merge.intro', {
            url: '/intro',
            templateUrl: 'mergeMasterIntro.html'
        })
        .state('merge.mode', {
            url: '/mode',
            templateUrl: 'mergeMasterMode.html'
        }).state('merge.selectDictionaries', {
            url: '/source-dictionaries',
            templateUrl: 'mergeMasterMode.html'
        }).state('merge.selectPerspectives', {
            url: '/source-perspectives',
            templateUrl: 'mergeMasterSourcePerspectives.html'
        }).state('merge.perspectives', {
            url: '/merge-perspectives',
            templateUrl: 'mergePerspectives.html'
        });




    $urlRouterProvider.otherwise('/merge/intro');
});

app.service('dictionaryService', lingvodocAPI);


app.controller('MergeMasterController', ['$scope', '$http', '$modal', '$interval', '$state', '$log', 'dictionaryService', function ($scope, $http, $modal, $interval, $state, $log, dictionaryService) {

    var clientId = $('#clientId').data('lingvodoc');
    var userId = $('#userId').data('lingvodoc');

    $scope.dictionaries = [];

    $scope.master = {
        'mergeMode': 'dictionaries',
        'selectedSourceDictionaryId': 'None',
        'selectedSourceDictionary': {},
        'perspectiveId1': '',
        'perspectiveId2': '',
        'perspective1': {},
        'perspective2': {},
        'perspectiveName': '',
        'perspectivePreview': []
    };


    var wrapFields = function(fields) {
        angular.forEach(fields, function(field) {
            field._statusEnabled = (field.status == 'enabled');
            field._newEntityType = field.entity_type;
        });
        return fields;
    };

    var unwrapFields = function(fields) {
        var exportFields = cloneObject(fields);
        angular.forEach(exportFields, function(field) {
            if(field._statusEnabled) {
                field.status = 'enabled';
            } else {
                field.status = 'disabled';
            }
            delete field._statusEnabled;


            if (field._newEntityType != field.entity_type) {
                field.new_type_name = field._newEntityType;
            }
            delete field._newEntityType;
        });

        return exportFields;
    };

    var findMatchedFields = function() {
        var matches = [];
        angular.forEach($scope.master.fields1, function(field1) {
            angular.forEach($scope.master.fields2, function(field2) {
                if (field1._statusEnabled && field2._statusEnabled) {
                    if (field1._newEntityType == field2._newEntityType) {
                        matches.push({
                            'first': field1,
                            'second': field2
                        });
                    }
                }
            });
        });
        return matches;
    };

    var createPreview = function(fields1, fields2) {
        $scope.master.perspectivePreview = [];

        angular.forEach(fields1, function(field) {
            if (field._statusEnabled) {
                $scope.master.perspectivePreview.push(field);
            }

        });
        angular.forEach(fields2, function(field) {
            if (field._statusEnabled) {
                $scope.master.perspectivePreview.push(field);
            }
        });
    };


    var removeFieldFromPreview = function(field) {

        var index = -1;
        for (var i = 0; i < $scope.master.perspectivePreview.length; i++) {
            if ($scope.master.perspectivePreview[i]._newEntityType == field._newEntityType) {
                index = i;
            }
        }
        if (index >= 0) {
            $scope.master.perspectivePreview.splice(index, 1);
        }
    };

    var updatePreview = function() {

        var matches = findMatchedFields();
        $scope.master.perspectivePreview = [];

        angular.forEach($scope.master.fields1, function(field) {
            if (field._statusEnabled) {
                $scope.master.perspectivePreview.push(field);
            }
        });
        angular.forEach($scope.master.fields2, function(field) {
            if (field._statusEnabled) {
                $scope.master.perspectivePreview.push(field);
            }
        });

        // remove duplicates
        angular.forEach(matches, function(m) {
           removeFieldFromPreview(m.second);
        });
    };


    $scope.selectSource = function() {
        if ($scope.master.mergeMode == 'dictionaries') {
            $state.go('merge.selectDictionaries');
        }

        if ($scope.master.mergeMode == 'perspectives') {
            $state.go('merge.selectPerspectives');
        }
    };

    $scope.startMergePerspectives = function() {
        if ($scope.master.perspective1 instanceof lingvodoc.Perspective &&
            $scope.master.perspective2 instanceof lingvodoc.Perspective) {

            if ($scope.master.perspective1.equals($scope.master.perspective2)) {
                alert('Please, select 2 different perspectives');
                return;
            }

            var p1 = $scope.master.perspective1;
            var url1 = '/dictionary/' + p1.parent_client_id + '/' + p1.parent_object_id + '/perspective/' + p1.client_id + '/' + p1.object_id + '/fields';
            var p2 = $scope.master.perspective2;
            var url2 = '/dictionary/' + p2.parent_client_id + '/' + p2.parent_object_id + '/perspective/' + p2.client_id + '/' + p2.object_id + '/fields';

            dictionaryService.getPerspectiveFields(url1).then(function(fields1) {

                dictionaryService.getPerspectiveFields(url2).then(function(fields2) {

                    $scope.master.fields1 = wrapFields(fields1);
                    $scope.master.fields2 = wrapFields(fields2);

                    createPreview($scope.master.fields1, $scope.master.fields2);

                    $state.go('merge.perspectives');

                }, function(reason) {

                });

            }, function(reason) {

            });


        } else {
            $log.error('');
        }
    };

    $scope.commitPerspective = function() {


        var updateFields1 = unwrapFields($scope.master.fields1);
        var updateFields2 = unwrapFields($scope.master.fields2);

        var req = {
            'dictionary_client_id' : $scope.master.selectedSourceDictionary.client_id,
            'dictionary_object_id': $scope.master.selectedSourceDictionary.object_id,
            'translation_string': $scope.master.perspectiveName,
            'translation': $scope.master.perspectiveName,
            'perspectives':[
                {
                    'client_id': $scope.master.perspective1.client_id,
                    'object_id': $scope.master.perspective1.object_id,
                    'fields' : updateFields1
                },
                {
                    'client_id': $scope.master.perspective2.client_id,
                    'object_id': $scope.master.perspective2.object_id,
                    'fields' : updateFields2
                }
            ]
        };

        dictionaryService.mergePerspectives(req).then(function(result) {
            $log.info(result);
        }, function(reason) {

        });
    };

    dictionaryService.getDictionariesWithPerspectives({'user_created': [userId]}).then(function(dictionaries) {
        $scope.dictionaries = dictionaries;
    }, function(reason) {
        $log.error(reason);
    });

    $scope.$watch('master.selectedSourceDictionaryId', function (id) {

        $scope.master.selectedSourceDictionary = {};
        for (var i = 0; i < $scope.dictionaries.length; ++i) {
            if ($scope.dictionaries[i].getId() == id) {
                $scope.master.selectedSourceDictionary = $scope.dictionaries[i];
                break;
            }
        }
    });

    $scope.$watch('master.perspectiveId1', function (id) {
        if (!$scope.master.selectedSourceDictionary.perspectives) {
            return;
        }
        $scope.master.perspective1 = {};
        for (var i = 0; i < $scope.master.selectedSourceDictionary.perspectives.length; ++i) {
            if ($scope.master.selectedSourceDictionary.perspectives[i].getId() == id) {
                $scope.master.perspective1 = $scope.master.selectedSourceDictionary.perspectives[i];
                break;
            }
        }
    });

    $scope.$watch('master.perspectiveId2', function (id) {
        if (!$scope.master.selectedSourceDictionary.perspectives) {
            return;
        }
        $scope.master.perspective2 = {};
        for (var i = 0; i < $scope.master.selectedSourceDictionary.perspectives.length; ++i) {
            if ($scope.master.selectedSourceDictionary.perspectives[i].getId() == id) {
                $scope.master.perspective2 = $scope.master.selectedSourceDictionary.perspectives[i];
                break;
            }
        }
    });

    $scope.$watch('master.fields1', function(fields) {
        updatePreview();
    }, true);

    $scope.$watch('master.fields2', function(fields) {
        updatePreview();
    }, true);

}]);