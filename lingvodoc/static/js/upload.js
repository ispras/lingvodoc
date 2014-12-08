'use strict';

define(function () {

    var upload = function (options) {

        this.options = options || {};
        this.reader = null;
        this.binaryString = null;

        this.readBinaryString = function(file) {

            var userOnload = this.options.onload || function(event, file) {};
            this.reader = new FileReader();
            this.reader.onerror = this.options.onerror || this.errorHandler;
            this.reader.onprogress = this.options.onprogress || function() {};
            this.reader.onabort = this.options.onabort || function() {};
            this.reader.onloadstart = this.options.onloadstart || function() {};
            this.reader.onload = function(event) {
                return userOnload(event, file)
            };
            this.reader.readAsBinaryString(file);
        }.bind(this);

        this.abort = function () {
            this.reader.abort();
        }.bind(this);

        this.errorHandler = function (evt) {
            switch (evt.target.error.code) {
                case evt.target.error.NOT_FOUND_ERR:
                    alert('File Not Found!');
                    break;
                case evt.target.error.NOT_READABLE_ERR:
                    alert('File is not readable');
                    break;
                case evt.target.error.ABORT_ERR:
                    break;
                default:
                    alert('An error occurred reading this file.');
            }
        }.bind(this);

        this.bindDragAndDrop = function(holderElement) {

            holderElement.addEventListener('dragenter', function(event) {
                e.stopPropagation();
                e.preventDefault();
            });

            holderElement.addEventListener('dragover', function(event) {
                event.stopPropagation();
                event.preventDefault();
            });

            holderElement.addEventListener('dragleave', function(event) {
                event.stopPropagation();
                event.preventDefault();
            });

            holderElement.addEventListener('drop', function(event) {
                event.preventDefault();
                for (var i = 0; i < event.dataTransfer.files.length; i++) {
                    this.readBinaryString(event.dataTransfer.files[i]);
                }
            }.bind(this));

        }.bind(this);

        this.bindInputFiles = function(element) {
            element.addEventListener('change', function(event) {
                event.preventDefault();
                for (var i = 0; i < event.target.files.length; i++) {
                    this.readBinaryString(event.target.files[i]);
                }
            }.bind(this));
        }.bind(this);
    };
    return upload;
});