function getCookie(name) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    for(var i=0;i < ca.length;i++) {
        var c = ca[i];
        while (c.charAt(0)==' ') c = c.substring(1,c.length);
        if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
    }
    return null;
}

var wrapPerspective = function (perspective) {

    if (typeof perspective.fields == 'undefined') {
        return;
    }

    for (var i = 0; i < perspective.fields.length; i++) {
        if (typeof perspective.fields[i].group !== 'undefined') {
            perspective.fields[i]._groupEnabled = true;
        }

        if (typeof perspective.fields[i].contains !== 'undefined') {
            perspective.fields[i]._containsEnabled = true;
        }
    }

    return perspective;
};

var exportPerspective = function(perspective) {
    var jsPerspective = {
        'fields': []
    };

    var positionCount = 1;
    for (var i = 0; i < perspective.fields.length; i++) {

        var field = JSON.parse(JSON.stringify(perspective.fields[i]));

        field['position'] = positionCount;
        positionCount += 1;

        if (field.data_type !== 'grouping_tag') {
            field['level'] = 'leveloneentity';
        } else {
            field['level'] = 'groupingentity';
        }

        if (field._groupEnabled) {
            delete field._groupEnabled;
        }

        if (field._containsEnabled) {
            delete field._containsEnabled;
        }

        if (field.contains) {
            for (var j = 0; j < field.contains.length; j++) {
                field.contains[j].level = 'leveltwoentity';
                field.contains[j].position = positionCount;
                positionCount += 1;
            }
        }
        jsPerspective.fields.push(field);
    }

    return jsPerspective;
};

var cloneObject = function(oldObject) {
    return JSON.parse(JSON.stringify(oldObject));
};

var enableControls = function(controls, enabled) {
    _.each(controls, function(value, key) {
        controls[key] = enabled;
    });
};

