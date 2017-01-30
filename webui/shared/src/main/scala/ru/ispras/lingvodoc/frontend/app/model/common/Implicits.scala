package ru.ispras.lingvodoc.frontend.app.model.common

import upickle.Js
import upickle.default._
import scala.scalajs.js.Date


object Implicits {

//  implicit val dateWriter: upickle.default.Writer[Date] = upickle.default.Writer[Date] {
//    date: Date =>
//      Js.Num(date.getTime())
//  }
//
//  implicit val dateReader: upickle.default.Reader[Date] = upickle.default.Reader[Date] {
//    case jsval: Js.Num =>
//      new Date(jsval.value)
//  }

  implicit def dateReadWriter = ReadWriter[Date]({
    date: Date => Js.Num(date.getTime())
  }, {
    case value: Js.Value => new Date(value.num)
    case _ => new Date(0)
  })





}
