package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model.{Language, Locale, LocalizedString}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}



@js.native
trait CreateLanguageScope extends Scope {
  var names: js.Array[LocalizedString] = js.native
  var locales: js.Array[Locale] = js.native
}

@injectable("CreateLanguageController")
class CreateLanguageController(scope: CreateLanguageScope,
                               modalInstance: ModalInstance[Language],
                               backend: BackendService,
                               val timeout: Timeout,
                               val exceptionHandler: ExceptionHandler,
                               params: js.Dictionary[js.Function0[js.Any]]) extends AbstractController[CreateLanguageScope](scope)
  with AngularExecutionContextProvider {

  val parentlanguage = params.find(_._1 == "parentLanguage") match {
    case Some(_) => params("parentLanguage").asInstanceOf[Option[Language]]
    case None => None
  }


  scope.names = (LocalizedString(Utils.getLocale().getOrElse(2), "") :: Nil).toJSArray
  scope.locales = js.Array()

  load()

  @JSExport
  def getAvailableLocales(translations: js.Array[LocalizedString], currentTranslation: LocalizedString): js.Array[Locale] = {
    val currentLocale = scope.locales.find(_.id == currentTranslation.localeId).get
    val otherTranslations = translations.filterNot(translation => translation.equals(currentTranslation))
    val availableLocales = scope.locales.filterNot(_.equals(currentLocale)).filter(locale => !otherTranslations.exists(translation => translation.localeId == locale.id)).toList
    (currentLocale :: availableLocales).toJSArray
  }


  @JSExport
  def addNameTranslation() = {
    val currentLocaleId = Utils.getLocale().getOrElse(2)
    if (scope.names.exists(_.localeId == currentLocaleId)) {
      // pick next available locale
      scope.locales.filterNot(locale => scope.names.exists(name => name.localeId == locale.id)).toList match {
        case firstLocale :: otherLocales =>
          scope.names = scope.names :+ LocalizedString(firstLocale.id, "")
        case Nil =>
      }
    } else {
      // add translation with current locale pre-selected
      scope.names = scope.names :+ LocalizedString(currentLocaleId, "")
    }
  }

  @JSExport
  def ok() = {
    if (!scope.names.forall(_.str.isEmpty)) {
      backend.createLanguage(scope.names, parentlanguage) onComplete {
        case Success(langId) =>
          backend.getLanguage(langId) map {language => modalInstance.close(language)}
        case Failure(e) =>
      }
    }
  }

  @JSExport
  def cancel() = {
    modalInstance.dismiss(())
  }


  private[this] def load() = {
    backend.getLocales() onComplete {
      case Success(locales) => scope.locales = locales.toJSArray
      case Failure(e) => throw ControllerException("Failed to get list of supported locales", e)
    }
  }
}
