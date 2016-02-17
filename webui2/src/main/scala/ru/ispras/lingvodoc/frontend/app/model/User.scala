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
                var birthday: Date,
                var about: String,
                var isActive: Boolean,
                var signupDate: Date) {

  var defaultLocale: Option[Int] = None
  var organizations: Seq[Unit] = Seq()
}

object User {
  implicit val writer = upickle.default.Writer[User] {
    case user => Js.Obj(
      ("id", Js.Num(user.id)),
      ("login", Js.Str(user.login)),
      ("email", Js.Str(user.email)),
      ("name", Js.Str(user.name)),
      ("intl_name", Js.Str(user.intlName)),
      ("birthday", Js.Str(user.birthday.toDateString())),
      ("about", Js.Str(user.about)),
      ("is_active", if (user.isActive) Js.True else Js.False),
      ("signup_date", Js.Str(user.signupDate.toDateString()))
    )
  }

  implicit val reader = upickle.default.Reader[User] {
    case js: Js.Obj =>
      val id = js("id").asInstanceOf[Js.Num].value.toInt
      val login = js("login").asInstanceOf[Js.Str].value
      val email = js("email").asInstanceOf[Js.Str].value
      val name = js("name").asInstanceOf[Js.Str].value
      val intlName = js("intl_name").asInstanceOf[Js.Str].value

      val about = js("about") match {
        case str: Js.Str => str.value
        case _ => ""
      }

      val isActive: Boolean = js("is_active") match {
        case Js.True => true
        case Js.False => false
        case _ => false
      }

      val birthdayTimestamp = Date.parse(js("birthday").asInstanceOf[Js.Str].value)
      val birthday = new Date()
      birthday.setTime(birthdayTimestamp)
      val signupTimestamp = Date.parse(js("signup_date").asInstanceOf[Js.Str].value)
      val signupDate = new Date()
      signupDate.setTime(signupTimestamp)
      User(id, login, email, name, intlName, birthday, about, isActive, signupDate)
  }
}