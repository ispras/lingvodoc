package ru.ispras.lingvodoc.frontend.app.utils

import ru.ispras.lingvodoc.frontend.app.model.Language

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


}
