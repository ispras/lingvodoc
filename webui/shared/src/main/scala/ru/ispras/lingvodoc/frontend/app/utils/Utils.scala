package ru.ispras.lingvodoc.frontend.app.utils

import ru.ispras.lingvodoc.frontend.app.model.{Field, Language, TranslationGist}

import scala.scalajs.js.URIUtils
import scala.scalajs.js.URIUtils._
import org.scalajs.dom

import scala.annotation.tailrec

object Utils {

//  def flattenLanguages1(languages: Seq[Language]) = {
//    var acc = Seq[Language]()
//    var queue = Vector[Language]()
//    queue = queue ++ languages
//
//    while (queue.nonEmpty) {
//      val first +: rest = queue
//      acc = acc :+ first
//      queue = rest ++ first.languages
//    }
//    acc
//  }


  def flattenLanguages(tree: Seq[Language]): Seq[Language] = {
    var languages = Seq[Language]()
    for (language <- tree) {
      languages = languages :+ language
      languages = languages ++ flattenLanguages(language.languages)
    }
    languages
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


  def getLocale(): Option[Int] = {
    Cookie.get("locale_id") match {
      case Some(x) => Some(x.toInt)
      case None => None
    }
  }

  def setLocale(localeId: Int) = {
    Cookie.set("locale_id", localeId.toString)
  }

  /**
    * Gets dataType Name
    * @param dataType
    * @return
    */
  def getDataTypeName(dataType: TranslationGist): String = {
    dataType.atoms.find(_.localeId == 2).get.content
  }
}
