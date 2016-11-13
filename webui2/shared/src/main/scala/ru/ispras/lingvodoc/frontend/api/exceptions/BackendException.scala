package ru.ispras.lingvodoc.frontend.api.exceptions

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class BackendException(message: String, nestedException: Throwable) extends  Exception(message, nestedException) {
  def this() = this("", null)
  def this(message: String) = this(message, null)
  def this(nestedException : Throwable) = this("", nestedException)
}
