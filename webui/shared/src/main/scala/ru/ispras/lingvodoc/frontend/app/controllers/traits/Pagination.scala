package ru.ispras.lingvodoc.frontend.app.controllers.traits

import scala.scalajs.js.annotation.JSExport
import scala.scalajs.js.JSConverters._



trait Pagination {

  protected def getOffset(page: Int, size: Int) = {
    (page - 1) * size
  }

  @JSExport
  def range(min: Int, max: Int, step: Int) = {
    (min to max by step).toSeq.toJSArray
  }

  @JSExport
  def getPageLink(page: Int): String
}
