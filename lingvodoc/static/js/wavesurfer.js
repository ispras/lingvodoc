'use strict';

var WaveSurfer = {
    defaultParams: {
        height: 128,
        waveColor: '#999',
        progressColor: '#555',
        cursorColor: '#333',
        cursorWidth: 1,
        skipLength: 2,
        minPxPerSec: 20,
        pixelRatio: window.devicePixelRatio,
        fillParent: true,
        scrollParent: false,
        hideScrollbar: false,
        normalize: false,
        audioContext: null,
        container: null,
        dragSelection: true,
        loopSelection: true,
        audioRate: 1,
        interact: true,
        splitChannels: false,
        renderer: 'Canvas',
        backend: 'WebAudio',
        mediaType: 'audio'
    },

    init: function (params) {
        // Extract relevant parameters (or defaults)
        this.params = WaveSurfer.util.extend({}, this.defaultParams, params);

        this.container = 'string' == typeof params.container ?
            document.querySelector(this.params.container) :
            this.params.container;

        if (!this.container) {
            throw new Error('Container element not found');
        }

        if (typeof this.params.mediaContainer == 'undefined') {
            this.mediaContainer = this.container;
        } else if (typeof this.params.mediaContainer == 'string') {
            this.mediaContainer = document.querySelector(this.params.mediaContainer);
        } else {
            this.mediaContainer = this.params.mediaContainer;
        }

        if (!this.mediaContainer) {
            throw new Error('Media Container element not found');
        }

        // Used to save the current volume when muting so we can
        // restore once unmuted
        this.savedVolume = 0;
        // The current muted state
        this.isMuted = false;
        // Will hold a list of event descriptors that need to be
        // cancelled on subsequent loads of audio
        this.tmpEvents = [];

        this.createDrawer();
        this.createBackend();
    },

    createDrawer: function () {
        var my = this;

        this.drawer = Object.create(WaveSurfer.Drawer[this.params.renderer]);
        this.drawer.init(this.container, this.params);

        this.drawer.on('redraw', function () {
            my.drawBuffer();
            my.drawer.progress(my.backend.getPlayedPercents());
        });

        // Click-to-seek
        this.drawer.on('click', function (e, progress) {
            setTimeout(function () {
                my.seekTo(progress);
            }, 0);
        });

        // Relay the scroll event from the drawer
        this.drawer.on('scroll', function (e) {
            my.fireEvent('scroll', e);
        });
    },

    createBackend: function () {
        var my = this;

        if (this.backend) {
            this.backend.destroy();
        }

        // Back compat
        if (this.params.backend == 'AudioElement') {
            this.params.backend = 'MediaElement';
        }

        if (this.params.backend == 'WebAudio' && !WaveSurfer.WebAudio.supportsWebAudio()) {
            this.params.backend = 'MediaElement';
        }

        this.backend = Object.create(WaveSurfer[this.params.backend]);
        this.backend.init(this.params);

        this.backend.on('finish', function () {
            my.fireEvent('finish');
        });

        this.backend.on('audioprocess', function (time) {
            my.fireEvent('audioprocess', time);
        });
    },

    restartAnimationLoop: function () {
        var my = this;
        var requestFrame = window.requestAnimationFrame ||
            window.webkitRequestAnimationFrame;
        var frame = function () {
            if (!my.backend.isPaused()) {
                my.drawer.progress(my.backend.getPlayedPercents());
                requestFrame(frame);
            }
        };
        frame();
    },

    getDuration: function () {
        return this.backend.getDuration();
    },

    getCurrentTime: function () {
        return this.backend.getCurrentTime();
    },

    play: function (start, end) {
        this.backend.play(start, end);
        this.restartAnimationLoop();
        this.fireEvent('play');
    },

    pause: function () {
        this.backend.pause();
        this.fireEvent('pause');
    },

    playPause: function () {
        this.backend.isPaused() ? this.play() : this.pause();
    },

    skipBackward: function (seconds) {
        this.skip(-seconds || -this.params.skipLength);
    },

    skipForward: function (seconds) {
        this.skip(seconds || this.params.skipLength);
    },

    skip: function (offset) {
        var position = this.getCurrentTime() || 0;
        var duration = this.getDuration() || 1;
        position = Math.max(0, Math.min(duration, position + (offset || 0)));
        this.seekAndCenter(position / duration);
    },

    seekAndCenter: function (progress) {
        this.seekTo(progress);
        this.drawer.recenter(progress);
    },

    seekTo: function (progress) {
        var paused = this.backend.isPaused();
        // avoid small scrolls while paused seeking
        var oldScrollParent = this.params.scrollParent;
        if (paused) {
            this.params.scrollParent = false;
        }
        this.backend.seekTo(progress * this.getDuration());
        this.drawer.progress(this.backend.getPlayedPercents());

        if (!paused) {
            this.backend.pause();
            this.backend.play();
        }
        this.params.scrollParent = oldScrollParent;
        this.fireEvent('seek', progress);
    },

    stop: function () {
        this.pause();
        this.seekTo(0);
        this.drawer.progress(0);
    },

    /**
     * Set the playback volume.
     *
     * @param {Number} newVolume A value between 0 and 1, 0 being no
     * volume and 1 being full volume.
     */
    setVolume: function (newVolume) {
        this.backend.setVolume(newVolume);
    },

    /**
     * Set the playback rate.
     *
     * @param {Number} rate A positive number. E.g. 0.5 means half the
     * normal speed, 2 means double speed and so on.
     */
    setPlaybackRate: function (rate) {
        this.backend.setPlaybackRate(rate);
    },

    /**
     * Toggle the volume on and off. It not currenly muted it will
     * save the current volume value and turn the volume off.
     * If currently muted then it will restore the volume to the saved
     * value, and then rest the saved value.
     */
    toggleMute: function () {
        if (this.isMuted) {
            // If currently muted then restore to the saved volume
            // and update the mute properties
            this.backend.setVolume(this.savedVolume);
            this.isMuted = false;
        } else {
            // If currently not muted then save current volume,
            // turn off the volume and update the mute properties
            this.savedVolume = this.backend.getVolume();
            this.backend.setVolume(0);
            this.isMuted = true;
        }
    },

    toggleScroll: function () {
        this.params.scrollParent = !this.params.scrollParent;
        this.drawBuffer();
    },

    toggleInteraction: function () {
        this.params.interact = !this.params.interact;
    },

    drawBuffer: function () {
        var nominalWidth = Math.round(
            this.getDuration() * this.params.minPxPerSec * this.params.pixelRatio
        );
        var parentWidth = this.drawer.getWidth();
        var width = nominalWidth;

        // Fill container
        if (this.params.fillParent && (!this.params.scrollParent || nominalWidth < parentWidth)) {
            width = parentWidth;
        }

        var peaks = this.backend.getPeaks(width);
        this.drawer.drawPeaks(peaks, width);
        this.fireEvent('redraw', peaks, width);
    },

    /**
     * Internal method.
     */
    loadArrayBuffer: function (arraybuffer) {
        this.decodeArrayBuffer(arraybuffer, function (data) {
            this.loadDecodedBuffer(data);
        }.bind(this));
    },

    /**
     * Directly load an externally decoded AudioBuffer.
     */
    loadDecodedBuffer: function (buffer) {
        this.backend.load(buffer);
        this.drawBuffer();
        this.fireEvent('ready');
    },

    /**
     * Loads audio data from a Blob or File object.
     *
     * @param {Blob|File} blob Audio data.
     */
    loadBlob: function (blob) {
        var my = this;
        // Create file reader
        var reader = new FileReader();
        reader.addEventListener('progress', function (e) {
            my.onProgress(e);
        });
        reader.addEventListener('load', function (e) {
            my.loadArrayBuffer(e.target.result);
        });
        reader.addEventListener('error', function () {
            my.fireEvent('error', 'Error reading file');
        });
        reader.readAsArrayBuffer(blob);
        this.empty();
    },

    /**
     * Loads audio and rerenders the waveform.
     */
    load: function (url, peaks) {
        switch (this.params.backend) {
            case 'WebAudio':
                return this.loadBuffer(url);
            case 'MediaElement':
                return this.loadMediaElement(url, peaks);
        }
    },

    /**
     * Loads audio using Web Audio buffer backend.
     */
    loadBuffer: function (url) {
        this.empty();
        // load via XHR and render all at once
        return this.getArrayBuffer(url, this.loadArrayBuffer.bind(this));
    },

    loadMediaElement: function (url, peaks) {
        this.empty();
        this.backend.load(url, this.mediaContainer, peaks);

        this.tmpEvents.push(
            this.backend.once('canplay', (function () {
                this.drawBuffer();
                this.fireEvent('ready');
            }).bind(this)),

            this.backend.once('error', (function (err) {
                this.fireEvent('error', err);
            }).bind(this))
        );


        // If no pre-decoded peaks provided, attempt to download the
        // audio file and decode it with Web Audio.
        if (!peaks && this.backend.supportsWebAudio()) {
            this.getArrayBuffer(url, (function (arraybuffer) {
                this.decodeArrayBuffer(arraybuffer, (function (buffer) {
                    this.backend.buffer = buffer;
                    this.drawBuffer();
                }).bind(this));
            }).bind(this));
        }
    },

    decodeArrayBuffer: function (arraybuffer, callback) {
        this.backend.decodeArrayBuffer(
            arraybuffer,
            this.fireEvent.bind(this, 'decoded'),
            this.fireEvent.bind(this, 'error', 'Error decoding audiobuffer')
        );
        this.tmpEvents.push(
            this.once('decoded', callback)
        );
    },

    getArrayBuffer: function (url, callback) {
        var my = this;
        var ajax = WaveSurfer.util.ajax({
            url: url,
            responseType: 'arraybuffer'
        });
        this.tmpEvents.push(
            ajax.on('progress', function (e) {
                my.onProgress(e);
            }),
            ajax.on('success', callback),
            ajax.on('error', function (e) {
                my.fireEvent('error', 'XHR error: ' + e.target.statusText);
            })
        );
        return ajax;
    },

    onProgress: function (e) {
        if (e.lengthComputable) {
            var percentComplete = e.loaded / e.total;
        } else {
            // Approximate progress with an asymptotic
            // function, and assume downloads in the 1-3 MB range.
            percentComplete = e.loaded / (e.loaded + 1000000);
        }
        this.fireEvent('loading', Math.round(percentComplete * 100), e.target);
    },

    /**
     * Exports PCM data into a JSON array and opens in a new window.
     */
    exportPCM: function (length, accuracy, noWindow) {
        length = length || 1024;
        accuracy = accuracy || 10000;
        noWindow = noWindow || false;
        var peaks = this.backend.getPeaks(length, accuracy);
        var arr = [].map.call(peaks, function (val) {
            return Math.round(val * accuracy) / accuracy;
        });
        var json = JSON.stringify(arr);
        if (!noWindow) {
            window.open('data:application/json;charset=utf-8,' +
                encodeURIComponent(json));
        }
        return json;
    },

    clearTmpEvents: function () {
        this.tmpEvents.forEach(function (e) {
            e.un();
        });
    },

    /**
     * Display empty waveform.
     */
    empty: function () {
        if (!this.backend.isPaused()) {
            this.stop();
            this.backend.disconnectSource();
        }
        this.clearTmpEvents();
        this.drawer.progress(0);
        this.drawer.setWidth(0);
        this.drawer.drawPeaks({length: this.drawer.getWidth()}, 0);
    },

    /**
     * Remove events, elements and disconnect WebAudio nodes.
     */
    destroy: function () {
        this.fireEvent('destroy');
        this.clearTmpEvents();
        this.unAll();
        this.backend.destroy();
        this.drawer.destroy();
    }
};

WaveSurfer.create = function (params) {
    var wavesurfer = Object.create(WaveSurfer);
    wavesurfer.init(params);
    return wavesurfer;
};

WaveSurfer.util = {
    extend: function (dest) {
        var sources = Array.prototype.slice.call(arguments, 1);
        sources.forEach(function (source) {
            Object.keys(source).forEach(function (key) {
                dest[key] = source[key];
            });
        });
        return dest;
    },

    getId: function () {
        return 'wavesurfer_' + Math.random().toString(32).substring(2);
    },

    ajax: function (options) {
        var ajax = Object.create(WaveSurfer.Observer);
        var xhr = new XMLHttpRequest();
        var fired100 = false;

        xhr.open(options.method || 'GET', options.url, true);
        xhr.responseType = options.responseType || 'json';

        xhr.addEventListener('progress', function (e) {
            ajax.fireEvent('progress', e);
            if (e.lengthComputable && e.loaded == e.total) {
                fired100 = true;
            }
        });

        xhr.addEventListener('load', function (e) {
            if (!fired100) {
                ajax.fireEvent('progress', e);
            }
            ajax.fireEvent('load', e);

            if (200 == xhr.status || 206 == xhr.status) {
                ajax.fireEvent('success', xhr.response, e);
            } else {
                ajax.fireEvent('error', e);
            }
        });

        xhr.addEventListener('error', function (e) {
            ajax.fireEvent('error', e);
        });

        xhr.send();
        ajax.xhr = xhr;
        return ajax;
    }
};


/* Observer */
WaveSurfer.Observer = {
    /**
     * Attach a handler function for an event.
     */
    on: function (event, fn) {
        if (!this.handlers) {
            this.handlers = {};
        }

        var handlers = this.handlers[event];
        if (!handlers) {
            handlers = this.handlers[event] = [];
        }
        handlers.push(fn);

        // Return an event descriptor
        return {
            name: event,
            callback: fn,
            un: this.un.bind(this, event, fn)
        };
    },

    /**
     * Remove an event handler.
     */
    un: function (event, fn) {
        if (!this.handlers) {
            return;
        }

        var handlers = this.handlers[event];
        if (handlers) {
            if (fn) {
                for (var i = handlers.length - 1; i >= 0; i--) {
                    if (handlers[i] == fn) {
                        handlers.splice(i, 1);
                    }
                }
            } else {
                handlers.length = 0;
            }
        }
    },

    /**
     * Remove all event handlers.
     */
    unAll: function () {
        this.handlers = null;
    },

    /**
     * Attach a handler to an event. The handler is executed at most once per
     * event type.
     */
    once: function (event, handler) {
        var my = this;
        var fn = function () {
            handler.apply(this, arguments);
            setTimeout(function () {
                my.un(event, fn);
            }, 0);
        };
        return this.on(event, fn);
    },

    fireEvent: function (event) {
        if (!this.handlers) {
            return;
        }
        var handlers = this.handlers[event];
        var args = Array.prototype.slice.call(arguments, 1);
        handlers && handlers.forEach(function (fn) {
            fn.apply(null, args);
        });
    }
};


/* Make the main WaveSurfer object an observer */
WaveSurfer.util.extend(WaveSurfer, WaveSurfer.Observer);

'use strict';

WaveSurfer.WebAudio = {
    scriptBufferSize: 256,
    PLAYING_STATE: 0,
    PAUSED_STATE: 1,
    FINISHED_STATE: 2,

    supportsWebAudio: function () {
        return !!(window.AudioContext || window.webkitAudioContext);
    },

    getAudioContext: function () {
        if (!WaveSurfer.WebAudio.audioContext) {
            WaveSurfer.WebAudio.audioContext = new (
                window.AudioContext || window.webkitAudioContext
            );
        }
        return WaveSurfer.WebAudio.audioContext;
    },

    getOfflineAudioContext: function (sampleRate) {
        if (!WaveSurfer.WebAudio.offlineAudioContext) {
            WaveSurfer.WebAudio.offlineAudioContext = new (
                window.OfflineAudioContext || window.webkitOfflineAudioContext
            )(1, 2, sampleRate);
        }
        return WaveSurfer.WebAudio.offlineAudioContext;
    },

    init: function (params) {
        this.params = params;
        this.ac = params.audioContext || this.getAudioContext();

        this.lastPlay = this.ac.currentTime;
        this.startPosition = 0;
        this.scheduledPause = null;

        this.states = [
            Object.create(WaveSurfer.WebAudio.state.playing),
            Object.create(WaveSurfer.WebAudio.state.paused),
            Object.create(WaveSurfer.WebAudio.state.finished)
        ];

        this.setState(this.PAUSED_STATE);

        this.createVolumeNode();
        this.createScriptNode();
        this.createAnalyserNode();
        this.setPlaybackRate(this.params.audioRate);
    },

    disconnectFilters: function () {
        if (this.filters) {
            this.filters.forEach(function (filter) {
                filter && filter.disconnect();
            });
            this.filters = null;
            // Reconnect direct path
            this.analyser.connect(this.gainNode);
        }
    },

    setState: function (state) {
        if (this.state !== this.states[state]) {
            this.state = this.states[state];
            this.state.init.call(this);
        }
    },

    // Unpacked filters
    setFilter: function () {
        this.setFilters([].slice.call(arguments));
    },

    /**
     * @param {Array} filters Packed ilters array
     */
    setFilters: function (filters) {
        // Remove existing filters
        this.disconnectFilters();

        // Insert filters if filter array not empty
        if (filters && filters.length) {
            this.filters = filters;

            // Disconnect direct path before inserting filters
            this.analyser.disconnect();

            // Connect each filter in turn
            filters.reduce(function (prev, curr) {
                prev.connect(curr);
                return curr;
            }, this.analyser).connect(this.gainNode);
        }

    },

    createScriptNode: function () {
        var my = this;
        var bufferSize = this.scriptBufferSize;
        if (this.ac.createScriptProcessor) {
            this.scriptNode = this.ac.createScriptProcessor(bufferSize);
        } else {
            this.scriptNode = this.ac.createJavaScriptNode(bufferSize);
        }
        this.scriptNode.connect(this.ac.destination);

        this.scriptNode.onaudioprocess = function () {
            var time = my.getCurrentTime();

            if (my.buffer && time > my.getDuration()) {
                my.setState(my.FINISHED_STATE);
            } else if (my.buffer && time >= my.scheduledPause) {
                my.setState(my.PAUSED_STATE);
            } else if (my.state === my.states[my.PLAYING_STATE]) {
                my.fireEvent('audioprocess', time);
            }
        };
    },

    createAnalyserNode: function () {
        this.analyser = this.ac.createAnalyser();
        this.analyser.connect(this.gainNode);
    },

    /**
     * Create the gain node needed to control the playback volume.
     */
    createVolumeNode: function () {
        // Create gain node using the AudioContext
        if (this.ac.createGain) {
            this.gainNode = this.ac.createGain();
        } else {
            this.gainNode = this.ac.createGainNode();
        }
        // Add the gain node to the graph
        this.gainNode.connect(this.ac.destination);
    },

    /**
     * Set the gain to a new value.
     *
     * @param {Number} newGain The new gain, a floating point value
     * between 0 and 1. 0 being no gain and 1 being maximum gain.
     */
    setVolume: function (newGain) {
        this.gainNode.gain.value = newGain;
    },

    /**
     * Get the current gain.
     *
     * @returns {Number} The current gain, a floating point value
     * between 0 and 1. 0 being no gain and 1 being maximum gain.
     */
    getVolume: function () {
        return this.gainNode.gain.value;
    },

    decodeArrayBuffer: function (arraybuffer, callback, errback) {
        if (!this.offlineAc) {
            this.offlineAc = this.getOfflineAudioContext(this.ac ? this.ac.sampleRate : 44100);
        }
        this.offlineAc.decodeAudioData(arraybuffer, (function (data) {
            callback(data);
        }).bind(this), errback);
    },

    /**
     * @returns {Array} Array of peaks or array of arrays of peaks.
     */
    getPeaks: function (length) {
        var sampleSize = this.buffer.length / length;
        var sampleStep = ~~(sampleSize / 10) || 1;
        var channels = this.buffer.numberOfChannels;
        var splitPeaks = [];
        var mergedPeaks = [];

        for (var c = 0; c < channels; c++) {
            var peaks = splitPeaks[c] = [];
            var chan = this.buffer.getChannelData(c);

            for (var i = 0; i < length; i++) {
                var start = ~~(i * sampleSize);
                var end = ~~(start + sampleSize);
                var max = 0;
                for (var j = start; j < end; j += sampleStep) {
                    var value = chan[j];
                    if (value > max) {
                        max = value;
                        // faster than Math.abs
                    } else if (-value > max) {
                        max = -value;
                    }
                }
                peaks[i] = max;

                if (c == 0 || max > mergedPeaks[i]) {
                    mergedPeaks[i] = max;
                }
            }
        }

        return this.params.splitChannels ? splitPeaks : mergedPeaks;
    },

    getPlayedPercents: function () {
        return this.state.getPlayedPercents.call(this);
    },

    disconnectSource: function () {
        if (this.source) {
            this.source.disconnect();
        }
    },

    destroy: function () {
        if (!this.isPaused()) {
            this.pause();
        }
        this.unAll();
        this.buffer = null;
        this.disconnectFilters();
        this.disconnectSource();
        this.gainNode.disconnect();
        this.scriptNode.disconnect();
        this.analyser.disconnect();
    },

    load: function (buffer) {
        this.startPosition = 0;
        this.lastPlay = this.ac.currentTime;
        this.buffer = buffer;
        this.createSource();
    },

    createSource: function () {
        this.disconnectSource();
        this.source = this.ac.createBufferSource();

        //adjust for old browsers.
        this.source.start = this.source.start || this.source.noteGrainOn;
        this.source.stop = this.source.stop || this.source.noteOff;

        this.source.playbackRate.value = this.playbackRate;
        this.source.buffer = this.buffer;
        this.source.connect(this.analyser);
    },

    isPaused: function () {
        return this.state !== this.states[this.PLAYING_STATE];
    },

    getDuration: function () {
        if (!this.buffer) {
            return 0;
        }
        return this.buffer.duration;
    },

    seekTo: function (start, end) {
        this.scheduledPause = null;

        if (start == null) {
            start = this.getCurrentTime();
            if (start >= this.getDuration()) {
                start = 0;
            }
        }
        if (end == null) {
            end = this.getDuration();
        }

        this.startPosition = start;
        this.lastPlay = this.ac.currentTime;

        if (this.state === this.states[this.FINISHED_STATE]) {
            this.setState(this.PAUSED_STATE);
        }

        return {start: start, end: end};
    },

    getPlayedTime: function () {
        return (this.ac.currentTime - this.lastPlay) * this.playbackRate;
    },

    /**
     * Plays the loaded audio region.
     *
     * @param {Number} start Start offset in seconds,
     * relative to the beginning of a clip.
     * @param {Number} end When to stop
     * relative to the beginning of a clip.
     */
    play: function (start, end) {
        // need to re-create source on each playback
        this.createSource();

        var adjustedTime = this.seekTo(start, end);

        start = adjustedTime.start;
        end = adjustedTime.end;

        this.scheduledPause = end;

        this.source.start(0, start, end - start);

        this.setState(this.PLAYING_STATE);
    },

    /**
     * Pauses the loaded audio.
     */
    pause: function () {
        this.scheduledPause = null;

        this.startPosition += this.getPlayedTime();
        this.source && this.source.stop(0);

        this.setState(this.PAUSED_STATE);
    },

    /**
     *   Returns the current time in seconds relative to the audioclip's duration.
     */
    getCurrentTime: function () {
        return this.state.getCurrentTime.call(this);
    },

    /**
     * Set the audio source playback rate.
     */
    setPlaybackRate: function (value) {
        value = value || 1;
        if (this.isPaused()) {
            this.playbackRate = value;
        } else {
            this.pause();
            this.playbackRate = value;
            this.play();
        }
    }
};

WaveSurfer.WebAudio.state = {};

WaveSurfer.WebAudio.state.playing = {
    init: function () {
    },
    getPlayedPercents: function () {
        var duration = this.getDuration();
        return (this.getCurrentTime() / duration) || 0;
    },
    getCurrentTime: function () {
        return this.startPosition + this.getPlayedTime();
    }
};

WaveSurfer.WebAudio.state.paused = {
    init: function () {
    },
    getPlayedPercents: function () {
        var duration = this.getDuration();
        return (this.getCurrentTime() / duration) || 0;
    },
    getCurrentTime: function () {
        return this.startPosition;
    }
};

WaveSurfer.WebAudio.state.finished = {
    init: function () {
        this.fireEvent('finish');
    },
    getPlayedPercents: function () {
        return 1;
    },
    getCurrentTime: function () {
        return this.getDuration();
    }
};

WaveSurfer.util.extend(WaveSurfer.WebAudio, WaveSurfer.Observer);

'use strict';

WaveSurfer.MediaElement = Object.create(WaveSurfer.WebAudio);

WaveSurfer.util.extend(WaveSurfer.MediaElement, {
    init: function (params) {
        this.params = params;

        // Dummy media to catch errors
        this.media = {
            currentTime: 0,
            duration: 0,
            paused: true,
            playbackRate: 1,
            play: function () {
            },
            pause: function () {
            }
        };

        this.mediaType = params.mediaType.toLowerCase();
        this.elementPosition = params.elementPosition;
    },

    load: function (url, container, peaks) {
        var my = this;

        var media = document.createElement(this.mediaType);
        media.controls = false;
        media.autoplay = false;
        media.preload = 'auto';
        media.src = url;

        media.addEventListener('error', function () {
            my.fireEvent('error', 'Error loading media element');
        });

        media.addEventListener('canplay', function () {
            my.fireEvent('canplay');
        });

        media.addEventListener('ended', function () {
            my.fireEvent('finish');
        });

        media.addEventListener('timeupdate', function () {
            my.fireEvent('audioprocess', my.getCurrentTime());
        });

        var prevMedia = container.querySelector(this.mediaType);
        if (prevMedia) {
            container.removeChild(prevMedia);
        }
        container.appendChild(media);

        this.media = media;
        this.peaks = peaks;
        this.onPlayEnd = null;
        this.buffer = null;
        this.setPlaybackRate(this.playbackRate);
    },

    isPaused: function () {
        return this.media.paused;
    },

    getDuration: function () {
        var duration = this.media.duration;
        if (duration >= Infinity) { // streaming audio
            duration = this.media.seekable.end();
        }
        return duration;
    },

    getCurrentTime: function () {
        return this.media.currentTime;
    },

    getPlayedPercents: function () {
        return (this.getCurrentTime() / this.getDuration()) || 0;
    },

    /**
     * Set the audio source playback rate.
     */
    setPlaybackRate: function (value) {
        this.playbackRate = value || 1;
        this.media.playbackRate = this.playbackRate;
    },

    seekTo: function (start) {
        if (start != null) {
            this.media.currentTime = start;
        }
        this.clearPlayEnd();
    },

    /**
     * Plays the loaded audio region.
     *
     * @param {Number} start Start offset in seconds,
     * relative to the beginning of a clip.
     * @param {Number} end End offset in seconds,
     * relative to the beginning of a clip.
     */
    play: function (start, end) {
        this.seekTo(start);
        this.media.play();
        end && this.setPlayEnd(end);
    },

    /**
     * Pauses the loaded audio.
     */
    pause: function () {
        this.media.pause();
        this.clearPlayEnd();
    },

    setPlayEnd: function (end) {
        var my = this;
        this.onPlayEnd = function (time) {
            if (time >= end) {
                my.pause();
                my.seekTo(end);
            }
        };
        this.on('audioprocess', this.onPlayEnd);
    },

    clearPlayEnd: function () {
        if (this.onPlayEnd) {
            this.un('audioprocess', this.onPlayEnd);
            this.onPlayEnd = null;
        }
    },

    getPeaks: function (length) {
        if (this.buffer) {
            return WaveSurfer.WebAudio.getPeaks.call(this, length);
        }
        return this.peaks || [];
    },

    getVolume: function () {
        return this.media.volume;
    },

    setVolume: function (val) {
        this.media.volume = val;
    },

    destroy: function () {
        this.pause();
        this.unAll();
        this.media.parentNode && this.media.parentNode.removeChild(this.media);
        this.media = null;
    }
});

//For backwards compatibility
WaveSurfer.AudioElement = WaveSurfer.MediaElement;

'use strict';

WaveSurfer.Drawer = {
    init: function (container, params) {
        this.container = container;
        this.params = params;

        this.width = 0;
        this.height = params.height * this.params.pixelRatio;

        this.lastPos = 0;

        this.createWrapper();
        this.createElements();
    },

    createWrapper: function () {
        this.wrapper = this.container.appendChild(
            document.createElement('wave')
        );

        this.style(this.wrapper, {
            display: 'block',
            position: 'relative',
            userSelect: 'none',
            webkitUserSelect: 'none',
            height: this.params.height + 'px'
        });

        if (this.params.fillParent || this.params.scrollParent) {
            this.style(this.wrapper, {
                width: '100%',
                overflowX: this.params.hideScrollbar ? 'hidden' : 'auto',
                overflowY: 'hidden'
            });
        }

        this.setupWrapperEvents();
    },

    handleEvent: function (e) {
        e.preventDefault();
        var bbox = this.wrapper.getBoundingClientRect();
        return ((e.clientX - bbox.left + this.wrapper.scrollLeft) / this.wrapper.scrollWidth) || 0;
    },

    setupWrapperEvents: function () {
        var my = this;

        this.wrapper.addEventListener('click', function (e) {
            var scrollbarHeight = my.wrapper.offsetHeight - my.wrapper.clientHeight;
            if (scrollbarHeight != 0) {
                // scrollbar is visible.  Check if click was on it
                var bbox = my.wrapper.getBoundingClientRect();
                if (e.clientY >= bbox.bottom - scrollbarHeight) {
                    // ignore mousedown as it was on the scrollbar
                    return;
                }
            }

            if (my.params.interact) {
                my.fireEvent('click', e, my.handleEvent(e));
            }
        });

        this.wrapper.addEventListener('scroll', function (e) {
            my.fireEvent('scroll', e);
        });
    },

    drawPeaks: function (peaks, length) {
        this.resetScroll();
        this.setWidth(length);
        this.drawWave(peaks);
    },

    style: function (el, styles) {
        Object.keys(styles).forEach(function (prop) {
            if (el.style[prop] != styles[prop]) {
                el.style[prop] = styles[prop];
            }
        });
        return el;
    },

    resetScroll: function () {
        if (this.wrapper !== null) {
            this.wrapper.scrollLeft = 0;
        }
    },

    recenter: function (percent) {
        var position = this.wrapper.scrollWidth * percent;
        this.recenterOnPosition(position, true);
    },

    recenterOnPosition: function (position, immediate) {
        var scrollLeft = this.wrapper.scrollLeft;
        var half = ~~(this.wrapper.clientWidth / 2);
        var target = position - half;
        var offset = target - scrollLeft;
        var maxScroll = this.wrapper.scrollWidth - this.wrapper.clientWidth;

        if (maxScroll == 0) {
            // no need to continue if scrollbar is not there
            return;
        }

        // if the cursor is currently visible...
        if (!immediate && -half <= offset && offset < half) {
            // we'll limit the "re-center" rate.
            var rate = 5;
            offset = Math.max(-rate, Math.min(rate, offset));
            target = scrollLeft + offset;
        }

        // limit target to valid range (0 to maxScroll)
        target = Math.max(0, Math.min(maxScroll, target));
        // no use attempting to scroll if we're not moving
        if (target != scrollLeft) {
            this.wrapper.scrollLeft = target;
        }

    },

    getWidth: function () {
        return Math.round(this.container.clientWidth * this.params.pixelRatio);
    },

    setWidth: function (width) {
        if (width == this.width) {
            return;
        }

        this.width = width;

        if (this.params.fillParent || this.params.scrollParent) {
            this.style(this.wrapper, {
                width: ''
            });
        } else {
            this.style(this.wrapper, {
                width: ~~(this.width / this.params.pixelRatio) + 'px'
            });
        }

        this.updateSize();
    },

    setHeight: function (height) {
        if (height == this.height) {
            return;
        }
        this.height = height;
        this.style(this.wrapper, {
            height: ~~(this.height / this.params.pixelRatio) + 'px'
        });
        this.updateSize();
    },

    progress: function (progress) {
        var minPxDelta = 1 / this.params.pixelRatio;
        var pos = Math.round(progress * this.width) * minPxDelta;

        if (pos < this.lastPos || pos - this.lastPos >= minPxDelta) {
            this.lastPos = pos;

            if (this.params.scrollParent) {
                var newPos = ~~(this.wrapper.scrollWidth * progress);
                this.recenterOnPosition(newPos);
            }

            this.updateProgress(progress);
        }
    },

    destroy: function () {
        this.unAll();
        if (this.wrapper) {
            this.container.removeChild(this.wrapper);
            this.wrapper = null;
        }
    },

    /* Renderer-specific methods */
    createElements: function () {
    },

    updateSize: function () {
    },

    drawWave: function (peaks, max) {
    },

    clearWave: function () {
    },

    updateProgress: function (position) {
    }
};

WaveSurfer.util.extend(WaveSurfer.Drawer, WaveSurfer.Observer);

'use strict';

WaveSurfer.Drawer.Canvas = Object.create(WaveSurfer.Drawer);

WaveSurfer.util.extend(WaveSurfer.Drawer.Canvas, {
    createElements: function () {
        var waveCanvas = this.wrapper.appendChild(
            this.style(document.createElement('canvas'), {
                position: 'absolute',
                zIndex: 1,
                top: 0,
                bottom: 0
            })
        );
        this.waveCc = waveCanvas.getContext('2d');

        this.progressWave = this.wrapper.appendChild(
            this.style(document.createElement('wave'), {
                position: 'absolute',
                zIndex: 2,
                top: 0,
                bottom: 0,
                overflow: 'hidden',
                width: '0',
                display: 'none',
                boxSizing: 'border-box',
                borderRightStyle: 'solid',
                borderRightWidth: this.params.cursorWidth + 'px',
                borderRightColor: this.params.cursorColor
            })
        );

        if (this.params.waveColor != this.params.progressColor) {
            var progressCanvas = this.progressWave.appendChild(
                document.createElement('canvas')
            );
            this.progressCc = progressCanvas.getContext('2d');
        }
    },

    updateSize: function () {
        var width = Math.round(this.width / this.params.pixelRatio);

        this.waveCc.canvas.width = this.width;
        this.waveCc.canvas.height = this.height;
        this.style(this.waveCc.canvas, {width: width + 'px'});

        this.style(this.progressWave, {display: 'block'});

        if (this.progressCc) {
            this.progressCc.canvas.width = this.width;
            this.progressCc.canvas.height = this.height;
            this.style(this.progressCc.canvas, {width: width + 'px'});
        }

        this.clearWave();
    },

    clearWave: function () {
        this.waveCc.clearRect(0, 0, this.width, this.height);
        if (this.progressCc) {
            this.progressCc.clearRect(0, 0, this.width, this.height);
        }
    },

    drawWave: function (peaks, channelIndex) {
        // Split channels
        if (peaks[0] instanceof Array) {
            var channels = peaks;
            if (this.params.splitChannels) {
                this.setHeight(channels.length * this.params.height * this.params.pixelRatio);
                channels.forEach(this.drawWave, this);
                return;
            } else {
                peaks = channels[0];
            }
        }

        // A half-pixel offset makes lines crisp
        var $ = 0.5 / this.params.pixelRatio;
        // A margin between split waveforms
        var height = this.params.height * this.params.pixelRatio;
        var offsetY = height * channelIndex || 0;
        var halfH = height / 2;
        var length = peaks.length;
        var scale = 1;
        if (this.params.fillParent && this.width != length) {
            scale = this.width / length;
        }
        var max = 1;
        if (this.params.normalize) {
            max = Math.max.apply(Math, peaks);
        }

        this.waveCc.fillStyle = this.params.waveColor;
        if (this.progressCc) {
            this.progressCc.fillStyle = this.params.progressColor;
        }

        [this.waveCc, this.progressCc].forEach(function (cc) {
            if (!cc) {
                return;
            }

            cc.beginPath();
            cc.moveTo($, halfH + offsetY);

            for (var i = 0; i < length; i++) {
                var h = Math.round(peaks[i] / max * halfH);
                cc.lineTo(i * scale + $, halfH + h + offsetY);
            }

            cc.lineTo(this.width + $, halfH + offsetY);
            cc.moveTo($, halfH + offsetY);

            for (var i = 0; i < length; i++) {
                var h = Math.round(peaks[i] / max * halfH);
                cc.lineTo(i * scale + $, halfH - h + offsetY);
            }

            cc.lineTo(this.width + $, halfH + offsetY);
            cc.closePath();
            cc.fill();

            // Always draw a median line
            cc.fillRect(0, halfH + offsetY - $, this.width, $);
        }, this);
    },

    updateProgress: function (progress) {
        var pos = Math.round(
                this.width * progress
            ) / this.params.pixelRatio;
        this.style(this.progressWave, {width: pos + 'px'});
    }
});


'use strict';

/* Regions manager */
WaveSurfer.Regions = {
    init: function (wavesurfer) {
        this.wavesurfer = wavesurfer;
        this.wrapper = this.wavesurfer.drawer.wrapper;

        /* Id-based hash of regions. */
        this.list = {};
    },

    /* Remove a region. */
    add: function (params) {
        var region = Object.create(WaveSurfer.Region);
        region.init(params, this.wavesurfer);

        this.list[region.id] = region;

        region.on('remove', (function () {
            delete this.list[region.id];
        }).bind(this));

        return region;
    },

    /* Remove all regions. */
    clear: function () {
        Object.keys(this.list).forEach(function (id) {
            this.list[id].remove();
        }, this);
    },

    enableDragSelection: function (params) {
        var my = this;
        var drag;
        var start;
        var region;

        this.wrapper.addEventListener('mousedown', function (e) {
            drag = true;
            start = my.wavesurfer.drawer.handleEvent(e);
            region = null;
        });
        this.wrapper.addEventListener('mouseup', function () {
            drag = false;
            region = null;
        });
        this.wrapper.addEventListener('mousemove', function (e) {
            if (!drag) {
                return;
            }

            if (!region) {
                region = my.add(params || {});
            }

            var duration = my.wavesurfer.getDuration();
            var end = my.wavesurfer.drawer.handleEvent(e);
            region.update({
                start: Math.min(end * duration, start * duration),
                end: Math.max(end * duration, start * duration)
            });
        });
    }
};

WaveSurfer.Region = {
    /* Helper function to assign CSS styles. */
    style: WaveSurfer.Drawer.style,

    init: function (params, wavesurfer) {
        this.wavesurfer = wavesurfer;
        this.wrapper = wavesurfer.drawer.wrapper;

        this.id = params.id == null ? WaveSurfer.util.getId() : params.id;
        this.start = Number(params.start) || 0;
        this.end = params.end == null ?
            // small marker-like region
        this.start + (4 / this.wrapper.scrollWidth) * this.wavesurfer.getDuration() :
            Number(params.end);
        this.resize = params.resize === undefined ? true : Boolean(params.resize);
        this.drag = params.drag === undefined ? true : Boolean(params.drag);
        this.loop = Boolean(params.loop);
        this.color = params.color || 'rgba(0, 0, 0, 0.1)';
        this.data = params.data || {};

        this.bindInOut();
        this.render();

        this.wavesurfer.fireEvent('region-created', this);
    },

    /* Update region params. */
    update: function (params) {
        if (null != params.start) {
            this.start = Number(params.start);
        }
        if (null != params.end) {
            this.end = Number(params.end);
        }
        if (null != params.loop) {
            this.loop = Boolean(params.loop);
        }
        if (null != params.color) {
            this.color = params.color;
        }
        if (null != params.data) {
            this.data = params.data;
        }
        if (null != params.resize) {
            this.resize = Boolean(params.resize);
        }
        if (null != params.drag) {
            this.drag = Boolean(params.drag);
        }
        this.updateRender();
        this.fireEvent('update');
        this.wavesurfer.fireEvent('region-updated', this);
    },

    /* Remove a single region. */
    remove: function (region) {
        if (this.element) {
            this.wrapper.removeChild(this.element);
            this.element = null;
            this.fireEvent('remove');
            this.wavesurfer.fireEvent('region-removed', this);
        }
    },

    /* Play the audio region. */
    play: function () {
        this.wavesurfer.play(this.start, this.end);
        this.fireEvent('play');
        this.wavesurfer.fireEvent('region-play', this);
    },

    /* Play the region in loop. */
    playLoop: function () {
        this.play();
        this.once('out', this.playLoop.bind(this));
    },

    /* Render a region as a DOM element. */
    render: function () {
        var regionEl = document.createElement('region');
        regionEl.className = 'wavesurfer-region';
        regionEl.title = this.formatTime(this.start, this.end);

        var width = this.wrapper.scrollWidth;
        this.style(regionEl, {
            position: 'absolute',
            zIndex: 2,
            height: '100%',
            top: '0px'
        });

        /* Resize handles */
        if (this.resize) {
            var handleLeft = regionEl.appendChild(document.createElement('handle'));
            var handleRight = regionEl.appendChild(document.createElement('handle'));
            handleLeft.className = 'wavesurfer-handle wavesurfer-handle-start';
            handleRight.className = 'wavesurfer-handle wavesurfer-handle-end';
            var css = {
                cursor: 'col-resize',
                position: 'absolute',
                left: '0px',
                top: '0px',
                width: '1%',
                maxWidth: '4px',
                height: '100%'
            };
            this.style(handleLeft, css);
            this.style(handleRight, css);
            this.style(handleRight, {
                left: '100%'
            });
        }

        this.element = this.wrapper.appendChild(regionEl);
        this.updateRender();
        this.bindEvents(regionEl);
    },

    formatTime: function (start, end) {
        return (start == end ? [start] : [start, end]).map(function (time) {
            return [
                Math.floor((time % 3600) / 60), // minutes
                ('00' + Math.floor(time % 60)).slice(-2) // seconds
            ].join(':');
        }).join('–');
    },

    /* Update element's position, width, color. */
    updateRender: function () {
        var dur = this.wavesurfer.getDuration();
        var width = this.wrapper.scrollWidth;

        if (this.start < 0) {
            this.start = 0;
            this.end = this.end - this.start;
        }
        if (this.end > dur) {
            this.end = dur;
            this.start = dur - (this.end - this.start);
        }
        this.style(this.element, {
            left: ~~(this.start / dur * width) + 'px',
            width: ~~((this.end - this.start) / dur * width) + 'px',
            backgroundColor: this.color,
            cursor: this.drag ? 'move' : 'default'
        });
        this.element.title = this.formatTime(this.start, this.end);
    },

    /* Bind audio events. */
    bindInOut: function () {
        var my = this;

        var onPlay = function () {
            my.firedIn = false;
            my.firedOut = false;
        };

        var onProcess = function (time) {
            if (!my.firedIn && my.start <= time && my.end > time) {
                my.firedIn = true;
                my.fireEvent('in');
                my.wavesurfer.fireEvent('region-in', my);
            }
            if (!my.firedOut && my.firedIn && my.end <= time) {
                my.firedOut = true;
                my.fireEvent('out');
                my.wavesurfer.fireEvent('region-out', my);
            }
        };

        this.wavesurfer.on('play', onPlay);
        this.wavesurfer.backend.on('audioprocess', onProcess);

        this.on('remove', function () {
            my.wavesurfer.un('play', onPlay);
            my.wavesurfer.backend.un('audioprocess', onProcess);
        });

        /* Loop playback. */
        this.on('out', function () {
            if (my.loop) {
                my.wavesurfer.play(my.start);
            }
        });
    },

    /* Bind DOM events. */
    bindEvents: function () {
        var my = this;

        this.element.addEventListener('mouseenter', function (e) {
            my.fireEvent('mouseenter', e);
            my.wavesurfer.fireEvent('region-mouseenter', my, e);
        });

        this.element.addEventListener('mouseleave', function (e) {
            my.fireEvent('mouseleave', e);
            my.wavesurfer.fireEvent('region-mouseleave', my, e);
        });

        this.element.addEventListener('click', function (e) {
            e.preventDefault();
            my.fireEvent('click', e);
            my.wavesurfer.fireEvent('region-click', my, e);
        });

        this.element.addEventListener('dblclick', function (e) {
            e.stopPropagation();
            e.preventDefault();
            my.fireEvent('dblclick', e);
            my.wavesurfer.fireEvent('region-dblclick', my, e);
        });

        /* Drag or resize on mousemove. */
        (this.drag || this.resize) && (function () {
            var duration = my.wavesurfer.getDuration();
            var drag;
            var resize;
            var startTime;

            var onDown = function (e) {
                e.stopPropagation();
                startTime = my.wavesurfer.drawer.handleEvent(e) * duration;

                if (e.target.tagName.toLowerCase() == 'handle') {
                    if (e.target.classList.contains('wavesurfer-handle-start')) {
                        resize = 'start';
                    } else {
                        resize = 'end';
                    }
                } else {
                    drag = true;
                }
            };
            var onUp = function (e) {
                if (drag || resize) {
                    drag = false;
                    resize = false;
                    e.stopPropagation();
                    e.preventDefault();

                    my.fireEvent('update-end');
                    my.wavesurfer.fireEvent('region-update-end');
                }
            };
            var onMove = function (e) {
                if (drag || resize) {
                    var time = my.wavesurfer.drawer.handleEvent(e) * duration;
                    var delta = time - startTime;
                    startTime = time;

                    // Drag
                    if (my.drag && drag) {
                        my.onDrag(delta);
                    }

                    // Resize
                    if (my.resize && resize) {
                        my.onResize(delta, resize);
                    }
                }
            };

            my.element.addEventListener('mousedown', onDown);
            my.wrapper.addEventListener('mousemove', onMove);
            document.body.addEventListener('mouseup', onUp);

            my.on('remove', function () {
                document.body.removeEventListener('mouseup', onUp);
                my.wrapper.removeEventListener('mousemove', onMove);
            });

            my.wavesurfer.on('destroy', function () {
                document.body.removeEventListener('mouseup', onUp);
            });
        }());
    },

    onDrag: function (delta) {
        this.update({
            start: this.start + delta,
            end: this.end + delta
        });
    },

    onResize: function (delta, direction) {
        if (direction == 'start') {
            this.update({
                start: Math.min(this.start + delta, this.end),
                end: Math.max(this.start + delta, this.end)
            });
        } else {
            this.update({
                start: Math.min(this.end + delta, this.start),
                end: Math.max(this.end + delta, this.start)
            });
        }
    }
};

WaveSurfer.util.extend(WaveSurfer.Region, WaveSurfer.Observer);


/* Augment WaveSurfer with region methods. */
WaveSurfer.initRegions = function () {
    if (!this.regions) {
        this.regions = Object.create(WaveSurfer.Regions);
        this.regions.init(this);
    }
};

WaveSurfer.addRegion = function (options) {
    this.initRegions();
    return this.regions.add(options);
};

WaveSurfer.clearRegions = function () {
    this.regions && this.regions.clear();
};

WaveSurfer.enableDragSelection = function (options) {
    this.initRegions();
    this.regions.enableDragSelection(options);
};

WaveSurfer.ELAN = {
    Types: {
        ALIGNABLE_ANNOTATION: 'ALIGNABLE_ANNOTATION',
        REF_ANNOTATION: 'REF_ANNOTATION'
    },

    init: function (params) {
        this.data = null;
        this.params = params;
        this.container = 'string' == typeof params.container ?
            document.querySelector(params.container) : params.container;

        if (!this.container) {
            throw Error('No container for ELAN');
        }

        this.bindClick();

        if (params.url) {
            this.load(params.url);
        }
    },

    load: function (url) {
        var my = this;
        this.loadXML(url, function (xml) {
            my.data = my.parseElan(xml);
            my.render();
            my.fireEvent('ready', my.data);
        });
    },

    loadXML: function (url, callback) {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', url, true);
        xhr.responseType = 'document';
        xhr.send();
        xhr.addEventListener('load', function (e) {
            callback && callback(e.target.responseXML);
        });
    },

    parseElan: function (xml) {
        var _forEach = Array.prototype.forEach;
        var _map = Array.prototype.map;

        var data = {
            media: {},
            timeOrder: {},
            tiers: [],
            annotations: {},
            alignableAnnotations: []
        };

        var header = xml.querySelector('HEADER');
        var inMilliseconds = header.getAttribute('TIME_UNITS') == 'milliseconds';
        var media = header.querySelector('MEDIA_DESCRIPTOR');
        data.media.url = media.getAttribute('MEDIA_URL');
        data.media.type = media.getAttribute('MIME_TYPE');

        var timeSlots = xml.querySelectorAll('TIME_ORDER TIME_SLOT');
        var timeOrder = {};
        _forEach.call(timeSlots, function (slot) {
            var value = parseFloat(slot.getAttribute('TIME_VALUE'));
            // If in milliseconds, convert to seconds with rounding
            if (inMilliseconds) {
                value = Math.round(value * 1e2) / 1e5;
            }
            timeOrder[slot.getAttribute('TIME_SLOT_ID')] = value;
        });

        data.tiers = _map.call(xml.querySelectorAll('TIER'), function (tier) {
            return {
                id: tier.getAttribute('TIER_ID'),
                linguisticTypeRef: tier.getAttribute('LINGUISTIC_TYPE_REF'),
                defaultLocale: tier.getAttribute('DEFAULT_LOCALE'),
                annotations: _map.call(
                    tier.querySelectorAll('REF_ANNOTATION, ALIGNABLE_ANNOTATION'),
                    function (node) {
                        var annot = {
                            type: node.nodeName,
                            id: node.getAttribute('ANNOTATION_ID'),
                            ref: node.getAttribute('ANNOTATION_REF'),
                            value: node.querySelector('ANNOTATION_VALUE')
                                .textContent.trim()
                        };

                        if (this.Types.ALIGNABLE_ANNOTATION == annot.type) {
                            // Add start & end to alignable annotation
                            annot.start = timeOrder[node.getAttribute('TIME_SLOT_REF1')];
                            annot.end = timeOrder[node.getAttribute('TIME_SLOT_REF2')];

                            // Add to the list of alignable annotations
                            data.alignableAnnotations.push(annot);
                        }

                        // Additionally, put into the flat map of all annotations
                        data.annotations[annot.id] = annot;

                        return annot;
                    }, this
                )
            };
        }, this);

        // Create JavaScript references between annotations
        data.tiers.forEach(function (tier) {
            tier.annotations.forEach(function (annot) {
                if (null != annot.ref) {
                    annot.reference = data.annotations[annot.ref];
                }
            }, this);
        }, this);

        // Sort alignable annotations by start & end
        data.alignableAnnotations.sort(function (a, b) {
            var d = a.start - b.start;
            if (d == 0) {
                d = b.end - a.end;
            }
            return d;
        });

        data.length = data.alignableAnnotations.length;

        return data;
    },

    render: function () {
        // apply tiers filter
        var tiers = this.data.tiers;
        if (this.params.tiers) {
            tiers = tiers.filter(function (tier) {
                return tier.id in this.params.tiers;
            }, this);
        }

        // denormalize references to alignable annotations
        var backRefs = {};
        var indeces = {};
        tiers.forEach(function (tier, index) {
            tier.annotations.forEach(function (annot) {
                if (annot.reference &&
                    annot.reference.type == this.Types.ALIGNABLE_ANNOTATION) {
                    if (!(annot.reference.id in backRefs)) {
                        backRefs[annot.ref] = {};
                    }
                    backRefs[annot.ref][index] = annot;
                    indeces[index] = true;
                }
            }, this);
        }, this);
        indeces = Object.keys(indeces).sort();

        this.renderedAlignable = this.data.alignableAnnotations.filter(
            function (alignable) {
                return backRefs[alignable.id];
            }
        );

        // table
        var table = document.createElement('table');
        table.className = 'wavesurfer-annotations';

        // head
        var thead = document.createElement('thead');
        var headRow = document.createElement('tr');
        thead.appendChild(headRow);
        table.appendChild(thead);
        var th = document.createElement('th');
        th.textContent = 'Time';
        th.className = 'wavesurfer-time';
        headRow.appendChild(th);
        indeces.forEach(function (index) {
            var tier = tiers[index];
            var th = document.createElement('th');
            th.className = 'wavesurfer-tier-' + tier.id;
            th.textContent = tier.id;
            th.style.width = this.params.tiers[tier.id];
            headRow.appendChild(th);
        }, this);

        // body
        var tbody = document.createElement('tbody');
        table.appendChild(tbody);
        this.renderedAlignable.forEach(function (alignable) {
            var row = document.createElement('tr');
            row.id = 'wavesurfer-alignable-' + alignable.id;
            tbody.appendChild(row);

            var td = document.createElement('td');
            td.className = 'wavesurfer-time';
            td.textContent = alignable.start.toFixed(1) + '–' +
                alignable.end.toFixed(1);
            row.appendChild(td);

            var backRef = backRefs[alignable.id];
            indeces.forEach(function (index) {
                var tier = tiers[index];
                var td = document.createElement('td');
                var annotation = backRef[index];
                if (annotation) {
                    td.id = 'wavesurfer-annotation-' + annotation.id;
                    td.dataset.ref = alignable.id;
                    td.dataset.start = alignable.start;
                    td.dataset.end = alignable.end;
                    td.textContent = annotation.value;
                }
                td.className = 'wavesurfer-tier-' + tier.id;
                row.appendChild(td);
            }, this);
        }, this);

        this.container.innerHTML = '';
        this.container.appendChild(table);
    },

    bindClick: function () {
        var my = this;
        this.container.addEventListener('click', function (e) {
            var ref = e.target.dataset.ref;
            if (null != ref) {
                var annot = my.data.annotations[ref];
                if (annot) {
                    my.fireEvent('select', annot.start, annot.end);
                }
            }
        });
    },

    getRenderedAnnotation: function (time) {
        var result;
        this.renderedAlignable.some(function (annotation) {
            if (annotation.start <= time && annotation.end >= time) {
                result = annotation;
                return true;
            }
            return false;
        });
        return result;
    },

    getAnnotationNode: function (annotation) {
        return document.getElementById(
            'wavesurfer-alignable-' + annotation.id
        );
    }
};

WaveSurfer.util.extend(WaveSurfer.ELAN, WaveSurfer.Observer);
