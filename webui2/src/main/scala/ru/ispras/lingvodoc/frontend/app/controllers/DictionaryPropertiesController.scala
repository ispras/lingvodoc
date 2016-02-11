package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.extensions.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.model.{Dictionary, Language}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils

import scala.scalajs.concurrent.JSExecutionContext.Implicits.runNow
import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport
import scala.scalajs.js.JSConverters._
import scala.util.{Failure, Success}

@js.native
trait DictionaryPropertiesScope extends Scope {
  var originalDictionary: Dictionary = js.native
  var dictionary: Dictionary = js.native
  var languages: js.Array[Language] = js.native
  var selectedLanguageId: String = js.native
  var dictionaryLanguageId: String = js.native
}

@injectable("DictionaryPropertiesController")
class DictionaryPropertiesController(scope: DictionaryPropertiesScope,
                                     modalInstance: ModalInstance[Dictionary],
                                     backend: BackendService,
                                     params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[DictionaryPropertiesScope](scope) {

  // create a backup copy of dictionary
  scope.originalDictionary = params("dictionary").asInstanceOf[Dictionary]
  scope.dictionary = scope.originalDictionary.copy()

  @JSExport
  def ok() = {
    var update = false

    scope.languages.find(lang => lang.getId == scope.selectedLanguageId) match {
      case Some(selectedLanguage) =>
        // check if language has changed
        scope.languages.find(lang => lang.clientId == scope.originalDictionary.parentClientId &&
          lang.objectId == scope.originalDictionary.parentObjectId) match {
          case Some(originalLanguage) =>
            if (scope.selectedLanguageId != originalLanguage.getId) {
              scope.dictionary.parentClientId = selectedLanguage.clientId
              scope.dictionary.parentObjectId = selectedLanguage.objectId
              update = true
            }
          case None =>
            // dictionary contains reference to non-existent language???
            console.warn("dictionary contains reference to non-existent language.")
        }
      case None =>
        console.warn("selected language doesn't exist.")
    }

    if (scope.dictionary.translation != scope.originalDictionary.translation) {
      update = true
    }

    if (update) {
      backend.updateDictionary(scope.dictionary) onComplete {
        case Success(_) => modalInstance.close(scope.dictionary)
        case Failure(e) =>
          modalInstance.dismiss(())
      }
    } else {
      modalInstance.dismiss(())
    }
  }

  @JSExport
  def cancel() = {
    modalInstance.dismiss(())
  }

  backend.getLanguages onComplete {
    case Success(languages) =>
      scope.languages = utils.Utils.flattenLanguages(languages).toJSArray
      languages.find(lang => lang.clientId == scope.dictionary.parentClientId &&
        lang.objectId == scope.dictionary.parentObjectId) match {
        case Some(language) =>
          scope.selectedLanguageId = language.getId
        case None =>
          // dictionary contains reference to non-existent language???
          console.warn("dictionary contains reference to non-existent language.")
      }

    case Failure(e) => println(e.getMessage)
  }
}
