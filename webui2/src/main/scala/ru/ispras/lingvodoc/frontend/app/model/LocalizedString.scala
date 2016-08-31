package ru.ispras.lingvodoc.frontend.app.model

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class LocalizedString(var localeId: Int, var str: String) {
  override def equals(other: Any) = other match {
    case that: LocalizedString =>
      (that canEqual this) &&
        (this.localeId == that.localeId) && (this.str == that.str)
    case _ =>
      false
  }

  def canEqual(other: Any) = other.isInstanceOf[LocalizedString]
}
