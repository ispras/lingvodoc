'use strict';

angular.module('MapsModule', ['ui.bootstrap', 'ngMap'])

    .factory('responseHandler', ['$timeout', '$modal', responseHandler])

    .controller('MapsController', ['$scope', '$http', '$log', 'responseHandler', function($scope, $http, $log, responseHandler) {

        var key = 'AIzaSyB6l1ciVMcP1pIUkqvSx8vmuRJL14lbPXk';
        $scope.googleMapsUrl = 'http://maps.google.com/maps/api/js?v=3.20&key=' + encodeURIComponent(key);









    }]);



