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
        'URIjs': 'lib/URIjs',
        'jquery': 'jquery-2.1.1.min',
        'bootstrap': 'bootstrap.min',
        'knockout': 'knockout-3.2.0',
        'knockstrap': 'knockstrap.min',
        'wavesurfer': 'wavesurfer'
    },
    'map': {
        '*': {
            'jQuery': 'jquery'
        }
    }
});

require(['model', 'jquery', 'ko', 'URIjs/URI', 'knockstrap', 'bootstrap'], function(model, $, ko, uri) {

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

        this.pageIndex = ko.observable(1);
        this.pageSize = ko.observable(20);
        this.pageCount = ko.observable(10);

        // this reloads list of meta words from server
        // once batchSize or/and start change
        ko.computed(function() {
            var url = new uri(baseUrl);
            url.addQuery('offset', (this.pageIndex() - 1) * this.pageSize());
            url.addQuery('size', this.pageSize());
            $.getJSON(url.toString()).done(function(response) {
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

        this.getPage = function(pageIndex) {
            this.pageIndex(parseInt(pageIndex))
        }.bind(this);

        ko.computed(function() {
            var url = $('#getDictionaryStatUrl').data('lingvodoc');
            $.getJSON(url).done(function(response) {
                if (response.metawords) {
                    var pageCount = Math.ceil(parseInt(response.metawords) / this.pageSize());
                    this.pageCount(pageCount);
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

        // etymology modal window
        this.etymologyModalVisible = ko.observable(false);
        this.etymologyWords = ko.observableArray([]);
        this.etymologySoundUrl = ko.observable();
        this.showEtymology = function(metaword, event) {
            this.etymologyModalVisible(false);
            var url = new uri(baseUrl);
            url.directory(url.directory() + '/' + metaword.metaword_client_id + '/' + metaword.metaword_id)
            url.filename('etymology');

            $.getJSON(url.toString()).done(function(response) {
                this.etymologyWords(response);
                this.etymologyModalVisible(true);
            }.bind(this)).fail(function(response) {

            }.bind(this));
        }.bind(this);

        this.playEtymologySound = function(entry, event) {
            if (entry.url) {
                this.etymologySoundUrl(entry.url);
            }
        }.bind(this);

        this.paradigmsModalVisible = ko.observable(false);
        this.paradigms = ko.observableArray([]);
        this.paradigmSoundUrl = ko.observable();
        this.showParadigms = function(metaword, event) {
            this.paradigmsModalVisible(false);
            var url = new uri(baseUrl);

            console.log(baseUrl);
            console.log(url.directory());

            url.directory(url.directory() + '/' + metaword.metaword_client_id + '/' + metaword.metaword_id)
            url.filename('metaparadigms');

            console.log(url.toString());

            $.getJSON(url.toString()).done(function(response) {
                this.paradigms(response);
                this.paradigmsModalVisible(true);
            }.bind(this)).fail(function(response) {

            }.bind(this));
        }.bind(this);

        this.playParadigmSound = function(entry, event) {
            if (entry.url) {
                this.paradigmSoundUrl(entry.url);
            }
        }.bind(this);
    };
    ko.applyBindings(new viewModel());


    //body: { name: 'etymology_modal', data: {'words': paradigms, 'soundUrl': paradigmSoundUrl, 'playSound': playParadigmSound} },
});