package ru.ispras.lingvodoc.frontend.app.utils

import org.scalajs.dom

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport
import scala.util.matching.Regex
import scala.scalajs.js.URIUtils._

import dom.console

object Cookie {
  
  def get(name: String): Option[String] = {
    new Regex(name + "=([^;]+)").findFirstMatchIn(dom.document.cookie) match {
      case Some(x) => Some(x.group(1))
      case None => None
    }
  }

  def set(name: String, value: String) = {
    val date = new js.Date()
    date.setFullYear(2038) // set expiration date in future
    val cookie = name + "=" + encodeURIComponent(value) + ";" + "path=/;" + "expires=" + date.toUTCString()
    dom.document.cookie = cookie
  }

  def unset(name: String) = {
    val date = new js.Date(0)
    val cookie = name + "=;" + "path=/;" + "expires=" + date.toUTCString()
  }
}
