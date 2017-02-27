package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.controllers.common.Translatable
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait DictionaryPropertiesScope extends Scope {
  var dictionary: Dictionary = js.native
  var languages: js.Array[Language] = js.native
  var translations: js.Array[LocalizedString] = js.native
  var selectedLanguageId: String = js.native
}

@injectable("DictionaryPropertiesController")
class DictionaryPropertiesController(scope: DictionaryPropertiesScope,
                                     modalInstance: ModalInstance[Dictionary],
                                     backend: BackendService,
                                     val timeout: Timeout,
                                     val exceptionHandler: ExceptionHandler,
                                     params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[DictionaryPropertiesScope](scope) with AngularExecutionContextProvider {

  // create a backup copy of dictionary
  private[this] val dictionary = params("dictionary").asInstanceOf[Dictionary]
  private[this] var locales = js.Array[Locale]()

  scope.dictionary = dictionary.copy()
  scope.languages = js.Array()
  scope.translations = js.Array()
  scope.selectedLanguageId = ""

  // dictionary translation gist
  private [this] var translationGist: Option[TranslationGist] = None

  load()

  @JSExport
  def getLocaleName(localeId: Int): String = {
    locales.find(l => l.id == localeId) match {
      case Some(locale) => locale.name
      case None => "Unknown locale"
    }
  }

  @JSExport
  def getAvailableLocales(translations: js.Array[LocalizedString], currentTranslation: LocalizedString): js.Array[Locale] = {
    val currentLocale = locales.find(_.id == currentTranslation.localeId).get
    val otherTranslations = translations.filterNot(translation => translation.equals(currentTranslation))
    val availableLocales = locales.filterNot(_.equals(currentLocale)).filter(locale => !otherTranslations.exists(translation => translation.localeId == locale.id)).toList
    (currentLocale :: availableLocales).toJSArray
  }

  @JSExport
  def addNameTranslation(): Unit = {
    val currentLocaleId = Utils.getLocale().getOrElse(2)
    if (scope.translations.exists(_.localeId == currentLocaleId)) {
      // pick next available locale
      locales.filterNot(locale => scope.translations.exists(name => name.localeId == locale.id)).toList match {
        case firstLocale :: otherLocales =>
          scope.translations = scope.translations :+ LocalizedString(firstLocale.id, "")
        case Nil =>
      }
    } else {
      // add translation with current locale pre-selected
      scope.translations = scope.translations :+ LocalizedString(currentLocaleId, "")
    }
  }



  @JSExport
  def ok(): Unit = {

    var updateRequests = Seq[Future[Unit]]()

    scope.languages.find(lang => lang.getId == scope.selectedLanguageId) match {
      case Some(selectedLanguage) =>
        // check if language has changed
        if (selectedLanguage.clientId != dictionary.parentClientId || selectedLanguage.objectId != dictionary.parentObjectId) {
          // update language
          scope.dictionary.parentClientId = selectedLanguage.clientId
          scope.dictionary.parentObjectId = selectedLanguage.objectId

          updateRequests = updateRequests :+ backend.updateDictionary(scope.dictionary)
        }
      case None => throw new ControllerException("Dictionary contains reference to non-existent language.")
    }

    val createdAtoms = scope.translations.filterNot(translation => translationGist.exists(_.atoms.exists(atom => atom.localeId == translation.localeId)))

    createdAtoms.foreach { atom =>
      translationGist.foreach { gist =>
        backend.createTranslationAtom(CompositeId.fromObject(gist), atom)
      }
    }

    // create a list of updated translation atoms
    // Array of (atom, updatedString)
    val updatedAtoms = translationGist.map { gist =>
      gist.atoms.sortBy(_.localeId).map(atom => (atom, LocalizedString(atom.localeId, atom.content))) zip scope.translations.filter(t => gist.atoms.exists(_.localeId == t.localeId)).sortBy(_.localeId) flatMap {
        case (original, updated) =>
          if (!original._2.str.equals(updated.str) && updated.str.nonEmpty) Some(original._1, updated) else None
      }
    }

    // update atoms
    updatedAtoms.foreach { updated =>
      updateRequests = updateRequests ++ updated.map { case (atom, str) =>
        atom.content = str.str
        backend.updateTranslationAtom(atom)
      }.toSeq
    }

    Future.sequence(updateRequests) map { _ =>
      modalInstance.close(scope.dictionary)
    }
  }

  @JSExport
  def cancel() = {
    modalInstance.dismiss(())
  }


  private[this] def load() = {

    // load list of locales
    backend.getLocales onComplete {
      case Success(l) =>
        // generate localized names
        locales = l.toJSArray
      case Failure(e) =>
    }

    // get translations
    backend.translationGist(dictionary.translationGistClientId, dictionary.translationGistObjectId) onComplete {
      case Success(gist) =>

        translationGist = Some(gist)
        scope.translations = gist.atoms.sortBy(_.localeId).map(atom => LocalizedString(atom.localeId, atom.content)).toJSArray

        // get list of languages
        backend.getLanguages onComplete {
          case Success(languages) =>
            scope.languages = utils.Utils.flattenLanguages(languages).toJSArray
            scope.languages.find(lang => lang.clientId == dictionary.parentClientId &&
              lang.objectId == dictionary.parentObjectId) match {
              case Some(language) =>
                scope.selectedLanguageId = language.getId
              case None =>
                // dictionary contains reference to non-existent language???
                console.warn("dictionary contains reference to non-existent language.")
            }

          case Failure(e) => println(e.getMessage)
        }

      case Failure(e) =>
    }
  }
}
