package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js

case class MetaData(name: String, value: String) {


}

object MetaData {

  implicit val writer = upickle.default.Writer[MetaData] {
    metadata => Js.Obj(
      ("name", Js.Str(metadata.name)),
      ("value", Js.Str(metadata.value))
    )
  }

  implicit val reader = upickle.default.Reader[MetaData] {
    case js: Js.Obj =>
      val metaType = js("type").str


      metaType match {
        case "authors" =>
        case "location" =>
        case _ =>
      }



      MetaData("", "")
  }
}







