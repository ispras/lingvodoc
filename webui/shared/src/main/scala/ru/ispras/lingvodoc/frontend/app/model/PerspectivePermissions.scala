package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class PerspectivePermissions(var read: Boolean, var write: Boolean)


object PerspectivePermissions {
  implicit val writer = upickle.default.Writer[PerspectivePermissions] {
    t =>
      Js.Obj(
        ("read", if (t.read) Js.True else Js.False),
        ("write", if (t.write) Js.True else Js.False)
      )
  }


  implicit val reader = upickle.default.Reader[PerspectivePermissions] {
    case js: Js.Obj =>

      val read = js("read") match {
        case Js.True => true
        case Js.False => false
        case _ => false
      }

      val write = js("write") match {
        case Js.True => true
        case Js.False => false
        case _ => false
      }

      PerspectivePermissions(read, write)
  }
}
