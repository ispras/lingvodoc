'use strict';

angular.module('UserUploadModule', ['ui.bootstrap'])

    .directive('onReadFile', function($parse) {
        return {
            restrict: 'A',
            scope: false,
            link: function(scope, element, attrs) {
                var fn = $parse(attrs.onReadFile);

                element.on('change', function(onChangeEvent) {
                    var reader = new FileReader();
                    var file = (onChangeEvent.srcElement || onChangeEvent.target).files[0];

                    scope.$apply(function() {
                        fn(scope, {
                            $file: file
                        });
                    });

                });
            }
        };
    })

    .directive('translatable', ['dictionaryService', getTranslation])

    .factory('responseHandler', ['$timeout', '$modal', responseHandler])

    .controller('UserUploadController', ['$scope', '$http', 'responseHandler', function($scope, $http, responseHandler) {

        var listBlobsUrl = $('#listBlobsUrl').data('lingvodoc');

        $scope.files = [];
        $scope.uploadMsg = false;

        $scope.upload = function(file) {

            var fd = new FormData();
            fd.append('blob', file);
            fd.append('data_type', $scope.dataType);

            $scope.uploadMsg = true;

            $http.post('/blob', fd, {
                transformRequest: angular.identity,
                headers: {'Content-Type': undefined}
            }).success(function() {
                loadBlobs();
                window.location = '/create_dictionary';
            }).error(function() {
                responseHandler.error(reason);
            });
        };

        var loadBlobs = function() {
            $http.get(listBlobsUrl).success(function(data, status, headers, config) {
                $scope.files = data;
            }).error(function(data, status, headers, config) {
                responseHandler.error(reason);
            });
        };

        loadBlobs();

    }])
    .run(function ($rootScope, $window) {
        $rootScope.setLocale = function(locale_id) {
            setCookie("locale_id", locale_id);
            $window.location.reload();
        };
    });



