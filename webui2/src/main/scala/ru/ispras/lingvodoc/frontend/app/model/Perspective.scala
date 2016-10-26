package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll
import scala.scalajs.js.JSConverters._



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
  var metadata: js.Array[String] = js.Array()
}

object Perspective {
  implicit val writer = upickle.default.Writer[Perspective] {
    perspective: Perspective =>
      // serialize fields
      val fields = perspective.fields.map {
        field => Field.writer.write(field)
      }.toSeq

      val meta = perspective.metadata.map(k => Js.Str(k))

      Js.Obj(
        ("client_id", Js.Num(perspective.clientId)),
        ("object_id", Js.Num(perspective.objectId)),
        ("parent_client_id", Js.Num(perspective.parentClientId)),
        ("parent_object_id", Js.Num(perspective.parentObjectId)),
        ("translation", Js.Str(perspective.translation)),
        ("translation_gist_client_id", Js.Num(perspective.translationGistClientId)),
        ("translation_gist_object_id", Js.Num(perspective.translationGistObjectId)),
        ("state_translation_gist_client_id", Js.Num(perspective.stateTranslationGistClientId)),
        ("state_translation_gist_object_id", Js.Num(perspective.stateTranslationGistObjectId)),
        ("is_template", if (perspective.isTemplate) Js.True else Js.False),
        ("marked_for_deletion", if (perspective.markedForDeletion) Js.True else Js.False),
        ("additional_metadata", Js.Arr(meta:_*)),
        ("fields", Js.Arr(fields:_*))
      )

  }

  implicit val reader = upickle.default.Reader[Perspective] {
    case js: Js.Obj =>
      val clientId = js("client_id").num.toInt
      val objectId = js("object_id").num.toInt
      val parentClientId = js("parent_client_id").num.toInt
      val parentObjectId = js("parent_object_id").num.toInt
      val translation = js("translation").str
      val translationGistClientId = js("translation_gist_client_id").num.toInt
      val translationGistObjectId = js("translation_gist_object_id").num.toInt
      val stateTranslationGistClientId = js("state_translation_gist_client_id").num.toInt
      val stateTranslationGistObjectId = js("state_translation_gist_object_id").num.toInt

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

      val meta = js.value.find(_._1 == "additional_metadata").getOrElse(("additional_metadata", Js.Arr()))._2.arr.map(_.str)

      val perspective = Perspective(clientId, objectId, parentClientId, parentObjectId, translation, translationGistClientId, translationGistObjectId, stateTranslationGistClientId, stateTranslationGistObjectId, isTemplate, markedForDeletion)
      perspective.metadata = meta.toJSArray
      perspective
  }

  def emptyPerspective(clientId: Int, objectId: Int): Perspective = {
    Perspective(clientId, objectId, Int.MinValue, Int.MinValue, "", Int.MinValue, Int.MinValue, Int.MinValue, Int.MinValue, isTemplate = false, markedForDeletion = false)
  }
}

