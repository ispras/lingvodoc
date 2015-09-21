'use strict';

angular.module('UserUploadModule', ['ui.bootstrap']).directive('onReadFile', function($parse) {
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
}).controller('UserUploadController', ['$scope', '$http', '$modal', '$log', '$timeout', function($scope, $http, $modal, $log, $timeout) {

    var listBlobsUrl = $('#listBlobsUrl').data('lingvodoc');


    $scope.files = [];

    $scope.upload = function(file) {

        var fd = new FormData();
        fd.append('blob', file);
        fd.append('data_type', 'dialeqt_dictionary');

        $http.post('/blob', fd, {
            transformRequest: angular.identity,
            headers: {'Content-Type': undefined}
        }).success(function () {
            loadBlobs();
        }).error(function () {

        });
    };

    var loadBlobs = function() {
        $http.get(listBlobsUrl).success(function (data, status, headers, config) {
            $scope.files = data;
        }).error(function (data, status, headers, config) {
        });
    };

    loadBlobs();

}]);



