package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js
import upickle.default._

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll
import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console
import upickle.Js._



@JSExportAll
case class Entity(override val clientId: Int,
                  override val objectId: Int,
                  var parentClientId: Int,
                  var parentObjectId: Int,
                  var level: String,
                  var published: Boolean,
                  var fieldClientId: Int,
                  var fieldObjectId: Int,
                  var content: String,
                  var localeId: Int
                 ) extends Object(clientId, objectId) {

  var entities: js.Array[Entity] = js.Array()
  var metadata: js.Array[MetaData] = js.Array()
  var link: Option[Link] = None
}

object Entity {
  implicit val writer = upickle.default.Writer[Entity] {
    // FIXME: add link field
    t => Js.Obj(
      ("client_id", Js.Num(t.clientId)),
      ("object_id", Js.Num(t.objectId)),
      ("parent_client_id", Js.Num(t.parentClientId)),
      ("parent_object_id", Js.Num(t.parentObjectId)),
      ("level", Js.Str(t.level)),
      ("published", if (t.published) Js.True else Js.False),
      ("field_client_id", Js.Num(t.fieldClientId)),
      ("field_object_id", Js.Num(t.fieldObjectId)),
      ("content", Js.Str(t.content)),
      ("locale_id", Js.Num(t.localeId))
    )
  }


  implicit val reader = upickle.default.Reader[Entity] {
    case jsobj: Js.Obj =>
      (new ((Js.Obj) => Entity) {
        def apply(jsVal: Js.Obj): Entity = {
          val clientId = jsVal("client_id").num.toInt
          val objectId = jsVal("object_id").num.toInt
          val parentClientId = jsVal("parent_client_id").num.toInt
          val parentObjectId = jsVal("parent_object_id").num.toInt
          val level = jsVal("level").str
          val fieldClientId = jsVal("field_client_id").num.toInt
          val fieldObjectId = jsVal("field_object_id").num.toInt

          val content = jsVal.value.find(_._1 == "content") match {
            case Some(c) => c._2 match {
              case Str(value) => value
              case Obj(value) => ""
              case Arr(value) => ""
              case Num(value) => ""
              case False => ""
              case True => ""
              case Null => ""
            }
            case None => ""
          }


          val localeId = jsVal("locale_id") match {
            case e: Js.Num => jsVal("locale_id").num.toInt
            case _ => 2
          }

          val isPublished = jsVal("published") match {
            case Js.True => true
            case Js.False => false
            case _ => false
          }

          // optional link
          val link = jsVal.value.find(_._1 == "link_client_id") match {
            case Some(link_client) => jsVal.value.find(_._1 == "link_object_id") match {
              case Some(link_object) => Some(Link(link_client._2.num.toInt, link_object._2.num.toInt))
              case None => None
            }
            case None => None
          }

          val e = Entity(clientId, objectId, parentClientId, parentObjectId, level, isPublished, fieldClientId, fieldObjectId, content, localeId)

          // get array of entities
          val entities = jsVal.value.find(_._1 == "contains").getOrElse(("contains", Js.Arr()))._2.asInstanceOf[Js.Arr]

          // parse list of subentities
          var subEntities = Seq[Entity]()
          for (jsEntity <- entities.value) {
            // skip non-object elements
            jsEntity match {
              case js1: Obj => subEntities = subEntities :+ apply(js1)
              case _ =>
            }
          }
          e.entities = subEntities.toJSArray
          e.link = link
          e
        }
      })(jsobj)
  }

}