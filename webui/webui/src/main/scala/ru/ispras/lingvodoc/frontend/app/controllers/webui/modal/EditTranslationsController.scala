package ru.ispras.lingvodoc.frontend.app.controllers.webui


import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs.extensions.ModalService
import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseController
import ru.ispras.lingvodoc.frontend.app.model.{Location => _, _}
import ru.ispras.lingvodoc.frontend.app.services._
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.scalajs.js.{Dynamic, Object}


@js.native
trait EditTranslationsScope extends Scope {
  var groupedGists: js.Array[Object with Dynamic] = js.native

}


@injectable("EditTranslationsController")
class EditTranslationsController(scope: EditTranslationsScope,
                                 params: RouteParams,
                                 location: Location,
                                 val modal: ModalService,
                                 userService: UserService,
                                 val backend: BackendService,
                                 timeout: Timeout,
                                 val exceptionHandler: ExceptionHandler)
  extends BaseController(scope, modal, timeout)
    with AngularExecutionContextProvider {

  private[this] var locales: Seq[Locale] = Seq[Locale]()
  private[this] var existingAtoms: Seq[TranslationAtom] = Seq[TranslationAtom]()

  scope.groupedGists = js.Array[Object with Dynamic]()


  @JSExport
  def getAvailableLocales(gist: TranslationGist, currentAtom: TranslationAtom): js.Array[Locale] = {
    val currentLocale = locales.find(_.id == currentAtom.localeId).get
    val otherTranslations = gist.atoms.filterNot(atom => atom.equals(currentAtom))
    val availableLocales = locales.filterNot(_.equals(currentLocale)).filter(locale => !otherTranslations.exists(translation => translation.localeId == locale.id)).toList
    (currentLocale :: availableLocales).toJSArray
  }

  @JSExport
  def addAtom(gist: TranslationGist): Unit = {
    val currentLocaleId = Utils.getLocale().getOrElse(2)
    val translation = if (gist.atoms.exists(_.localeId == currentLocaleId)) {
      // pick next available locale
      locales.filterNot(locale => gist.atoms.exists(name => name.localeId == locale.id)).toList match {
        case firstLocale :: _ =>
          Option(LocalizedString(firstLocale.id, ""))
        case Nil =>
          Option.empty[LocalizedString]
      }
    } else {
      // add translation with current locale pre-selected
      Option(LocalizedString(currentLocaleId, ""))
    }

    translation.foreach { str =>
      val atom = TranslationAtom(-1, -1, gist.clientId, gist.objectId, str.str, str.localeId)
      gist.atoms = gist.atoms :+ atom
    }
  }

  @JSExport
  def getCurrentTranslation(gist: TranslationGist): String = {
    val currentLocaleId = Utils.getLocale().getOrElse(2)
    gist.atoms.map(a => (a.localeId, a.content)).find(_._1 == currentLocaleId).map(_._2).getOrElse("")
  }

  @JSExport
  def updateGist(gist: TranslationGist): Unit = {
    gist.atoms.filter(atom => atom.clientId < 0 && atom.objectId < 0).toSeq.foreach { newAtom =>
      val localizedString = LocalizedString(newAtom.localeId, newAtom.content)
      backend.createTranslationAtom(CompositeId.fromObject(gist), localizedString) map { atomId =>
        backend.translationAtom(atomId) map { atom =>
          existingAtoms = existingAtoms :+ atom
        }
      }
    }

    gist.atoms.filterNot(atom => atom.clientId < 0 && atom.objectId < 0) foreach { atom =>
      backend.updateTranslationAtom(atom)
    }
  }

  @JSExport
  def atomExists(atom: TranslationAtom): Boolean = existingAtoms.exists(a => a.clientId == atom.clientId && a.objectId == atom.objectId)


  load(() => {

    backend.getLocales() map { l =>
      locales = l
    }

    backend.allTranslationGists() map { gists =>
      scope.groupedGists = gists.groupBy(_.gistType).toSeq.map(s => js.Dynamic.literal("type" -> s._1, "gists" -> s._2.toJSArray)).toJSArray
      existingAtoms = gists.map(_.atoms).flatMap(_.toSeq)
    } recover {
      case e: Throwable =>
        console.error("This page is not available!")
        location.path("/")
    }
  })

  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}
}

