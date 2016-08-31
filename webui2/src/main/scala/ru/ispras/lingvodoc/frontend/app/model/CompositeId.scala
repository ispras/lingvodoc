package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js

case class CompositeId(override val clientId: Int, override val objectId: Int) extends Object(clientId, objectId)


object CompositeId {

  def fromObject[T <: Object](o: T): CompositeId = {
    CompositeId(o.clientId, o.objectId)
  }

  implicit val writer = upickle.default.Writer[CompositeId] {
    id: CompositeId =>
      Js.Obj(
        ("client_id", Js.Num(id.clientId)),
        ("object_id", Js.Num(id.objectId)))
  }

  implicit val reader = upickle.default.Reader[CompositeId] {
    case js: Js.Obj =>
      val clientId = js("client_id").num.toInt
      val objectId = js("object_id").num.toInt
      CompositeId(clientId, objectId)
  }
}