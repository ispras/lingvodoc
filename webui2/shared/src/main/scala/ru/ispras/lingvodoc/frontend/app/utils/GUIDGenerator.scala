package ru.ispras.lingvodoc.frontend.app.utils

import scala.scalajs.js.annotation.{JSExport, JSExportAll}
import scala.util.Random

@JSExportAll
object GUIDGenerator {
  private [this] val rng = Random

  def generate(): String = {
    "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".map(c => {
      val r = rng.nextInt(16 + 1)
      c.toString match {
        case "x" => Integer.toHexString(r).toString
        case "y" => Integer.toHexString(r & 3 | 0x8).toString
        case _ => c.toString
      }
    }).mkString
  }
}
