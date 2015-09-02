var app = angular.module('viewDictionaryModule', ['ui.bootstrap']);

app.directive('wavesurfer', function() {
    return {
        restrict: 'E',

        link: function($scope, $element, $attrs) {
            $element.css('display', 'block');

            var options = angular.extend({container: $element[0]}, $attrs);
            var wavesurfer = WaveSurfer.create(options);

            if($attrs.url) {
                wavesurfer.load($attrs.url, $attrs.data || null);
            }

            $scope.$emit('wavesurferInit', wavesurfer);
        }
    };
});


app.controller('ViewDictionaryController', ['$scope', '$http', '$modal', function($scope, $http, $modal) {

    WaveSurferController.call(this, $scope);

    $scope.metawords = [];

    $scope.pageIndex = 1;
    $scope.pageSize = 10;
    $scope.pageCount = 1;


    $scope.showEtymology = function(metaword) {

        var url = $('#getMetaWordsUrl').data('lingvodoc') + encodeURIComponent(metaword.metaword_client_id) +
            '/' + encodeURIComponent(metaword.metaword_id) + '/etymology';

        $http.get(url).success(function(data, status, headers, config) {

            var modalInstance = $modal.open({
                animation  : true,
                templateUrl: 'etymologyModal.html',
                controller : 'ShowEtymologyController',
                size       : 'lg',
                resolve    : {
                    words: function () {
                        return data;
                    }
                }
            });

        }).error(function(data, status, headers, config) {
        });
    };


    $scope.showParadigms = function(metaword) {
        var url = $('#getMetaWordsUrl').data('lingvodoc') + encodeURIComponent(metaword.metaword_client_id) +
            '/' + encodeURIComponent(metaword.metaword_id) + '/metaparadigms';

        $http.get(url).success(function(data, status, headers, config) {

            var modalInstance = $modal.open({
                animation  : true,
                templateUrl: 'paradigmModal.html',
                controller : 'ShowParadigmsController',
                size       : 'lg',
                resolve    : {
                    words: function () {
                        return data;
                    }
                }
            });

        }).error(function(data, status, headers, config) {
        });
    };

    $scope.getPage = function(pageNumber) {
        if(pageNumber > 0 && pageNumber <= $scope.pageCount) {
            $scope.pageIndex = pageNumber;
            getMetawords();
        }
    };

    $scope.range = function(min, max, step) {
        step = step || 1;
        var input = [];
        for(var i = min; i <= max; i += step) {
            input.push(i);
        }
        return input;
    };


    var addUrlParameter = function(url, key, value) {
        return url + (url.indexOf('?') >= 0 ? "&" : '?') + encodeURIComponent(key) + "=" + encodeURIComponent(value);
    };


    var getDictStats = function() {
        var getDictStatsUrl = $('#getDictionaryStatUrl').data('lingvodoc');
        $http.get(getDictStatsUrl).success(function(data, status, headers, config) {
            if(data.metawords) {
                $scope.pageCount = Math.ceil(parseInt(data.metawords) / $scope.pageSize);
            }
        }).error(function(data, status, headers, config) {
        });
    };


    var getMetawords = function() {

        var getMetawordsUrl = $('#getMetaWordsUrl').data('lingvodoc');
        getMetawordsUrl = addUrlParameter(getMetawordsUrl, 'offset', ($scope.pageIndex - 1) * $scope.pageSize);
        getMetawordsUrl = addUrlParameter(getMetawordsUrl, 'size', $scope.pageSize);

        $http.get(getMetawordsUrl).success(function(data, status, headers, config) {
            $scope.metawords = data;
        }).error(function(data, status, headers, config) {
        });
    };


    // load data
    getDictStats();
    getMetawords();

}]);


app.controller('ShowEtymologyController', ['$scope', '$http', 'words', function($scope, $http, words) {
    WaveSurferController.call(this, $scope);
    $scope.words = words;
}]);

app.controller('ShowParadigmsController', ['$scope', '$http', 'words', function($scope, $http, words) {

    WaveSurferController.call(this, $scope);
    $scope.words = words;
}]);

