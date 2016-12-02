package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js
import upickle.default._

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class Source[T <: Object](var source: T)

object Source {
  implicit val reader = upickle.default.Reader[Source[_]] {
    case obj: Js.Obj =>
        val source = obj("type").str match {
          case "language" => readJs[Language](obj)
          case "dictionary" => readJs[Dictionary](obj)
          case "perspective" => readJs[Perspective](obj)
        }
        Source(source)
  }
}
