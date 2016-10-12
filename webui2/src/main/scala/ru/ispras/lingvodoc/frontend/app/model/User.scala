package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js

import scala.scalajs.js.Date
import scala.scalajs.js.annotation.JSExportAll


@JSExportAll
case class User(id: Int,
                var login: String,
                var email: String,
                var name: String,
                var intlName: String,
                var birthday: String,
                var isActive: Boolean,
                var createdAt: Double) {

  var defaultLocale: Option[Int] = None
  var organizations: Seq[Unit] = Seq()
}

object User {
  implicit val writer = upickle.default.Writer[User] {
    user => Js.Obj(
      ("id", Js.Num(user.id)),
      ("login", Js.Str(user.login)),
      ("email", Js.Str(user.email)),
      ("name", Js.Str(user.name)),
      ("intl_name", Js.Str(user.intlName)),
      ("birthday", Js.Str(user.birthday)),
      ("is_active", if (user.isActive) Js.True else Js.False),
      ("created_at", Js.Num(user.createdAt))
    )
  }

  implicit val reader = upickle.default.Reader[User] {
    case js: Js.Obj =>
      val id = js("id").asInstanceOf[Js.Num].value.toInt
      val login = js("login").asInstanceOf[Js.Str].value
      val email = js("email").asInstanceOf[Js.Str].value
      val name = js("name").asInstanceOf[Js.Str].value
      val intlName = js("intl_name").asInstanceOf[Js.Str].value

      val isActive: Boolean = js("is_active") match {
        case Js.True => true
        case Js.False => false
        case _ => false
      }

      val birthday = js("birthday").str
      val createdAtTimestamp = js("created_at").num

      org.scalajs.dom.console.log(birthday)
      org.scalajs.dom.console.log(createdAtTimestamp)

      User(id, login, email, name, intlName, birthday, isActive, createdAtTimestamp)
  }
}