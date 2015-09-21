'use strict';

var Value = function(lang, content) {
    this.lang = lang;
    this.content = content;
};

var TextTitle = function(lang, content) {
    Value.call(this, lang, content);
};
TextTitle.prototype = new Value();

var TextComment = function(lang, content) {
    Value.call(this, lang, content);
};
TextComment.prototype = new Value();

var Item = function(lang, content, type) {
    this.type = type;
    Value.call(this, lang, content);
};
Item.prototype = new Value();

var Translation = function(lang, content) {
    Value.call(this, lang, content);
};
Translation.prototype = new Value();

var DictItem = function(url) {
    this.type = 'lingvodoc_metaword';
    this.url = url;
};

var Word = function(items) {
    this.items = items;

    // returns true if word is linked to some
    // metaword in dictionary. otherwise it
    // return false
    this.hasDictionaryEntry = function() {
        for (var i = 0; i < this.items.length; i++) {
            if (this.items[i].type == 'lingvodoc_metaword') {
                return true;
            }
        }
        return false;
    }.bind(this);

    this.getDictionaryEntry = function() {
        for (var i = 0; i < this.items.length; i++) {
            var item = this.items[i];
            if (item.type == 'lingvodoc_metaword') {
                return item;
            }
        }
        return null;
    }.bind(this);

    this.getTextEntry = function() {
        for (var i = 0; i < this.items.length; i++) {
            var item = this.items[i];
            if (item.type == 'txt') {
                return item;
            }
        }
        return null;
    }.bind(this);
};
Word.fromJS = function(word) {
    var items = [];
    for (var i = 0; i < word.items.length; i++) {
        var item = word.items[i];
        if (item.type === 'lingvodoc_metaword') {
            items.push(new DictItem(item.url));
        } else {
            items.push(new Item(item.lang, item.content, item.type));
        }
    }
    return new Word(items);
};

var Phrase = function(words, translations) {
    this.words = words;
    this.translations = translations;
};
Phrase.fromJS = function(phrase) {
    var i = 0, words = [], translations = [];
    for (i = 0; i < phrase.words.length; i++) {
        var word = phrase.words[i];
        words.push(Word.fromJS(word));
    }

    for (i = 0; i < phrase.translations.length; i++) {
        var translation = phrase.translations[i];
        translations.push(new Translation(translation.lang, translation.content));
    }
    return new Phrase(words, translations);
};

var Paragraph = function(phrases) {
    this.phrases = phrases;
};
Paragraph.fromJS = function(paragraph) {
    var phrases = [];
    for (var i = 0; i < paragraph.phrases.length; i++) {
        var phrase = paragraph.phrases[i];
        phrases.push(Phrase.fromJS(phrase));
    }
    return new Paragraph(phrases);
};

var Text = function(text_id, client_id, text_titles, paragraphs) {
    this.text_id = text_id;
    this.client_id = client_id;
    this.text_titles = text_titles;
    this.paragraphs = paragraphs;
};
Text.fromJS = function(text) {
    var i;
    var text_titles = [], paragraphs = [];

    for (i = 0; i < text.text_titles.length; i++) {
        var title = text.text_titles[i];
        text_titles.push(new TextTitle(title.lang, title.content));
    }

    for (i = 0; i < text.paragraphs.length; i++) {
        var paragraph = text.paragraphs[i];
        paragraphs.push(Paragraph.fromJS(paragraph));
    }
    return new Text(text.text_id, text.client_id, text_titles, paragraphs);
};



var app = angular.module('demoModule', ['ui.bootstrap']);

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

app.controller('DemoController', ['$scope', '$http', '$modal', function($scope, $http, $modal) {

    $scope.texts = [];

    var url = $('#getCorpusUrl').data('lingvodoc');
    $http.get(url).success(function(data, status, headers, config) {
        if (data.corpus_id && data.corpus_client_id) {
            for (var i = 0; i < data.texts.length; i++) {
                $scope.texts.push(Text.fromJS(data.texts[i]));
                if (i > 5) break;
            }
        }
    }).error(function(data, status, headers, config) {
    });

    $scope.showWordInfo = function(word) {

        var modalInstance = $modal.open({
            animation  : true,
            templateUrl: 'wordItemsTtemplate.html',
            controller : 'ShowWordController',
            size       : 'lg',
            resolve    : {
                items: function() {
                    return word.items;
                },
                title: function() {
                    return word.getTextEntry();
                }
            }
        });
    };

    $scope.showMetawordInfo = function(word) {
        if (word.url && word.paradigm_url && word.etymology_url) {
            var modalInstance = $modal.open({
                animation  : true,
                templateUrl: 'wordMetawordTemplate.html',
                controller : 'ShowMetawordController',
                size       : 'lg',
                resolve    : {
                    metawordUrl : function() {
                        return word.url;
                    },
                    etymologyUrl: function() {
                        return word.paradigm_url;
                    },
                    paradigmUrl : function() {
                        return word.etymology_url;
                    }
                }
            });
        }
    };
    
}]);

app.controller('ShowWordController', ['$scope', 'items', 'title', function($scope, items, title) {
    $scope.title = title;
    $scope.items = items;
}]);

app.controller('ShowMetawordController', ['$scope', '$http', 'metawordUrl', 'etymologyUrl', 'paradigmUrl', function($scope, $http, metawordUrl, etymologyUrl, paradigmUrl) {

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

    $http.get(metawordUrl).success(function(data, status, headers, config) {
        if (data.corpus_id && data.corpus_client_id) {
            $scope.metaword = data;
        }
    }).error(function(data, status, headers, config) {
    });

    $http.get(etymologyUrl).success(function(data, status, headers, config) {
        if (data.corpus_id && data.corpus_client_id) {
            $scope.etymologies = data;
        }
    }).error(function(data, status, headers, config) {
    });

    $http.get(paradigmUrl).success(function(data, status, headers, config) {
        if (data.corpus_id && data.corpus_client_id) {
            $scope.paradigms = data;
        }
    }).error(function(data, status, headers, config) {
    });

}]);
