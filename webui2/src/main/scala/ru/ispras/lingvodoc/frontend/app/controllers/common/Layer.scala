package ru.ispras.lingvodoc.frontend.app.controllers.common

import ru.ispras.lingvodoc.frontend.app.model.LocalizedString

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll
import scala.util.Random


@JSExportAll
case class Layer(override var names: js.Array[LocalizedString], var fieldEntries: js.Array[FieldEntry]) extends Translatable {

  private val rnd = new Random()
  val internalId = rnd.nextInt(9) * 100000 + rnd.nextInt(9) + 10000 + rnd.nextInt(9) * 1000 + rnd.nextInt(9) * 100 + rnd.nextInt(9) * 10 + rnd.nextInt(9)

  override def equals(other: Any) = other match {
    case that: Layer =>
      (that canEqual this) && ((that.names zip this.names) forall { n => n._1.equals(n._2) }) && (that.internalId == this.internalId)
    case _ =>
      false
  }

  def canEqual(other: Any) = other.isInstanceOf[Layer]
}
