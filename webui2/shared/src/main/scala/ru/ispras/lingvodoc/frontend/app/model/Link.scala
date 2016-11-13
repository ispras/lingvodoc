package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js


case class Link(override val clientId: Int, override val objectId: Int) extends Object(clientId, objectId)



object Link {
  implicit val writer = upickle.default.Writer[Link] {
    link: Link =>
      Js.Obj(
        ("client_id", Js.Num(link.clientId)),
        ("object_id", Js.Num(link.objectId)))
  }

  implicit val reader = upickle.default.Reader[Link] {
    case js: Js.Obj =>
      val clientId = js("client_id").num.toInt
      val objectId = js("object_id").num.toInt
      Link(clientId, objectId)
  }
}