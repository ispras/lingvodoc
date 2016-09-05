package ru.ispras.lingvodoc.frontend.app.controllers.common

import ru.ispras.lingvodoc.frontend.app.model.{LocalizedString, TranslationGist}
import ru.ispras.lingvodoc.frontend.app.utils.GUIDGenerator

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class FieldEntry(override var names: js.Array[LocalizedString]) extends Translatable {

  val internalId = GUIDGenerator.generate()

  var fieldId: String = ""
  var translatable: Boolean = true
  var dataType: Option[TranslationGist] = None
  var hasSubfield: Boolean = false
  var subfieldId: String = ""
  var linkedLayerId: String = ""
  override def equals(other: Any) = other match {
    case that: FieldEntry =>
      (that canEqual this) && ((that.names zip this.names) forall { n => n._1.equals(n._2) }) && (that.fieldId == this.fieldId) && (that.translatable == this.translatable) && (that.internalId == this.internalId)
    case _ =>
      false
  }

  def canEqual(other: Any) = other.isInstanceOf[FieldEntry]
}
