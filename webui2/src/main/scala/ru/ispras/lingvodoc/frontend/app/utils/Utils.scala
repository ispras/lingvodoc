package ru.ispras.lingvodoc.frontend.app.utils

import ru.ispras.lingvodoc.frontend.app.model.{Field, Language}

object Utils {

  def flattenLanguages(languages: Seq[Language]) = {
    var acc = Seq[Language]()
    var queue = Vector[Language]()
    queue = queue ++ languages

    while (queue.nonEmpty) {
      val first +: rest = queue
      acc = acc :+ first
      queue = rest ++ first.languages
    }
    acc
  }

  def getUserId: Int = {
    0
  }

  /*
  var perspectiveToDictionaryFields = function(perspectiveFields) {
        var fields = [];
        angular.forEach(perspectiveFields, function(field, index) {
            if (typeof field.group == 'string') {

                var createNewGroup = true;
                for (var j = 0; j < fields.length; j++) {
                    if (fields[j].entity_type == field.group && fields[j].isGroup) {
                        fields[j].contains.push(field);
                        createNewGroup = false;
                        break;
                    }
                }

                if (createNewGroup) {
                    fields.push({
                        'entity_type': field.group,
                        'isGroup': true,
                        'contains': [field]
                    });
                }

            } else {
                fields.push(field);
            }
        });
        return fields;
    };
   */

//  def perspectiveToDictionaryFields(fields: Seq[Field]) = {
//
//    var dh: Seq[Field] = Seq[Field]()
//    for (field <- fields) {
//
//    }
//  }
}
