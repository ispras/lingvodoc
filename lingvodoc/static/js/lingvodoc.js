'use strict';

require.config({
    baseUrl: '/static/js/',
    shim: {
        'bootstrap' : ['jquery'],
        'wavesurfer': {
            'exports': 'WaveSurfer'
        }
    },
    paths: {
        'jquery': 'jquery-2.1.1.min',
        'bootstrap': 'bootstrap.min',
        'knockout': 'knockout-3.2.0',
        'wavesurfer': 'wavesurfer.min'
    }
});

require(['model', 'jquery', 'knockout','bootstrap', 'kobindings'], function(model, $, ko) {

    var jQuery = $;

    var wrapArrays = function(word) {
        for (var prop in word) {
            if (word.hasOwnProperty(prop)) {
                if (word[prop] instanceof Array) {
                    word[prop] = ko.observableArray(word[prop]);
                }
            }
        }
    };

    var newEmptyMetaWord = function() {
        var newWord = {'metaword_id': 'new', 'entries': [], 'transcriptions': [], 'translations': [], 'sounds': [], 'addedByUser': true};
        wrapArrays(newWord);
        return newWord;
    };

    var viewModel = function() {

        var currentId = $('#currentId').data('lingvodoc');
        var baseUrl = $('#getMetaWordsUrl').data('lingvodoc');

        // list of meta words loaded from ajax backends
        this.metawords = ko.observableArray([]);

        // list of enabled text inputs in table
        this.enabledInputs = ko.observableArray([]);

        this.lastSoundFileUrl = ko.observable();

        // this reloads list of meta words from server
        // once batchSize or/and start change
        ko.computed(function() {

            $.getJSON(baseUrl).done(function(response) {
                if (response instanceof Array) {
                    for (var i = 0; i < response.length; i++) {
                        wrapArrays(response[i]);
                    }
                    // set metawords
                    this.metawords(response);
                } else {
                    // TODO: handle error
                    // response is not array?
                }

            }.bind(this)).fail(function(respones) {
                // TODO: handle error
            });
        }, this);

        this.getNewMetaWord = function() {
            for (var i = 0; i < this.metawords().length; i++) {
                if (this.metawords()[i]['metaword_id'] === 'new') {
                    return this.metawords()[i];
                }
            }
            return null;
        };

        this.addNewMetaWord = function() {
            // only one new word is allowed
            if (!this.getNewMetaWord()) {
                this.metawords.unshift(newEmptyMetaWord());
            }
        }.bind(this);

        this.saveTextValue = function(type, metaword, event) {
            if (event.target.value) {
                var value = new model.TextValue(type, event.target.value);
                this.saveValue(value, metaword);
            }
        }.bind(this);

        this.saveWordSoundValue = function(metaword, value) {
            this.saveValue(value, metaword);
        }.bind(this);

        this.saveValue = function(value, metaword) {

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
                if(value instanceof model.WordSoundValue) {
                    obj[value.type] = [];
                    obj[value.type].push({'name': value.name, 'content': value.content, 'type': value.mime });
                } else if (value instanceof model.TextValue) {
                    obj[value.type] = [];
                    obj[value.type].push({'content': value.content});
                } else {
                    console.error('Value type is not supported!');
                    return;
                }

            $.ajax({
                contentType: 'application/json',
                data: JSON.stringify(obj),
                dataType: 'json',
                success: function(response) {
                    if (updateId) {
                        metaword.client_id = response.client_id;
                        metaword.metaword_id = response.metaword_id;
                        metaword.metaword_client_id = response.metaword_client_id;
                    }
                    metaword[value.type](response[value.type]);
                    this.metawords.valueHasMutated();
                }.bind(this),
                error: function() {
                    // TODO: Error handling

                }.bind(this),
                processData: false,
                type: 'POST',
                url: baseUrl
            });

            this.disableInput(metaword, value.type);

        }.bind(this);

        this.addValue = function(item, type) {
            if (!this.isInputEnabled(item, type)) {
                this.enabledInputs.push({ 'metaword_id': item.metaword_id, 'type': type });
            }
        }.bind(this);

        this.removeValue = function(metaword, type, obj, event) {

            var url = baseUrl + encodeURIComponent(currentId) + '/' + encodeURIComponent(obj.id);

            $.ajax({
                contentType: 'application/json',
                'data': JSON.stringify(obj),
                dataType: 'json',
                success: function(response) {
                    this.metaWordsRemoveValue(metaword, type, obj);
                }.bind(this),
                error: function() {
                    // TODO: Error handling

                }.bind(this),
                processData: false,
                type: 'DELETE',
                url: url
            });
        }.bind(this);

        this.removeWord = function(obj, event) {

            if (obj.metaword_id !== 'new') {
                var url = baseUrl + encodeURIComponent(currentId) + '/' + encodeURIComponent(obj.metaword_id);
                $.ajax({
                    contentType: 'application/json',
                    data: JSON.stringify(obj),
                    dataType: 'json',
                    success: function(response) {
                        // remove from list after server confirmed successful removal
                        this.metawords.remove(function(i) {
                            return i.metaword_id === obj.metaword_id && obj.dict_id;
                        });
                    }.bind(this),
                    error: function() {
                        // TODO: Error handling

                    }.bind(this),
                    processData: false,
                    type: 'DELETE',
                    url: url
                });
            } else {
                this.metawords.remove(function(i) {
                    return i.metaword_id === 'new';
                });
            }

        }.bind(this);

        this.isInputEnabled = function(item, type) {
            for (var i = 0; i < this.enabledInputs().length; i++) {
                var checkItem = this.enabledInputs()[i];
                if (checkItem.metaword_id === item.metaword_id && type === checkItem.type) {
                    return true;
                }
            }
            return false;
        }.bind(this);

        this.disableInput = function(item, type) {
            this.enabledInputs.remove(function(i) {
                return i.metaword_id === item.metaword_id && i.type === type;
            });
        }.bind(this);

        this.playSound = function(entry, event) {
            if (entry.url) {
                this.lastSoundFileUrl(entry.url);
            }
        }.bind(this);

        this.metaWordsRemoveValue = function(metaword, type, obj) {
            this.metawords.remove(function(currentMetaword) {
                if (currentMetaword.metaword_id === metaword.metaword_id) {
                    if (type in currentMetaword) {
                        var values = currentMetaword[type];
                        for (var i = 0; i < values.length; i++) {
                            var value = values[i];
                            if (value.id === obj.id) {
                                return true;
                            }
                        }
                    }
                }
                return false;
            });


        }.bind(this);

        this.showParadigms = function(metaword, event) {

        }.bind(this);

        this.showEtymology = function(metaword, event) {

        }.bind(this);

    };

    ko.applyBindings(new viewModel());
});