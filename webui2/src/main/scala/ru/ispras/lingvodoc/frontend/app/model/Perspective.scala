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
                       var translationGistClientId: Int,
                       var translationGistObjectId: Int,
                       var stateTranslationGistClientId: Int,
                       var stateTranslationGistObjectId: Int,
                       var isTemplate: Boolean,
                       var markedForDeletion: Boolean) extends Object(clientId, objectId) {

  var fields: js.Array[Field] = js.Array()
  var blobs: js.Array[File] = js.Array()
}

object Perspective {
  implicit val writer = upickle.default.Writer[Perspective] {
    perspective =>
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
            ("translation_gist_client_id", Js.Num(f.translationGistClientId)),
            ("translation_gist_object_id", Js.Num(f.translationGistObjectId)),
            ("state_translation_gist_client_id", Js.Num(f.stateTranslationGistClientId)),
            ("state_translation_gist_object_id", Js.Num(f.stateTranslationGistObjectId)),
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
          val translationGistClientId = js("translation_gist_client_id").asInstanceOf[Js.Num].value.toInt
          val translationGistObjectId = js("translation_gist_object_id").asInstanceOf[Js.Num].value.toInt
          val stateTranslationGistClientId = js("state_translation_gist_client_id").asInstanceOf[Js.Num].value.toInt
          val stateTranslationGistObjectId = js("state_translation_gist_object_id").asInstanceOf[Js.Num].value.toInt


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

          Perspective(clientId, objectId, parentClientId, parentObjectId, translation, translationGistClientId, translationGistObjectId, stateTranslationGistClientId, stateTranslationGistObjectId, isTemplate, markedForDeletion)
        }
      })(jsval)
  }

  def emptyPerspective(clientId: Int, objectId: Int): Perspective = {
    Perspective(clientId, objectId, Int.MinValue, Int.MinValue, "", Int.MinValue, Int.MinValue, Int.MinValue, Int.MinValue, isTemplate = false, markedForDeletion = false)
  }
}

