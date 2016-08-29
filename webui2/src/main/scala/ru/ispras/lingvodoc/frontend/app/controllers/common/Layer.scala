package ru.ispras.lingvodoc.frontend.app.controllers.common

import ru.ispras.lingvodoc.frontend.app.model.LocalizedString

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class Layer(override var names: js.Array[LocalizedString], var fieldTypes: js.Array[FieldType]) extends Translatable {
  override def equals(other: Any) = other match {
    case that: Layer =>
      (that canEqual this) && ((that.names zip this.names) forall { n => n._1.equals(n._2) })
    case _ =>
      false
  }

  def canEqual(other: Any) = other.isInstanceOf[Layer]
}
