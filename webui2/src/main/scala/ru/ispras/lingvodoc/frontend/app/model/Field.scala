package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js
import upickle.default._


import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.{JSExportAll, JSExport}

@JSExportAll
case class Field(override val clientId: Int,
                 override val objectId: Int,
                 var entityType: String,
                 var entityTypeTranslation: String,
                 var dataType: String,
                 var dataTypeTranslation: String,
                 var level: String,
                 var position: Int,
                 var status: String,
                 var fields: js.Array[Field]) extends Object(clientId, objectId) {

  var group: Option[String] = None
}

object Field {
  implicit val writer = upickle.default.Writer[Field] {
    case field =>
      (new (Field => Js.Obj) {
        override def apply(f: Field): Js.Obj = {

          val contains = f.fields.map(e => apply(e)).toSeq
          Js.Obj(
            ("client_id", Js.Num(f.clientId)),
            ("object_id", Js.Num(f.objectId)),
            ("data_type", Js.Str(f.dataType)),
            ("data_type_translation", Js.Str(f.dataTypeTranslation)),
            ("entity_type", Js.Str(f.entityType)),
            ("entity_type_translation", Js.Str(f.entityTypeTranslation)),
            ("level", Js.Str(f.level)),
            ("status", Js.Str(f.status)),
            ("position", Js.Num(f.position)),
            ("contains", Js.Arr(contains:_*))
          )
        }
      })(field)
  }

  implicit val reader = upickle.default.Reader[Field] {
    case jsval: Js.Obj =>
      // XXX: In order to compile this it may be required to increase stack size of sbt process.
      // Otherwise optimizer may crush with StackOverflow exception
      (new ((Js.Obj) => Field) {
        def apply(js: Js.Obj): Field = {

          val clientId = js("client_id").asInstanceOf[Js.Num].value.toInt
          val objectId = js("object_id").asInstanceOf[Js.Num].value.toInt
          val entityType = js("entity_type").asInstanceOf[Js.Str].value
          val entityTypeTranslation = js("entity_type_translation").asInstanceOf[Js.Str].value
          val dataType = js("data_type").asInstanceOf[Js.Str].value
          val dataTypeTranslation = js("data_type_translation").asInstanceOf[Js.Str].value
          val level = js("level").asInstanceOf[Js.Str].value
          val status = js("status").asInstanceOf[Js.Str].value
          val position = js("position").asInstanceOf[Js.Num].value.toInt

          val group = js.value.find(_._1 == "group").getOrElse(("group", null))._2.asInstanceOf[Js.Str].value

          // get array of child fields or empty list if there are none
          val fields = js.value.find(_._1 == "contains").getOrElse(("contains", Js.Arr()))._2.asInstanceOf[Js.Arr]

          var subfields = Seq[Field]()
          for (e <- fields.value) {
            // skip non-object elements
            e match {
              case jsObj: Js.Obj =>
                subfields = subfields :+ apply(jsObj)
              case _ =>
            }
          }
          val field = Field(clientId, objectId, entityType, entityTypeTranslation, dataType, dataTypeTranslation, level,
            position, status, subfields.toJSArray)
          field.group = Option(group)
          field
        }
      })(jsval)
  }
}