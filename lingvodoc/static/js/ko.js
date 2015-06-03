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
    
    ko.bindingHandlers.markup = {
        init: function(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {

            var value = valueAccessor();
            var valueUnwrapped = ko.unwrap(value);
            var wsurfer = Object.create(wavesurfer);


            console.log(element);

            var waveformElements = element.getElementsByClassName('markup-waveform');
            if (waveformElements.length < 1) {
                throw 'Container for waveform not found';
            }

            wsurfer.init({
                container: waveformElements[0],
                waveColor: 'black',
                progressColor: 'red'
            });


            // Regions
            if (wsurfer.enableDragSelection) {
                wsurfer.enableDragSelection({
                    color: 'rgba(0, 255, 0, 0.1)'
                });
            }

            // play file on load
            wsurfer.on('ready', function () {
                //wsurfer.play();
            });

            // regions events
            wsurfer.on('region-click', function(region, event) {
                if (typeof valueUnwrapped.selectRegion == 'function') {
                    valueUnwrapped.selectRegion(region);
                }
            });

            wsurfer.on('region-dblclick', function(region, event) {
                region.remove(region);
            });

            // bind controls
            [].forEach.call(element.querySelectorAll('[data-action]'), function (el) {
                el.addEventListener('click', function (e) {
                    var action = e.currentTarget.dataset.action;

                    switch (action) {
                        case 'play':
                            wsurfer.play();
                            break;
                        case 'pause':
                            wsurfer.pause();
                            break;
                        case 'backward':
                            wsurfer.skipBackward();
                            break;
                        case 'forward':
                            wsurfer.skipForward();
                            break;
                    }
                });
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
