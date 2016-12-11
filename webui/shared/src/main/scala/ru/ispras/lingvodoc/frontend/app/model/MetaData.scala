package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js
import upickle.default._
import derive.key

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class Authors(@key("type") `type`: String, @key("content") authors: String)

@JSExportAll
case class Location(@key("type") `type`: String, @key("content") location: LatLng)

@JSExportAll
case class Blob(@key("type") `type`: String, @key("content") blob: CompositeId)


@JSExportAll
case class MetaData(authors: Option[Authors] = Option.empty[Authors], location: Option[Location] = Option.empty[Location], info: Seq[Blob] = Seq[Blob]()) {}

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

      val jsBlobs = metadata.info map { info =>
        Js.Obj(("info", writeJs[Blob](info)))
      }
      val jsList = Js.Obj(("content", Js.Arr(jsBlobs: _*)), ("type", Js.Str("list")))

      values = values :+ ("info", jsList)

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

      import org.scalajs.dom.console
      try {
        val blobs = js.value.find(_._1 == "info").map(_._2.obj("content").arr.map { e => readJs[Blob](e("info")) }).toSeq.flatten
        MetaData(authors, location, blobs)
      } catch {
        case e: Throwable =>
          console.log(e.getMessage)
          MetaData(authors, location, Seq.empty[Blob])
      }


  }
}
