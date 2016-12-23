package ru.ispras.lingvodoc.frontend.app.controllers.traits

import com.greencatsoft.angularjs.Controller
import ru.ispras.lingvodoc.frontend.app.model.Language
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.scalajs.js.annotation.JSExport


trait LanguageEdit {
  this: Controller[_] =>

  private[this] var indentation = Map[String, Int]()

  @JSExport
  def languagePadding(language: Language): String = {
    "&nbsp;&nbsp;&nbsp;" * indentation.getOrElse(language.getId, 0)
  }

  protected def computeIndentation(languagesTree: Seq[Language]): Unit = {
    indentation = indentations(languagesTree)
  }

  private[this] def getDepth(language: Language, tree: Seq[Language], depth: Int = 0): Option[Int] = {
    if (tree.exists(_.getId == language.getId)) {
      Some(depth)
    } else {
      for (lang <- tree) {
        val r = getDepth(language, lang.languages.toSeq, depth + 1)
        if (r.nonEmpty) {
          return r
        }
      }
      Option.empty[Int]
    }
  }

  private[this] def indentations(tree: Seq[Language]) = {
    val languages = Utils.flattenLanguages(tree)
    languages.map { language =>
      language.getId -> getDepth(language, tree).get
    }.toMap
  }
}
