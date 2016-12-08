package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js
import upickle.Js._
import upickle.default._

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class SearchResult(override val clientId: Int,
                        override val objectId: Int,
                        var parentClientId: Int,
                        var parentObjectId: Int,
                        var translation: String,
                        var translationGistClientId: Int,
                        var translationGistObjectId: Int,
                        var stateTranslationGistClientId: Int,
                        var stateTranslationGistObjectId: Int,
                        var isTemplate: Boolean,
                        var markedForDeletion: Boolean,
                        var lexicalEntry: LexicalEntry) extends Object(clientId, objectId) {}


object SearchResult {
  implicit val writer = upickle.default.Writer[SearchResult] {
    perspective =>
      (new (SearchResult => Js.Obj) {
        override def apply(f: SearchResult): Js.Obj = {

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
            ("marked_for_deletion", if (f.markedForDeletion) Js.True else Js.False)
          )
        }
      })(perspective)
  }

  implicit val reader = upickle.default.Reader[SearchResult] {
    case jsval: Js.Obj =>
      // XXX: In order to compile this it may be required to increase stack size of sbt process.
      // Otherwise optimizer may crush with StackOverflow exception
      (new ((Js.Obj) => SearchResult) {
        def apply(js: Js.Obj): SearchResult = {

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

          val lexicalEntry = readJs[LexicalEntry](js("lexical_entry"))


          SearchResult(clientId, objectId, parentClientId, parentObjectId, translation, translationGistClientId, translationGistObjectId, stateTranslationGistClientId, stateTranslationGistObjectId, isTemplate, markedForDeletion, lexicalEntry)
        }
      })(jsval)
  }

}
