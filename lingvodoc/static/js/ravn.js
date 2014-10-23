'use strict';

require.config({
    baseUrl: '/static/js/',
    shim: {
        'bootstrap' : ['jquery']
    },
    paths: {
        'jquery': 'jquery-2.1.1.min',
        'bootstrap': 'bootstrap.min',
        'knockout': 'knockout-3.2.0'
    }
});

require(['jquery', 'knockout','bootstrap'], function($, ko, bootstrap) {

    var jQuery = $;
    var backendBaseURL = document.URL;

    function encodeGetParams(data) {
        return Object.keys(data).map(function(key) {
            return [key, data[key]].map(encodeURIComponent).join("=");
        }).join("&");
    }

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
        var newWord = {'id': 'new', 'transcriptions': [], 'translations': [], 'addedByUser': true};
        wrapArrays(newWord);
        return newWord;
    };

    var viewModel = function() {

        this.start = ko.observable(15);
        this.batchSize = ko.observable(15);
        this.dictId = ko.observable(1);

        // list of meta words loaded from ajax backends
        this.list = ko.observableArray([]);

        // list of enabled text inputs in table
        this.enabledInputs = ko.observableArray([]);

        // this reloads list of meta words from server
        // once batchSize or/and start change
        ko.computed(function() {

            var url = document.URL + '/metawords/?' + encodeGetParams({
                'batch_size': this.batchSize(),
                'start': this.start()
            });

            $.getJSON(url).done(function(response) {

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
                if (this.list()[i]['id'] === 'new') {
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

        this.saveValue = function(type, data, event) {

            var updateId = false;
            var newValue = event.target.value;

            if (newValue) {
                var obj = {};
                // when edit existing word, copy id and dict_id
                if (data.id !== 'new') {
                    obj['id'] = data.id;
                    obj['dict_id'] = data.dict_id;
                } else {
                    updateId = true; // update id after word is saved
                    obj['dict_id'] = this.dictId();
                }

                obj[type] = [];
                obj[type].push([{ 'content': newValue }]);

                $.ajax({
                    contentType: 'application/json',
                    data: JSON.stringify(obj),
                    dataType: 'json',
                    success: function(response) {
                        if (updateId) {
                            data.id = response.id;
                            data.dict_id = response.dict_id
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
                this.enabledInputs.push({ 'id': item.id, 'type': type });
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

            if (obj.id !== 'new') {
                $.ajax({
                    contentType: 'application/json',
                    data: JSON.stringify(obj),
                    dataType: 'json',
                    success: function(response) {

                        // remove from list after server confirmed successful removal
                        this.list.remove(function(i) {
                            return i.id === obj.id && obj.dict_id;
                        });
                    }.bind(this),
                    error: function() {
                        // TODO: Error handling

                    }.bind(this),
                    processData: false,
                    type: 'DELETE',
                    url: backendBaseURL + '/save/' + this.dictId() + '/' + obj.id
                });
            } else {
                this.list.remove(function(i) {
                    return i.id === 'new';
                });
            }

        }.bind(this);

        this.isInputEnabled = function(item, type) {
            for (var i = 0; i < this.enabledInputs().length; i++) {
                var checkItem = this.enabledInputs()[i];
                if (checkItem.id === item.id && type === checkItem.type) {
                    return true;
                }
            }
            return false;
        }.bind(this);

        this.disableInput = function(item, type) {
            this.enabledInputs.remove(function(i) {
                return i.id === item.id && i.type === type;
            });
        }.bind(this);
    };

    ko.applyBindings(new viewModel());

});