package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js
import upickle.default._

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class PerspectiveMeta(override val clientId: Int,
                           override val objectId: Int,
                           metaData: MetaData) extends Object(clientId, objectId)


object PerspectiveMeta {
  implicit val reader = upickle.default.Reader[PerspectiveMeta] {
    case js: Js.Obj =>
      val clientId = js("client_id").num.toInt
      val objectId = js("object_id").num.toInt
      val meta = readJs[MetaData](js)
      PerspectiveMeta(clientId, objectId, meta)
  }
}

