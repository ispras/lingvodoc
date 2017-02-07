package ru.ispras.lingvodoc.frontend.app.controllers.traits

import com.greencatsoft.angularjs.Controller
import ru.ispras.lingvodoc.frontend.app.controllers.common.Value

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport


trait LinkEntities {
  this: Controller[_] =>

  @JSExport
  def linksCount(values: js.Array[Value]): Int = {
    values.filterNot(_.getEntity().markedForDeletion).size
  }
}
