package ru.ispras.lingvodoc.frontend.app.controllers.common

import ru.ispras.lingvodoc.frontend.app.model.LocalizedString

import scala.scalajs.js

trait Translatable {
  var names: js.Array[LocalizedString]
}
