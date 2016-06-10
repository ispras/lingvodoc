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
                    translation: String,
                    translationString: String,
                    languages: js.Array[Language],
                    dictionaries: js.Array[Dictionary]) extends Object(clientId, objectId)

object Language {
  implicit val writer = upickle.default.Writer[Language] {
    case t => Js.Obj(
      ("client_id", Js.Num(t.clientId)),
      ("object_id", Js.Num(t.objectId)),
      ("translation", Js.Str(t.translation)),
      ("translation_string", Js.Str(t.translationString))
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
          val translation = js("translation").asInstanceOf[Js.Str].value
          val translationString = js("translation_string").asInstanceOf[Js.Str].value

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
          Language(clientId, objectId, translation, translationString, childLanguages.toJSArray, dictionaries.toJSArray)
        }
      })(jsval)
  }
}
