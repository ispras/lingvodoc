package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js
import upickle.default._
import derive.key

case class Authors(@key("type") `type`: String, @key("content") authors: String)
case class Location(@key("type") `type`: String, @key("content") location: LatLng)

case class MetaData(authors: Option[Authors] = Option.empty[Authors], location: Option[Location] = Option.empty[Location]) {}

object MetaData {

  implicit val writer = upickle.default.Writer[MetaData] {
    metadata =>

      var values = Seq[(String, Js.Value)]()

      metadata.authors match {
        case Some(authors) => values = values :+ ("authors", writeJs[Authors](authors))
        case None =>
      }

      metadata.location match {
        case Some(location) => values = values :+ ("location", writeJs[Location](location))
        case None =>
      }

      Js.Obj(values: _*)
  }

  implicit val reader = upickle.default.Reader[MetaData] {
    case js: Js.Obj =>

      val authors = js.value.find(_._1 == "authors") match {
        case Some(a) => Some(readJs[Authors](a._2))
        case None => None
      }

      val location = js.value.find(_._1 == "location") match {
        case Some(a) => Some(readJs[Location](a._2))
        case None => None
      }

      MetaData(authors, location)
  }
}
