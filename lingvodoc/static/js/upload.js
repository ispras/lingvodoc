'use strict';

define(function () {

    var upload = function (options) {

        this.options = options || {};
        this.reader = null;
        this.binaryString = null;

        this.readBinaryString = function (data) {
            this.reader = new FileReader();
            this.reader.onerror = this.options.onerror || this.errorHandler;
            this.reader.onprogress = this.options.onprogress || function() {};
            this.reader.onabort = this.options.onabort || function() {};
            this.reader.onloadstart = this.options.onloadstart || function() {};
            this.reader.onload = this.options.onload || function() {};
            this.reader.readAsBinaryString(data);
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
            });

            holderElement.addEventListener('dragover', function(event) {
                event.preventDefault();
            });

            holderElement.addEventListener("dragleave", function(event) {
            });

            holderElement.addEventListener('drop', function(event) {
                event.preventDefault();
                this.readBinaryString(event.dataTransfer.files[0]);
            }.bind(this));




        }.bind(this);
    };
    return upload;
});