package ru.ispras.lingvodoc.frontend.app.model

import derive.key
import upickle.Js
import upickle.default._
import org.scalajs.dom.console

import scala.scalajs.js
import scala.scalajs.js.Date
import scala.scalajs.js.annotation.JSExportAll
import scala.scalajs.js.JSConverters._


@JSExportAll
case class Field(override val clientId: Int,
                 override val objectId: Int,
                 var translation: String,
                 var translationGistClientId: Int,
                 var translationGistObjectId: Int,
                 var dataTypeTranslationGistClientId: Int,
                 var dataTypeTranslationGistObjectId: Int,
                 var isTranslatable: Boolean,
                 var created: Date) extends Object(clientId, objectId) {

  var fields: js.Array[Field] = js.Array[Field]()
  var link: Option[Link] = None
}

object Field {
  implicit val writer = upickle.default.Writer[Field] {
    field: Field =>
      (new (Field => Js.Obj) {
        override def apply(f: Field): Js.Obj = {
          val contains = f.fields.map(e => apply(e)).toSeq

          var values = Seq[(String, Js.Value)](("client_id", Js.Num(f.clientId)),
            ("object_id", Js.Num(f.objectId)),
            ("translation", Js.Str(f.translation)),
            ("translation_gist_client_id", Js.Num(f.translationGistClientId)),
            ("translation_gist_object_id", Js.Num(f.translationGistObjectId)),
            ("data_type_translation_gist_client_id", Js.Num(f.dataTypeTranslationGistClientId)),
            ("data_type_translation_gist_object_id", Js.Num(f.dataTypeTranslationGistObjectId)),
            ("is_translatable", if (f.isTranslatable) Js.True else Js.False),
            ("created_at", Js.Num(f.created.getTime())),
            ("contains", Js.Arr(contains: _*)))

          field.link match {
            case Some(link) => values = values :+ ("link", Js.Obj(("client_id", Js.Num(link.clientId)), ("object_id", Js.Num(link.objectId))))
            case None =>
          }

          Js.Obj(values: _*)
        }
      }) (field)
  }

  implicit val reader = upickle.default.Reader[Field] {
    case jsval: Js.Obj =>
      // XXX: In order to compile this it may be required to increase stack size of sbt process.
      // Otherwise optimizer may crush with StackOverflow exception
      (new ((Js.Obj) => Field) {
        def apply(js: Js.Obj): Field = {



          val translation = js("translation").str
          val translationGistClientId = js("translation_gist_client_id").num.toInt
          val translationGistObjectId = js("translation_gist_object_id").num.toInt
          val dataTypeTranslationGistClientId = js("data_type_translation_gist_client_id").num.toInt
          val dataTypeTranslationGistObjectId = js("data_type_translation_gist_object_id").num.toInt
          val createdAt = new Date(js("created_at").num)
          val isTranslatable = js("is_translatable") match {
            case Js.True => true
            case Js.False => false
            case _ => false
          }

          val link = js.value.find(_._1 == "link") match {
            case Some(l) => Some(readJs[Link](l._2))
            case None => None
          }

          // FIXME: First try to get field_client_id/field_object_id
          // FIXME: and fallback to client_id/object_id if failed
          // val clientId = js("field_client_id").num.toInt
          // val objectId = js("field_object_id").num.toInt

          val clientId = js.value.find(_._1 == "field_client_id") match {
            case Some(p) => p._2.num.toInt
            case None => js("client_id").num.toInt
          }

          val objectId = js.value.find(_._1 == "field_object_id") match {
            case Some(p) => p._2.num.toInt
            case None => js("object_id").num.toInt
          }

          // get array of child fields or empty list if there are none
          val fields = js.value.find(_._1 == "contains").getOrElse(("contains", Js.Arr()))._2.asInstanceOf[Js.Arr]

          var subFields = Seq[Field]()
          for (e <- fields.value) {
            // skip non-object elements
            e match {
              case jsObj: Js.Obj =>
                subFields = subFields :+ apply(jsObj)
              case _ =>
            }
          }

          val field = Field(clientId, objectId, translation, translationGistClientId, translationGistObjectId, dataTypeTranslationGistClientId, dataTypeTranslationGistObjectId, isTranslatable, createdAt)
          field.fields = subFields.toJSArray
          field.link = link
          field
        }
      }) (jsval)
  }
}


