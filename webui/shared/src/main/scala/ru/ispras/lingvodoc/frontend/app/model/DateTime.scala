package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js
import upickle.default._
import scala.scalajs.js.Date
import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class DateTime(date: Date) {
  def timestamp(): Double = date.getTime()
  def dateString(): String = {
    date.toDateString()
  }
}

object DateTime {
  implicit def datetimeReadWriter = ReadWriter[DateTime]({
    date: DateTime => Js.Num(date.timestamp() / 1000.0)
  }, {
    case value: Js.Num => DateTime(new Date(value.value * 1000.0))
    case _ => DateTime(new Date(0))
  })
}
