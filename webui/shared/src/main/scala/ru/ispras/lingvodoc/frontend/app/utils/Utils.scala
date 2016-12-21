package ru.ispras.lingvodoc.frontend.app.utils

import ru.ispras.lingvodoc.frontend.app.model.{Field, Language, TranslationGist}

import scala.scalajs.js.URIUtils
import scala.scalajs.js.URIUtils._
import org.scalajs.dom

import scala.annotation.tailrec
import scala.scalajs.js
import scala.scalajs.js.typedarray.{ArrayBuffer, Uint8Array}

object Utils {


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


object Base64Utils {

  implicit class ArrayBufferBase64(val src: ArrayBuffer) {
    def toBase64: String = {
      val arr = js.Array[Byte]()
      val data = new Uint8Array(src)
      for (i <- 0 until data.byteLength) {
        arr.push(data(i).toByte)
      }
      dom.window.btoa(new String(arr.toArray, "Latin1"))
    }
  }

  implicit class StringBufferBase64(val src: String) {
    def toBase64: String = {
      dom.window.btoa(src)
    }
  }
}


