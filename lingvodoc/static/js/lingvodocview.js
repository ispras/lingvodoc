'use strict';

require.config({
    'baseUrl': '/static/js/',
    'shim': {
        'bootstrap' : ['jquery'],
        'wavesurfer': {
            'exports': 'WaveSurfer'
        },
        'knockstrap': ['jquery', 'bootstrap', 'knockout']
    },
    'paths': {
        'jquery': 'jquery-2.1.1.min',
        'bootstrap': 'bootstrap.min',
        'knockout': 'knockout-3.2.0',
        'knockstrap': 'knockstrap.min',
        'wavesurfer': 'wavesurfer.min'
    },
    'map': {
        '*': {
            'jQuery': 'jquery'
        }
    }
});

require(['model', 'jquery', 'ko', 'knockstrap', 'bootstrap'], function(model, $, ko) {

    var wrapArrays = function(word) {
        for (var prop in word) {
            if (word.hasOwnProperty(prop)) {
                if (word[prop] instanceof Array) {
                    word[prop] = ko.observableArray(word[prop]);
                }
            }
        }
    };

    var viewModel = function() {

        var baseUrl = $('#getMetaWordsUrl').data('lingvodoc');

        // list of meta words loaded from ajax backends
        this.metawords = ko.observableArray([]);

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

        this.playSound = function(entry, event) {
            if (entry.url) {
                this.lastSoundFileUrl(entry.url);
            }
        }.bind(this);

        this.showParadigms = function(metaword, event) {

        }.bind(this);

        this.showEtymology = function(metaword, event) {

        }.bind(this);

    };
    ko.applyBindings(new viewModel());
});