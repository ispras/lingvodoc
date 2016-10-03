package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Scope, Timeout}
import ru.ispras.lingvodoc.frontend.app.services.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport
import scala.scalajs.js.JSConverters._
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
  def ok() = {

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

    // create a list of updated translation atoms
    // Array of (atom, updatedString)
    val updatedAtoms = translationGist.map { gist =>
      gist.atoms.sortBy(_.localeId).map(atom => (atom, LocalizedString(atom.localeId, atom.content))) zip scope.translations flatMap {
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

    Future.sequence(updateRequests) onComplete {
      case Success(_) => modalInstance.close(scope.dictionary)
      case Failure(e) =>
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
                console.log("Selected id=" + scope.selectedLanguageId)

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
