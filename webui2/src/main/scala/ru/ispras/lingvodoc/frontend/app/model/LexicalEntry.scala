package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js
import upickle.Js.Obj
import upickle.default._


import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll
import scala.scalajs.js.JSConverters._


@JSExportAll
case class LexicalEntry(override val clientId: Int,
                        override val objectId: Int,
                        var parentClientId: Int,
                        var parentObjectId: Int,
                        var level: String,
                        var published: Boolean,
                        var markedForDeletion: Boolean) extends Object(clientId, objectId) {

  var entities: js.Array[Entity] = js.Array()
}

object LexicalEntry {
  implicit val writer = upickle.default.Writer[LexicalEntry] {
    lexicalEntry => Js.Obj(
      ("client_id", Js.Num(lexicalEntry.clientId)),
      ("object_id", Js.Num(lexicalEntry.objectId)),
      ("parent_client_id", Js.Num(lexicalEntry.parentClientId)),
      ("parent_object_id", Js.Num(lexicalEntry.parentObjectId)),
      ("level", Js.Str(lexicalEntry.level)),
      ("published", if (lexicalEntry.published) Js.True else Js.False),
      ("marked_for_deletion", if (lexicalEntry.markedForDeletion) Js.True else Js.False)
    )
  }

  implicit val reader = upickle.default.Reader[LexicalEntry] {
    case jsobj: Js.Obj =>

      val clientId = jsobj("client_id").asInstanceOf[Js.Num].value.toInt
      val objectId = jsobj("object_id").asInstanceOf[Js.Num].value.toInt
      val parentClientId = jsobj("parent_client_id").asInstanceOf[Js.Num].value.toInt
      val parentObjectId = jsobj("parent_object_id").asInstanceOf[Js.Num].value.toInt
      val level = jsobj("level").asInstanceOf[Js.Str].value

      val isPublished = jsobj("published") match {
        case Js.True => true
        case Js.False => false
        case _ => false
      }

      val isMarkedForDeletion = jsobj("marked_for_deletion") match {
        case Js.True => true
        case Js.False => false
        case _ => false
      }

      // get array of entities
      val entities = jsobj.value.find(_._1 == "contains").getOrElse(("contains", Js.Arr()))._2.asInstanceOf[Js.Arr].value.map(entity => readJs[Entity](entity))

      val entry = LexicalEntry(clientId, objectId, parentClientId, parentObjectId, level, isPublished, isMarkedForDeletion)
      entry.entities = entities.toJSArray
      entry
  }
}


