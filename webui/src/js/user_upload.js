'use strict';

var app = angular.module('UserUploadModule', ['ui.bootstrap']);

app.directive('onReadFile', function($parse) {
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
});

app.controller('UserUploadController', ['$scope', '$http', '$modal', '$log', '$timeout', function($scope, $http, $modal, $log, $timeout) {

    $scope.readFile = function(file) {


        $log.info(file);

        var fd = new FormData();
        fd.append('file', file);
        fd.append('filename', file.name);
        fd.append('data_type', 'dialeqt_dictionary');

        $http.post('/blob', fd, {
            transformRequest: angular.identity,
            headers: {'Content-Type': undefined}
        }).success(function () {

        }).error(function () {


        });
    }


}]);



