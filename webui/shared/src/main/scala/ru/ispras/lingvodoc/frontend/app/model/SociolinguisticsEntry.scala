package ru.ispras.lingvodoc.frontend.app.model

import derive.key
import upickle.default._

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class SociolinguisticsEntry(perspectives: Seq[CompositeId], location: LatLng, date: String, questions: Map[String, String])

object SociolinguisticsEntry {
  import upickle.Js
  implicit def MapWithStringKeysR[V: Reader] = Reader[Map[String, V]] {
    case json: Js.Obj => json.value.map(x => (x._1, readJs[V](x._2))).toMap
  }
}


