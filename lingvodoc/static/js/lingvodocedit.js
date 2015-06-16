'use strict';

var model = {};

model.Value = function() {
    this.type = 'abstract';
};

model.TextValue = function(type, content) {
    this.type = type;
    this.content = content;
};
model.TextValue.prototype = new model.Value();

model.SoundValue = function(name, mime, content) {
    this.type = 'sounds';
    this.name = name;
    this.mime = mime;
    this.content = content;
};
model.SoundValue.prototype = new model.Value();


var app = angular.module('editDictionaryModule', ['ui.bootstrap']);

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


app.directive('onReadFile', function ($parse) {
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
                            $fileName   : file.name,
                            $fileType   : file.type,
                            $fileContent: b64file
                        });
                    });
                };

                reader.readAsBinaryString(file);
            });
        }
    };
});


app.controller('EditDictionaryController', ['$scope', '$http', '$modal', function($scope, $http, $modal) {

    $scope.metawords = [];

    $scope.pageIndex = 1;
    $scope.pageSize = 10;
    $scope.pageCount = 1;

    $scope.paused = true;


    var activeUrl = null;
    var enabledInputs = [];

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


    $scope.play = function(url) {
        if(!$scope.wavesurfer) {
            return;
        }

        activeUrl = url;

        $scope.wavesurfer.once('ready', function() {
            $scope.wavesurfer.play();
            $scope.$apply();
        });

        $scope.wavesurfer.load(activeUrl);
    };


    $scope.markup = function(sound) {
        var modalInstance = $modal.open({
            animation  : true,
            templateUrl: 'markupModal.html',
            controller : 'MarkupController',
            size       : 'lg',
            resolve    : {
                soundUrl: function () {
                    return sound.url;
                }
            }
        });
    };



    $scope.playPause = function() {
        $scope.wavesurfer.playPause();
    };

    $scope.isPlaying = function(url) {
        return url == activeUrl;
    };

    $scope.isMediaFileAvailable = function() {
        return activeUrl != null;
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

    $scope.addedByUser = function(metaword) {
        return !!metaword.addedByUser;
    };

    $scope.isInputEnabled = function(metaword, type) {
        for (var i = 0; i < enabledInputs.length; i++) {
            var checkItem = enabledInputs[i];
            if (checkItem.metaword_id === metaword.metaword_id && type === checkItem.type) {
                return true;
            }
        }
        return false;
    };

    $scope.disableInput = function(metaword, type) {

        console.log(metaword, type);
        console.log(enabledInputs);
        var removeIndex = -1;
        for (var i = 0; i < enabledInputs.length; i++) {
            if (enabledInputs[i].metaword_id === metaword.metaword_id && enabledInputs[i].type === type) {
                removeIndex = i;
                break;
            }
        }

        if (removeIndex >= 0) {
            enabledInputs.splice(removeIndex, 1);
        }
    };



    $scope.addNewMetaWord = function() {
        $scope.metawords.unshift({
            'metaword_id'   : 'new',
            'entries'       : [],
            'transcriptions': [],
            'translations'  : [],
            'sounds'        : [],
            'addedByUser'   : true
        });
    };

    $scope.addValue = function(metaword, type) {
        if (!$scope.isInputEnabled(metaword, type)) {
            enabledInputs.push({
                'metaword_id': metaword.metaword_id,
                'type'       : type
            });
        }
    };

    $scope.removeValue = function(metaword, value, type) {
        console.log(arguments);
    };

    $scope.saveTextValue = function(metaword, type, event) {
        if (['entries', 'translations', 'transcriptions'].indexOf(type) >= 0 && event.target.value) {
            $scope.saveValue(metaword, new model.TextValue(type, event.target.value));
        }
    };

    $scope.saveSoundValue = function(metaword, name, type, content) {
        $scope.saveValue(metaword, new model.SoundValue(name, type, content));
    };

    $scope.saveValue = function(metaword, value) {

        var updateId = false;
        var obj = {};
        // when edit existing word, copy id and dict_id
        if (metaword.metaword_id !== 'new') {
            obj['client_id'] = metaword.client_id;
            obj['metaword_id'] = metaword.metaword_id;
            obj['metaword_client_id'] = metaword.metaword_client_id;
        } else {
            updateId = true; // update id after word is saved
        }

        if(value instanceof model.SoundValue) {
            obj[value.type] = [];
            obj[value.type].push({'name': value.name, 'content': value.content, 'type': value.mime });
        } else if (value instanceof model.TextValue) {
            obj[value.type] = [];
            obj[value.type].push({'content': value.content});
        } else {
            console.error('Value type is not supported!');
            return;
        }

        var url = $('#getMetaWordsUrl').data('lingvodoc');
        $http.post(url, obj).success(function(data, status, headers, config) {

            if(updateId) {
                metaword.client_id = data.client_id;
                metaword.metaword_id = data.metaword_id;
                metaword.metaword_client_id = data.metaword_client_id;
            }
            metaword[value.type] = data[value.type];

            $scope.disableInput(metaword, value.type);

        }).error(function(data, status, headers, config) {
        });
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




    // signal handlers
    $scope.$on('wavesurferInit', function(e, wavesurfer) {

        $scope.wavesurfer = wavesurfer;

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
    });


    // load data
    getDictStats();
    getMetawords();

}]);

app.controller('ShowEtymologyController', ['$scope', '$http', 'words', function($scope, $http, words) {

    var activeUrl = null;

    $scope.words = words;

    $scope.play = function(url) {
        if(!$scope.wavesurfer) {
            return;
        }

        activeUrl = url;

        $scope.wavesurfer.once('ready', function() {
            $scope.wavesurfer.play();
            $scope.$apply();
        });

        $scope.wavesurfer.load(activeUrl);
    };

    $scope.playPause = function() {
        $scope.wavesurfer.playPause();
    };

    $scope.isPlaying = function(url) {
        return url == activeUrl;
    };

    $scope.isMediaFileAvailable = function() {
        return activeUrl != null;
    };

    // signal handlers
    $scope.$on('wavesurferInit', function(e, wavesurfer) {

        $scope.wavesurfer = wavesurfer;

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
    });

    $scope.$on('modal.closing', function(e) {
        $scope.wavesurfer.stop();
        $scope.wavesurfer.destroy();
    });
}]);

app.controller('ShowParadigmsController', ['$scope', '$http', 'words', function($scope, $http, words) {

    var activeUrl = null;

    $scope.words = words;

    $scope.play = function(url) {
        if(!$scope.wavesurfer) {
            return;
        }

        activeUrl = url;

        $scope.wavesurfer.once('ready', function() {
            $scope.wavesurfer.play();
            $scope.$apply();
        });

        $scope.wavesurfer.load(activeUrl);
    };

    $scope.playPause = function() {
        $scope.wavesurfer.playPause();
    };

    $scope.isPlaying = function(url) {
        return url == activeUrl;
    };

    $scope.isMediaFileAvailable = function() {
        return activeUrl != null;
    };

    // signal handlers
    $scope.$on('wavesurferInit', function(e, wavesurfer) {

        $scope.wavesurfer = wavesurfer;

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
    });

    $scope.$on('modal.closing', function(e) {
        $scope.wavesurfer.stop();
        $scope.wavesurfer.destroy();
    });
}]);

app.controller('MarkupController', ['$scope', '$http', 'soundUrl', function($scope, $http, soundUrl) {

    var activeUrl = null;

    $scope.play = function(url) {

        if(!$scope.wavesurfer) {
            return;
        }

        activeUrl = url;

        $scope.wavesurfer.once('ready', function() {
            $scope.wavesurfer.play();
            $scope.$apply();
        });

        $scope.wavesurfer.load(activeUrl);
    };

    $scope.playPause = function() {
        $scope.wavesurfer.playPause();
    };

    $scope.isPlaying = function(url) {
        return $scope.wavesurfer.isPlaying();
    };

    $scope.isMediaFileAvailable = function() {
        return activeUrl != null;
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

        $scope.play(soundUrl);
    });

    $scope.$on('modal.closing', function(e) {
        $scope.wavesurfer.stop();
        $scope.wavesurfer.destroy();
    });

}]);
