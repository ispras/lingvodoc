package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
abstract class Object(@key("client_id") cId: Int, @key("object_id") oId: Int) {
  val clientId: Int = cId
  val objectId: Int = oId

  override def equals(obj: Any): Boolean = {
    obj match {
      case o: Object =>
        o.clientId == clientId && o.objectId == objectId
      case _ =>
        false
    }
  }


  def getId: String = {
    clientId.toString + "_" + objectId.toString
  }
}
