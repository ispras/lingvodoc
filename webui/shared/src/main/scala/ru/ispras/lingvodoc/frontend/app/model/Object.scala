package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
abstract class Object(@key("client_id") cId: Int, @key("object_id") oId: Int) {
  val clientId = cId
  val objectId = oId

  def equals(obj: Object): Boolean = {
    obj.clientId == clientId && obj.objectId == objectId
  }

  def getId: String = {
    clientId.toString + "_" + objectId.toString
  }
}
