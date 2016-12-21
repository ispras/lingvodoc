package ru.ispras.lingvodoc.frontend.app.utils

import org.scalajs.dom
import ru.ispras.lingvodoc.frontend.app.model.{Language, TranslationGist}

import scala.scalajs.js

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


object ConversionUtils {
  implicit class ArrayBufferBase64(val src: js.typedarray.ArrayBuffer) {
    import com.github.marklister.base64.Base64.Encoder
    def toBase64: String = {
      val arr = js.Array[Byte]()
      val data = new js.typedarray.Uint8Array(src)
      for (i <- 0 until data.byteLength) {
        arr.push(data(i).toByte)
      }
      arr.toArray.toBase64
    }
  }

  implicit class JSArrayBufferToString(val src: js.typedarray.ArrayBuffer) {
    def toStr(encoding: String = "UTF-8"): String = {
      val c = new js.typedarray.Uint8Array(src)
      val arr = js.Array[Byte]()
      for (i <- 0 until c.byteLength) {
        arr.push(c(i).toByte)
      }
      new String(arr.toArray, encoding)
    }
  }
}


