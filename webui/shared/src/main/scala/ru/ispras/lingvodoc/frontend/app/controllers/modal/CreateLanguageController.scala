package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.ModalInstance
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{LanguageEdit, LoadingPlaceholder}
import ru.ispras.lingvodoc.frontend.app.model.{CompositeId, Language, Locale, LocalizedString}
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait CreateLanguageScope extends Scope {
  var names: js.Array[LocalizedString] = js.native
  var locales: js.Array[Locale] = js.native
  var languages: js.Array[Language] = js.native
  var languageId: UndefOr[String] = js.native
  var progressBar: Boolean = js.native
}

@injectable("CreateLanguageController")
class CreateLanguageController(scope: CreateLanguageScope,
                               modalInstance: ModalInstance[Language],
                               backend: BackendService,
                               val timeout: Timeout,
                               val exceptionHandler: ExceptionHandler,
                               params: js.Dictionary[js.Function0[js.Any]]) extends AbstractController[CreateLanguageScope](scope)
  with AngularExecutionContextProvider
  with LanguageEdit
  with LoadingPlaceholder {

  // edit language
  private[this] val language = params.find(_._1 == "language") map { case (_, inst) =>
    inst.asInstanceOf[Language]
  }

  // parent language if present
  private[this] var parentLanguage = params.find(_._1 == "parentLanguage") flatMap { case (_, inst) =>
    inst.asInstanceOf[Option[Language]]
  }

  // list of already existing translations
  private[this] var readOnlyTranslations = Set[Int]()

  scope.names = (LocalizedString(Utils.getLocale().getOrElse(2), "") :: Nil).toJSArray
  scope.locales = js.Array[Locale]()
  scope.languages = js.Array[Language]()
  scope.languageId = parentLanguage.map(_.getId).orUndefined
  scope.progressBar = true

  @JSExport
  def getAvailableLocales(translations: js.Array[LocalizedString], currentTranslation: LocalizedString): js.Array[Locale] = {
    scope.locales.find(_.id == currentTranslation.localeId) match {
      case Some(currentLocale) =>
        val otherTranslations = translations.filterNot(translation => translation.equals(currentTranslation))
        val availableLocales = scope.locales.filterNot(_.equals(currentLocale)).filter(locale => !otherTranslations.exists(translation => translation.localeId == locale.id)).toList
        (currentLocale :: availableLocales).toJSArray
      case None =>
        js.Array[Locale]()
    }
  }

  @JSExport
  def isReadOnly(localeId: Int): Boolean = {
    readOnlyTranslations.contains(localeId)
  }

  @JSExport
  def addNameTranslation(): Unit = {
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
  def getLanguageName(): UndefOr[String] = {
    language.map(_.translation).orUndefined
  }

  @JSExport
  def ok(): Unit = {

    import org.scalajs.dom.console

    scope.progressBar = true

    language match {

      // update existing language
      case Some(lang) =>
        // create newly added translations
        val atomRequests = scope.names.filterNot(translation => readOnlyTranslations.contains(translation.localeId)).filter(_.str.nonEmpty).toSeq map { translation =>
          backend.createTranslationAtom(CompositeId(lang.translationGistClientId, lang.translationGistObjectId), translation)
        }

        Future.sequence(atomRequests) map { _ =>

          // update parent language if it is changed
          val selectedParentLanguage = Utils.flattenLanguages(scope.languages).find(_.getId == scope.languageId)

          val needUpdate: Boolean = parentLanguage match {
            case Some(parent) =>
              if (selectedParentLanguage.nonEmpty)
                selectedParentLanguage.exists(_.getId != parent.getId)
              else
                true
            case None =>
              selectedParentLanguage.nonEmpty
          }

          if (needUpdate) {
            if (selectedParentLanguage.nonEmpty) {
              backend.updateLanguage(CompositeId.fromObject(lang), selectedParentLanguage, Option.empty[CompositeId]) map { _ =>
                modalInstance.close(lang)
              } recover { case e: Throwable =>
                console.error(e.getMessage)
                modalInstance.dismiss(())
              }
            } else {
              console.error("Removing parent language is not supported at the moment!")
              modalInstance.dismiss(())
            }
          } else {
            modalInstance.dismiss(())
          }
        }

      // Create a new language
      case None =>
        if (!scope.names.forall(_.str.isEmpty)) {
          backend.createLanguage(scope.names.filterNot(_.str.isEmpty), parentLanguage) onComplete {
            case Success(langId) =>
              backend.getLanguage(langId) map { language => modalInstance.close(language) }
            case Failure(e) =>
              console.error(e.getMessage)
              modalInstance.dismiss(())
          }
        } else {
          modalInstance.dismiss(())
        }
    }
  }

  @JSExport
  def cancel(): Unit = {
    modalInstance.dismiss(())
  }


  doAjax(() => {
    backend.getLocales() flatMap { locales =>
      scope.locales = locales.toJSArray

      backend.getLanguages map { languageTree =>
        scope.languages = Utils.flattenLanguages(languageTree).toJSArray

        language foreach { lang =>
          scope.languages = scope.languages.filterNot(_.getId == lang.getId)
        }

        computeIndentation(languageTree)

        // fetch already existing translations
        language foreach { editLanguage =>
          backend.translationGist(CompositeId(editLanguage.translationGistClientId, editLanguage.translationGistObjectId)) foreach { gist =>
            scope.names = gist.atoms.map(atom => LocalizedString(atom.localeId, atom.content))
            readOnlyTranslations = scope.names.map(_.localeId).toSet
          }
        }

      } recover { case e: Throwable =>

      }
    } recover { case e: Throwable =>

    }
  })

  override protected def onLoaded[T](result: T): Unit = {}

  override protected def onError(reason: Throwable): Unit = {}

  override protected def preRequestHook(): Unit = {
    scope.progressBar = true
  }

  override protected def postRequestHook(): Unit = {
    scope.progressBar = false
  }
}
