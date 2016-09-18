package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import ru.ispras.lingvodoc.frontend.app.services.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model.{Dictionary, Language, LocalizedString, TranslationGist}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

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
                                     params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[DictionaryPropertiesScope](scope) {

  // create a backup copy of dictionary
  private[this] val dictionary = params("dictionary").asInstanceOf[Dictionary]
  scope.dictionary = dictionary.copy()

  // dictionary translation gist
  private [this] var translationGist: Option[TranslationGist] = None

  @JSExport
  def ok() = {
    scope.languages.find(lang => lang.getId == scope.selectedLanguageId) match {
      case Some(selectedLanguage) =>
        // check if language has changed
        if (selectedLanguage.clientId != dictionary.parentClientId || selectedLanguage.objectId != dictionary.parentObjectId) {
          // update language
          scope.dictionary.parentClientId = selectedLanguage.clientId
          scope.dictionary.parentObjectId = selectedLanguage.objectId

          backend.updateDictionary(scope.dictionary) onComplete {
            case Success(_) =>

              // create a list of updated translation atoms
              // Array of (atom, updatedString)
              val updatedAtoms = translationGist.map { gist =>
                gist.atoms.map(atom => (atom, LocalizedString(atom.localeId, atom.content))) zip scope.translations flatMap {
                  case (original, updated) => if (original._2.str.equals(updated.str)) Some(original._1, updated) else None
                }
              }
              // update atoms
              updatedAtoms.foreach { updated =>
                val reqs = updated.map { case (atom, str) =>
                  atom.content = str.str
                  backend.updateTranslationAtom(atom)
                }.toSeq

                Future.sequence(reqs) onComplete {
                  case Success(_) => modalInstance.close(scope.dictionary)
                  case Failure(e) =>
                }
              }

            case Failure(e) =>
          }
        }
      case None => throw new ControllerException("Dictionary contains reference to non-existent language.")
    }
  }

  @JSExport
  def cancel() = {
    modalInstance.dismiss(())
  }


  private[this] def load() = {

    // get translations
    backend.translationGist(dictionary.translationGistClientId, dictionary.translationGistObjectId) onComplete {
      case Success(gist) =>

        translationGist = Some(gist)
        scope.translations = gist.atoms.map(atom => LocalizedString(atom.localeId, atom.content)).toJSArray

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
