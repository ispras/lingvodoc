package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js
import upickle.Js.Obj

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll
import scala.scalajs.js.JSConverters._
import upickle.default._


@JSExportAll
case class Language(override val clientId: Int,
                    override val objectId: Int,
                    var translationGistClientId: Int,
                    var translationGistObjectId: Int,
                    languages: js.Array[Language],
                    dictionaries: js.Array[Dictionary]) extends Object(clientId, objectId) {

  var translation: Option[String] = None


  def getTranslation() = {
    translation.getOrElse("1111")
  }
}

object Language {
  implicit val writer = upickle.default.Writer[Language] {
    language => Js.Obj(
      ("client_id", Js.Num(language.clientId)),
      ("object_id", Js.Num(language.objectId)),
      ("translation_gist_client_id", Js.Num(language.translationGistClientId)),
      ("translation_gist_object_id", Js.Num(language.translationGistObjectId))
    )
  }

  implicit val reader = upickle.default.Reader[Language] {
    case jsval: Js.Obj =>
      // XXX: In order to compile this it may be required to increase stack size of sbt process.
      // Otherwise optimizer may crush with StackOverflow exception
      (new ((Js.Obj) => Language) {
        def apply(js: Js.Obj): Language = {
          val clientId = js("client_id").asInstanceOf[Js.Num].value.toInt
          val objectId = js("object_id").asInstanceOf[Js.Num].value.toInt
          val translationGistClientId = js("translation_gist_client_id").asInstanceOf[Js.Num].value.toInt
          val translationGistObjectId = js("translation_gist_object_id").asInstanceOf[Js.Num].value.toInt

          // get array of child languages or empty list if there are none
          val langs = js.value.find(_._1 == "contains").getOrElse(("contains", Js.Arr()))._2.asInstanceOf[Js.Arr]

          // get array of dictionaries
          val dictsJs = js.value.find(_._1 == "dicts").getOrElse(("dicts", Js.Arr()))._2.asInstanceOf[Js.Arr]
          val dictionaries = dictsJs.value.map(dict => readJs[Dictionary](dict))

          var childLanguages = Seq[Language]()
          for (e <- langs.value) {
            // skip non-object elements
            e match {
              case js1: Obj =>
                childLanguages = childLanguages :+ apply(js1)
              case _ =>
            }
          }
          Language(clientId, objectId, translationGistClientId, translationGistObjectId, childLanguages.toJSArray, dictionaries.toJSArray)
        }
      })(jsval)
  }
}
