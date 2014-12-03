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

require(['jquery', 'knockout','bootstrap', 'upload', 'wavesurfer'], function($, ko, bootstrap, upload, wavesurfer) {

    var jQuery = $;


    var Value = function() {
        this.type = 'abstract';
    };

    var TextValue = function(type, content) {
        this.type = type;
        this.content = content;
    };
    TextValue.prototype = new Value();

    var WordSoundValue = function(name, content, mime) {
        this.type = 'sounds';
        this.name = name;
        this.mime = mime;
        this.content = content;
    };
    WordSoundValue.prototype = new Value();


    // define some custom bindings for KO
    ko.bindingHandlers.dragndropUpload = {
        init: function (element, valueAccessor, allBindingsAccessor,
                        viewModel, bindingContext) {
            var value = valueAccessor();
            var valueUnwrapped = ko.unwrap(value);

            var options = {
                'onload': function(e, file) {
                    if (e.target.result) {
                        var b64file = btoa(e.target.result);
                        if (typeof valueUnwrapped == 'function') {
                            var wordSound = new WordSoundValue(file.name, b64file, file.type);
                            valueUnwrapped(wordSound);
                        }
                    }
                },
                'onloadstart': function() {

                }
            };
            var reader = new upload(options);
            reader.bindDragAndDrop(element);
        }
    };

    ko.bindingHandlers.wavesurfer = {
        init: function(element, valueAccessor, allBindingsAccessor,
                        viewModel, bindingContext) {

            var value = valueAccessor();
            var valueUnwrapped = ko.unwrap(value);

            var wsurfer = Object.create(WaveSurfer);

            wsurfer.init({
                container: element,
                waveColor: 'black',
                progressColor: 'red'
            });

            wsurfer.on('ready', function () {
                wsurfer.play();
            });

            ko.utils.domData.set(element, 'wsurfer', wsurfer);
        },
        update: function(element, valueAccessor, allBindingsAccessor,
                         viewModel, bindingContext) {

            var value = valueAccessor();
            var valueUnwrapped = ko.unwrap(value);

            var wsurfer = ko.utils.domData.get(element, 'wsurfer');
            if (typeof wsurfer != 'undefined' && valueUnwrapped) {
                wsurfer.load(valueUnwrapped);
            }
        }
    };

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

        //this.start = ko.observable(15);
        //this.batchSize = ko.observable(15);

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

        this.saveSound = function(data, wordSound) {
            // XXX: What a weird way to handle this
            var event = {'target': {
               'value': wordSound
            }};
            this.saveValue('sounds', data, event);
        }.bind(this);


        this.saveTextValue = function(type, metaword, event) {
            if (event.target.value) {
                var value = new TextValue(type, event.target.value);
                this.saveValue(value, metaword);
            }
        }.bind(this);

        this.saveWordSoundValue = function(metaword, value) {
            this.saveValue(value, metaword);
        }.bind(this);;



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
                if(value instanceof WordSoundValue) {
                    obj[value.type] = [];
                    obj[value.type].push({'name': value.name, 'content': value.content, 'type': value.mime });
                } else if (value instanceof TextValue) {
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

        this.removeValue = function(type, obj, event) {

            var url = baseUrl + encodeURIComponent(currentId) + '/' + encodeURIComponent(obj.id);
            $.ajax({
                contentType: 'application/json',
                data: {
                    'data': JSON.stringify(obj)
                },
                dataType: 'json',
                success: function(response) {

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

                var url = baseUrl + encodeURIComponent(currentId) + '/' + encodeURIComponent(obj.id);
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

    };




    window.viewModel = new viewModel();
    ko.applyBindings(window.viewModel);
});