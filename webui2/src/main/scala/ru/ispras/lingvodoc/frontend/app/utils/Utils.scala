package ru.ispras.lingvodoc.frontend.app.utils

import ru.ispras.lingvodoc.frontend.app.model.{Field, Language}
import scala.scalajs.js.URIUtils
import scala.scalajs.js.URIUtils._


import org.scalajs.dom

object Utils {

  def flattenLanguages(languages: Seq[Language]) = {
    var acc = Seq[Language]()
    var queue = Vector[Language]()
    queue = queue ++ languages

    while (queue.nonEmpty) {
      val first +: rest = queue
      acc = acc :+ first
      queue = rest ++ first.languages
    }
    acc
  }

  def getUserId: Int = {
    0
  }

  /**
   * Gets data stored into data-lingvodoc attribute
   * @param key id of element
   * @return
   */
  def getData(key: String): Option[String] = {
    val e = Option(dom.document.getElementById(key))
    e match {
      case Some(x) => Option(x.getAttribute("data-lingvodoc"))
      case None => None
    }
  }
}
