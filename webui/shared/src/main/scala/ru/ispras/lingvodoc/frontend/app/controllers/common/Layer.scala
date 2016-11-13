package ru.ispras.lingvodoc.frontend.app.controllers.common

import ru.ispras.lingvodoc.frontend.app.model.LocalizedString
import ru.ispras.lingvodoc.frontend.app.utils.GUIDGenerator

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class Layer(override var names: js.Array[LocalizedString], var fieldEntries: js.Array[FieldEntry]) extends Translatable {

  val internalId = GUIDGenerator.generate()

  override def equals(other: Any) = other match {
    case that: Layer =>
      (that canEqual this) && ((that.names zip this.names) forall { n => n._1.equals(n._2) }) && (that.internalId == this.internalId)
    case _ =>
      false
  }

  def canEqual(other: Any) = other.isInstanceOf[Layer]
}



