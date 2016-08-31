package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js

case class MetaData(name: String, value: String) {}

object MetaData {

  implicit val writer = upickle.default.Writer[MetaData] {
    metadata => Js.Obj(
      ("name", Js.Str(metadata.name)),
      ("value", Js.Str(metadata.value))
    )
  }

  implicit val reader = upickle.default.Reader[MetaData] {
    case js: Js.Obj =>
      val name = js("name").asInstanceOf[Js.Str].value
      val value = js("login").asInstanceOf[Js.Str].value
      MetaData(name, value)
  }
}







