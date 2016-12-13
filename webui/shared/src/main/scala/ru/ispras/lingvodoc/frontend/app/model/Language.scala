package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js
import upickle.Js.Obj

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll
import scala.scalajs.js.JSConverters._
import upickle.default._

import scala.annotation.tailrec


@JSExportAll
case class Language(override val clientId: Int,
                    override val objectId: Int,
                    var translationGistClientId: Int,
                    var translationGistObjectId: Int,
                    var translation: String,
                    languages: js.Array[Language],
                    dictionaries: js.Array[Dictionary]) extends Object(clientId, objectId) {

}

object Language {
  implicit val writer = upickle.default.Writer[Language] {
    language => Js.Obj(
      ("client_id", Js.Num(language.clientId)),
      ("object_id", Js.Num(language.objectId)),
      ("translation_gist_client_id", Js.Num(language.translationGistClientId)),
      ("translation_gist_object_id", Js.Num(language.translationGistObjectId)),
      ("translation", Js.Str(language.translation))
    )
  }

  implicit val reader = upickle.default.Reader[Language] {
    case jsval: Js.Obj =>
      // XXX: In order to compile this it may be required to increase stack size of sbt process.
      // Otherwise optimizer may crush with StackOverflow exception
      (new ((Js.Obj) => Language) {
        def apply(js: Js.Obj): Language = {
          val clientId = js("client_id").num.toInt
          val objectId = js("object_id").num.toInt
          val translationGistClientId = js("translation_gist_client_id").num.toInt
          val translationGistObjectId = js("translation_gist_object_id").num.toInt

          val translation = js.value.find(_._1 == "translation") match {
            case Some(_) => js("translation").str
            case None => "no translation"
          }

          //val translation = js("translation").str

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
          Language(clientId, objectId, translationGistClientId, translationGistObjectId, translation, childLanguages.toJSArray, dictionaries.toJSArray)
        }
      })(jsval)
  }

  def findParentLanguage(language: Language, tree: Seq[Language]): Option[Language] = {
    @tailrec
    def recurseOverChildren(children: Seq[Language]): Option[Language] = {
      children.toList match {
        case Nil => None
        case head :: tail =>
          if(head.languages.exists(_.getId == language.getId))
            Some(head)
          else
            recurseOverChildren((tail ++ head.languages.toList).toSeq)
      }
    }
    recurseOverChildren(tree)
  }
}
