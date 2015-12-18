var Corpora = function() {

    var Value = function(lang, content) {
        this.lang = lang;
        this.content = content;
    };

    var TextTitle = function(lang, content) {
        Value.call(this, lang, content);
    };
    TextTitle.prototype = new Value();
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

    return {

    }
};

angular.module('CorporaModule', ['ui.bootstrap'])

    .factory('dictionaryService', ['$http', '$q', lingvodocAPI])

    .factory('responseHandler', ['$timeout', '$modal', responseHandler])

    .controller('CorporaController', ['$scope', '$http', '$q', '$modal', '$location', '$log', 'dictionaryService', 'responseHandler', function($scope, $http, $q, $modal, $location, $log, dictionaryService, responseHandler) {

        $scope.dictionaries = [];
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

                    $log.info($scope.dictionaries);

                }, function(reason) {
                    responseHandler.error(reason);
                });

            }, function(reason) {
                responseHandler.error(reason);
            });

        }, function(reason) {
            responseHandler.error(reason);
        });


        var props = {
            'xml_path': '/home/steve/sinie-utesy.xml',
            'dictionary_translation_string': 'Name for new dict',
            'perspective_translation_string': 'name for new persp', 'parent_client_id': 1, 'parent_object_id': 1
        };

        //$http.post('/convert/xml', props).success(function(data, status, headers, config) {
        //
        //}).error(function(data, status, headers, config) {
        //
        //});
    }]);



