package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js
import upickle.Js._

import scala.scalajs.js.annotation.JSExportAll


@JSExportAll
case class Role(name: String, subjectOverride: Boolean, subject: Option[CompositeId])

object Role {
  implicit val writer = upickle.default.Writer[Role] {
    role: Role =>
      Js.Obj(
        ("name", Js.Str(role.name))
      )
  }

  implicit val reader = upickle.default.Reader[Role] {
    case js: Js.Obj =>
      val name = js("name").str
      val subjectOverride = js("subject_override") match {
        case True => true
        case False => false
        case _ => false
      }

      val subject = js.value.find(_._1 == "subject_client_id") flatMap { case (_, clientId) =>
        js.value.find(_._1 == "subject_object_id") map { case (_, objectId) =>
            CompositeId(clientId.num.toInt, objectId.num.toInt)
        }
      }

      Role(name, subjectOverride, subject)
  }
}