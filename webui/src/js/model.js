'use strict';

var model = {};

model.Value = function() {
    this.export = function() {
        return {};
    }
};

model.TextValue = function(content) {
    this.content = content;
    this.export = function() {
        return {
            'content': content,
            'data_type': 'text'
        }
    };
};
model.TextValue.prototype = new model.Value();

model.SoundValue = function(name, mime, content) {
    this.name = name;
    this.mime = mime;
    this.content = content;

    this.export = function() {
        return {
            'content': content,
            'filename': name,
            'data_type': 'sound'
        }
    };
};
model.SoundValue.prototype = new model.Value();

model.ImageValue = function(name, mime, content) {
    this.name = name;
    this.mime = mime;
    this.content = content;

    this.export = function() {
        return {
            'content': content,
            'filename': name,
            'data_type': 'image'
        }
    };
};
model.ImageValue.prototype = new model.Value();


model.MarkupValue = function(name, mime, content) {
    this.name = name;
    this.mime = mime;
    this.content = content;

    this.export = function() {
        return {
            'content': content,
            'filename': name,
            'data_type': 'markup'
        }
    };
};
model.MarkupValue.prototype = new model.Value();











