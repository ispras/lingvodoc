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
    var backendBaseURL = document.URL;

    // define some custom bindings for KO
    ko.bindingHandlers.dragndropUpload = {
        init: function (element, valueAccessor, allBindingsAccessor,
                        viewModel, bindingContext) {
            var value = valueAccessor();
            var valueUnwrapped = ko.unwrap(value);

            var options = {
                'onload': function(e) {
                    if (e.target.result) {
                        var b64file = btoa(e.target.result);
                        if (typeof valueUnwrapped == 'function') {
                            valueUnwrapped(b64file);
                        }
                    }
                },
                'onloadstart': function() {
                    console.log('upload started!');
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

    var encodeGetParams = function(data) {
        return Object.keys(data).map(function(key) {
            return [key, data[key]].map(encodeURIComponent).join("=");
        }).join("&");
    };

    var wrapArrays = function(word) {

        // FIXME: just a placeholder!!!
        if (!('sounds' in word)) {
            word.sounds = [];
        }

        for (var prop in word) {
            if (word.hasOwnProperty(prop)) {
                if (word[prop] instanceof Array) {
                    word[prop] = ko.observableArray(word[prop]);
                }
            }
        }
    };

    var newEmptyMetaWord = function() {
        var newWord = {'metaword_id': 'new', 'transcriptions': [], 'translations': [], 'sounds': [], 'addedByUser': true};
        wrapArrays(newWord);
        return newWord;
    };

    var viewModel = function() {

        this.start = ko.observable(15);
        this.batchSize = ko.observable(15);

        // list of meta words loaded from ajax backends
        this.list = ko.observableArray([]);

        // list of enabled text inputs in table
        this.enabledInputs = ko.observableArray([]);

        this.lastSoundFileUrl = ko.observable();

        // this reloads list of meta words from server
        // once batchSize or/and start change
        ko.computed(function() {

            var url = document.URL + '/metawords/?' + encodeGetParams({
                'batch_size': this.batchSize(),
                'start': this.start()
            });

            $.getJSON(url).done(function(response) {
                console.log(response);
                if (response instanceof Array) {
                    for (var i = 0; i < response.length; i++) {
                        wrapArrays(response[i]);
                    }
                    // set list
                    this.list(response);
                } else {
                    // TODO: handle error
                    // response is not array?
                }

            }.bind(this)).fail(function(respones) {
                // TODO: handle error
            });
        }, this);

        this.getNewMetaWord = function() {
            for (var i = 0; i < this.list().length; i++) {
                if (this.list()[i]['metaword_id'] === 'new') {
                    return this.list()[i];
                }
            }
            return null;
        };

        this.addNewMetaWord = function() {
            // only one new word is allowed
            if (this.getNewMetaWord() === null) {
                this.list.unshift(newEmptyMetaWord());
            }
        }.bind(this);

        this.saveSound = function(data, sound) {
            // XXX: What a weird way to handle this
            var event = {'target': {
               'value': sound
            }};
            this.saveValue('sounds', data, event);
        }.bind(this);

        this.saveValue = function(type, data, event) {

            var updateId = false;
            var newValue = event.target.value;

            if (newValue) {
                var obj = {};
                // when edit existing word, copy id and dict_id
                if (data.metaword_id !== 'new') {
//                    obj['id'] = data.id;
//                    obj['dict_id'] = data.dict_id;
                    obj['client_id'] = data.client_id;
                    obj['metaword_id'] = data.metaword_id;
                    obj['metaword_client_id'] = data.metaword_client_id;

                } else {
                    updateId = true; // update id after word is saved
                }

                obj[type] = [];
                obj[type].push({ 'content': newValue });
                console.log(obj);

                $.ajax({
                    contentType: 'application/json',
                    data: JSON.stringify(obj),
                    dataType: 'json',
                    success: function(response) {
                        if (updateId) {
                            data.client_id = response.client_id;
                            data.metaword_id = response.metaword_id;
                            data.metaword_client_id = response.metaword_client_id;
                        }
                        data[type].push({ 'content': newValue });
                        this.list.valueHasMutated();
                    }.bind(this),
                    error: function() {
                        console.log(obj);
                        // TODO: Error handling

                    }.bind(this),
                    processData: false,
                    type: 'POST',
                    url: backendBaseURL + '/save/'
                });
            }

            this.disableInput(data, type);

        }.bind(this);

        this.addValue = function(item, type) {
            if (!this.isInputEnabled(item, type)) {
                console.log(item);
                this.enabledInputs.push({ 'metaword_id': item.metaword_id, 'type': type });
            }
        }.bind(this);

        this.removeValue = function(type, obj, event) {
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
                url: backendBaseURL + '/save/' + obj.id
            });
        }.bind(this);

        this.removeWord = function(obj, event) {

            if (obj.metaword_id !== 'new') {
                $.ajax({
                    contentType: 'application/json',
                    data: JSON.stringify(obj),
                    dataType: 'json',
                    success: function(response) {

                        // remove from list after server confirmed successful removal
                        this.list.remove(function(i) {
                            return i.metaword_id === obj.metaword_id && obj.dict_id;
                        });
                    }.bind(this),
                    error: function() {
                        // TODO: Error handling

                    }.bind(this),
                    processData: false,
                    type: 'DELETE',
                    url: backendBaseURL + '/save/' +  obj.id
                });
            } else {
                this.list.remove(function(i) {
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
    };

    ko.applyBindings(new viewModel());

});