'use strict';

define([], function(){
   var model = {};

    model.Value = function() {
        this.type = 'abstract';
    };

    model.TextValue = function(type, content) {
        this.type = type;
        this.content = content;
    };
    model.TextValue.prototype = new model.Value();

    model.WordSoundValue = function(name, content, mime) {
        this.type = 'sounds';
        this.name = name;
        this.mime = mime;
        this.content = content;
    };
    model.WordSoundValue.prototype = new model.Value();

    return model;
});
