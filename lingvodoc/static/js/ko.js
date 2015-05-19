'use strict';

define(['model', 'knockout', 'wavesurfer', 'upload'], function(model, ko, wavesurfer, upload){
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
                            var wordSound = new model.WordSoundValue(file.name, b64file, file.type);
                            valueUnwrapped(wordSound);
                        }
                    }
                }
            };
            var reader = new upload(options);
            reader.bindDragAndDrop(element);
        }
    };

    ko.bindingHandlers.inputFiles = {
        init: function (element, valueAccessor, allBindingsAccessor,
                        viewModel, bindingContext) {
            var value = valueAccessor();
            var valueUnwrapped = ko.unwrap(value);

            var options = {
                'onload': function(e, file) {
                    if (e.target.result) {
                        var b64file = btoa(e.target.result);
                        if (typeof valueUnwrapped == 'function') {
                            var wordSound = new model.WordSoundValue(file.name, b64file, file.type);
                            valueUnwrapped(wordSound);
                        }
                    }
                }
            };
            var reader = new upload(options);
            reader.bindInputFiles(element);
        }
    };

    ko.bindingHandlers.wavesurfer = {
        init: function(element, valueAccessor, allBindingsAccessor,
                       viewModel, bindingContext) {

            var value = valueAccessor();
            var valueUnwrapped = ko.unwrap(value);

            var wsurfer = Object.create(wavesurfer);

            wsurfer.init({
                container: element,
                waveColor: 'black',
                progressColor: 'red'
            });


            // Regions
            if (wsurfer.enableDragSelection) {
                wsurfer.enableDragSelection({
                    color: 'rgba(0, 255, 0, 0.1)'
                });
            }

            wsurfer.on('ready', function () {
                wsurfer.play();
            });

            wsurfer.on('region-click', function(region, event) {
                if (typeof valueUnwrapped.selectRegion == 'function') {
                    valueUnwrapped.selectRegion(region);
                }
            });

            wsurfer.on('region-dblclick', function(region, event) {
                region.remove(region);
            });

            ko.utils.domData.set(element, 'wsurfer', wsurfer);
        },
        update: function(element, valueAccessor, allBindingsAccessor,
                         viewModel, bindingContext) {

            var value = valueAccessor();
            var valueUnwrapped = ko.unwrap(value);

            var wsurfer = ko.utils.domData.get(element, 'wsurfer');
            if (typeof wsurfer != 'undefined' && valueUnwrapped) {
                wsurfer.load(valueUnwrapped.url());
            }
        }
    };

    return ko;
});
