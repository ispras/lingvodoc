package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class Perspective(override val clientId: Int,
                       override val objectId: Int,
                       var parentClientId: Int,
                       var parentObjectId: Int,
                       var translation: String,
                       var translationString: String,
                       var status: String,
                       var isTemplate: Boolean,
                       var markedForDeletion: Boolean) extends Object(clientId, objectId) {

  var fields: js.Array[Field] = js.Array()
  var blobs: js.Array[Blob] = js.Array()
}

object Perspective {
  implicit val writer = upickle.default.Writer[Perspective] {
    case perspective =>
      (new (Perspective => Js.Obj) {
        override def apply(f: Perspective): Js.Obj = {

          // serialize fields
          val fields = f.fields.map {
            field => Field.writer.write(field)
          }.toSeq

          Js.Obj(
            ("client_id", Js.Num(f.clientId)),
            ("object_id", Js.Num(f.objectId)),
            ("parent_client_id", Js.Num(f.parentClientId)),
            ("parent_object_id", Js.Num(f.parentObjectId)),
            ("translation", Js.Str(f.translation)),
            ("translation_string", Js.Str(f.translationString)),
            ("status", Js.Str(f.status)),
            ("is_template", if (f.isTemplate) Js.True else Js.False),
            ("marked_for_deletion", if (f.markedForDeletion) Js.True else Js.False),
            ("fields", Js.Arr(fields:_*))
          )
        }
      })(perspective)
  }

  implicit val reader = upickle.default.Reader[Perspective] {
    case jsval: Js.Obj =>
      // XXX: In order to compile this it may be required to increase stack size of sbt process.
      // Otherwise optimizer may crush with StackOverflow exception
      (new ((Js.Obj) => Perspective) {
        def apply(js: Js.Obj): Perspective = {

          val clientId = js("client_id").asInstanceOf[Js.Num].value.toInt
          val objectId = js("object_id").asInstanceOf[Js.Num].value.toInt
          val parentClientId = js("parent_client_id").asInstanceOf[Js.Num].value.toInt
          val parentObjectId = js("parent_object_id").asInstanceOf[Js.Num].value.toInt
          val translation = js("translation").asInstanceOf[Js.Str].value
          val translationString = js("translation_string").asInstanceOf[Js.Str].value
          val status = js("status").asInstanceOf[Js.Str].value


          val isTemplate = js("is_template") match {
            case Js.True => true
            case Js.False => false
            case _ => false
          }

          val markedForDeletion = js("marked_for_deletion") match {
            case Js.True => true
            case Js.False => false
            case _ => false
          }

          Perspective(clientId, objectId, parentClientId, parentObjectId, translation, translationString, status, isTemplate, markedForDeletion)
        }
      })(jsval)
  }

  def emptyPerspective(clientId: Int, objectId: Int): Perspective = {
    Perspective(clientId, objectId, Int.MinValue, Int.MinValue, "", "", "", isTemplate = false, markedForDeletion = false)
  }
}

