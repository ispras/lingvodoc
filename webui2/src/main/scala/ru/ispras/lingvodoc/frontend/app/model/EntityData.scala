package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js
import upickle.Js._
import upickle.default._

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll


@JSExportAll
case class FileContent(@key("file_name") fileName: String, @key("file_name") fileType: String, @key("content") content: String)

@JSExportAll
case class EntityData(fieldClientId: Int, fieldObjectId: Int, localeId: Int) {
  var content: Option[Either[String, FileContent]] = None
  var linkClientId: Option[Int] = None
  var linkObjectId: Option[Int] = None
  var selfClientId: Option[Int] = None
  var selfObjectId: Option[Int] = None
}

object EntityData {

  implicit val writer = upickle.default.Writer[EntityData] {
    entity: EntityData =>
      var values = Seq[(String, Js.Value)](
        ("field_client_id", Js.Num(entity.fieldClientId)),
        ("field_object_id", Js.Num(entity.fieldObjectId)),
        ("locale_id", Js.Num(entity.localeId)))

      if (entity.content.nonEmpty)
        entity.content.get match {
          case Left(str) => values = values :+ (("content", Js.Str(str)))
          case Right(obj) =>
            values = values :+ (("filename", Js.Str(obj.fileName)))
            values = values :+ (("filetype", Js.Str(obj.fileType)))
            values = values :+ (("content", Js.Str(obj.content)))
        }

      if (entity.linkClientId.nonEmpty)
        values = values :+ (("link_client_id", Js.Num(entity.linkClientId.get)))

      if (entity.linkObjectId.nonEmpty)
        values = values :+ (("link_object_id", Js.Num(entity.linkObjectId.get)))

      if (entity.selfClientId.nonEmpty)
        values = values :+ (("self_client_id", Js.Num(entity.selfClientId.get)))

      if (entity.selfObjectId.nonEmpty)
        values = values :+ (("self_object_id", Js.Num(entity.selfObjectId.get)))

      Js.Obj(values: _*)
  }

  implicit val reader = upickle.default.Reader[EntityData] {
    case js: Js.Obj =>
      val fieldClientId = js("field_client_id").num.toInt
      val fieldObjectId = js("field_object_id").num.toInt
      val localeId = js("locale_id").num.toInt

      val content = js.value.find(_._1 == "content") match {
        case Some(c) => c._2 match {
          case Str(value) => Some(Left(value))
          case Obj(value) => Some(Right(readJs[FileContent](value._2)))
          case Arr(value) => None
          case Num(value) => None
          case False => None
          case True => None
          case Null => None
        }
        case None => None
      }

      val linkClientId = js.value.find(_._1 == "link_client_id") match {
        case Some(l) => Some(l._2.num.toInt)
        case None => None
      }

      val linkObjectId = js.value.find(_._1 == "link_object_id") match {
        case Some(l) => Some(l._2.num.toInt)
        case None => None
      }

      val selfClientId = js.value.find(_._1 == "self_client_id") match {
        case Some(l) => Some(l._2.num.toInt)
        case None => None
      }

      val selfObjectId = js.value.find(_._1 == "self_object_id") match {
        case Some(l) => Some(l._2.num.toInt)
        case None => None
      }

      val entity = EntityData(fieldClientId, fieldObjectId, localeId)
      entity.content = content
      entity.linkClientId = linkClientId
      entity.linkObjectId = linkObjectId
      entity.selfClientId = selfClientId
      entity.selfObjectId = selfObjectId
      entity
  }
}
