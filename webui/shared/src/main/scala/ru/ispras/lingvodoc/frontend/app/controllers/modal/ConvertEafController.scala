package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{ErrorModalHandler, LoadingPlaceholder}
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait ConvertEafScope extends Scope {
  var locales: js.Array[Locale] = js.native
  var mode: String = js.native
  var languages: js.Array[Language] = js.native
  var language: Option[Language] = js.native
  var languageId: String = js.native
  var names: js.Array[LocalizedString] = js.native
  var fileId: String = js.native
  var updateDictionaryName: String = js.native
  var updateDictionaries: js.Array[Dictionary] = js.native
  var validated: Boolean = js.native
  var errorMessage: String = js.native
  var complete: Boolean = js.native
  var progressBar: Boolean = js.native
}

@injectable("ConvertEafController")
class ConvertEafController(scope: ConvertEafScope,
                           val modalService: ModalService,
                           instance: ModalInstance[Unit],
                           backend: BackendService,
                           timeout: Timeout,
                           val exceptionHandler: ExceptionHandler,
                           params: js.Dictionary[js.Function0[js.Any]])
  extends BaseModalController(scope, modalService, instance, timeout, params)
    with AngularExecutionContextProvider {

  private[this] var indentation = Map[String, Int]()
  private[this] val corpusId = params("corpusId").asInstanceOf[CompositeId]
  private[this] val markupUrl = params("markupUrl").asInstanceOf[Option[String]]
  private[this] val soundUrl = params("soundUrl").asInstanceOf[Option[String]]
  private[this] var allDictionaries: Seq[Dictionary] = Seq[Dictionary]()
  private[this] var selectedUpdateDictionary: Option[Dictionary] = Option.empty[Dictionary]

  scope.locales = js.Array[Locale]()
  scope.mode = "create"
  scope.languages = js.Array[Language]()
  scope.language = None
  scope.languageId = ""
  scope.names = js.Array[LocalizedString](LocalizedString(Utils.getLocale().getOrElse(2), ""))
  scope.updateDictionaryName = ""
  scope.updateDictionaries = js.Array[Dictionary]()
  scope.validated = false
  scope.errorMessage = ""
  scope.complete = false
  scope.progressBar = true


  @JSExport
  def newLanguage(): Unit = {

    val parentLanguage = scope.languages.find(_.getId == scope.languageId)

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/createLanguage.html"
    options.controller = "CreateLanguageController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          "parentLanguage" -> parentLanguage.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modalService.open[Language](options)

    instance.result foreach { _ =>
      backend.getLanguages onComplete {
        case Success(tree: Seq[Language]) =>
          indentation = indentations(tree)
          scope.languages = Utils.flattenLanguages(tree).toJSArray
        case Failure(e) =>
      }
    }
  }

  @JSExport
  def addNameTranslation(): Unit = {
    val currentLocaleId = Utils.getLocale().getOrElse(2)
    if (scope.names.exists(_.localeId == currentLocaleId)) {
      // pick next available locale
      scope.locales.filterNot(locale => scope.names.exists(name => name.localeId == locale.id)).headOption.foreach { firstLocale =>
        scope.names = scope.names :+ LocalizedString(firstLocale.id, "")
      }
    } else {
      // add translation with current locale pre-selected
      scope.names = scope.names :+ LocalizedString(currentLocaleId, "")
    }
  }

  @JSExport
  def getDisplayName(): String = {
    val localeId = Utils.getLocale().getOrElse(2)
    scope.names.find(name => name.localeId == localeId) match {
      case Some(name) => name.str
      case None => ""
    }
  }

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
  def languagePadding(language: Language): String = {
    "&nbsp;&nbsp;&nbsp;" * indentation.getOrElse(language.getId, 0)
  }


  @JSExport
  def convert(): Unit = {
    load(() => {
      scope.errorMessage = ""

      scope.mode match {
        case "create" =>
          scope.languages.find(_.getId == scope.languageId) match {
            case Some(language) =>
              // make sure there is at least one non-empty name
              if (scope.names.exists(_.str.nonEmpty)) {
                // create dictionary name
                createDictionaryName() map { gistId =>
                  // create dictionary
                  backend.createDictionary(CompositeId.fromObject(language), gistId) map { dictionaryId =>
                    // start conversion process
                    backend.convertEafCorpus(corpusId, dictionaryId, soundUrl, markupUrl) map { _ =>

                      scope.complete = true

                      // close modal
                      import scala.scalajs.js.timers._
                      setTimeout(5000) {
                        instance.dismiss(())
                      }

                    } recover { case e => error(e) }
                  } recover { case e => error(e) }
                } recover { case e => error(e) }
              } else {
                scope.errorMessage = "Please enter at least one name!"
                Future.successful(())
              }
            case None => scope.errorMessage = "Please select parent language!"
              Future.successful(())
          }
        case "update" =>
          backend.convertEafCorpus(corpusId, CompositeId.fromObject(selectedUpdateDictionary.get), soundUrl, markupUrl) map { _ =>
            scope.complete = true

            // close modal
            import scala.scalajs.js.timers._
            setTimeout(5000) {
              instance.dismiss(())
            }
          }
      }
    })
    ()
  }

  @JSExport
  def cancel(): Unit = {
    instance.dismiss(())
  }

  @JSExport
  def onUpdateDictionaryName(): Unit = {
    scope.updateDictionaries = allDictionaries.filter(_.translation.toLowerCase.contains(scope.updateDictionaryName.toLowerCase)).take(10).toJSArray
  }


  @JSExport
  def toggleUpdateDictionary(updateDictionary: Dictionary): Unit = {
    selectedUpdateDictionary = selectedUpdateDictionary match {
      case Some(dictionary) =>
        if (dictionary.getId == updateDictionary.getId) {
          None
        } else {
          Some(updateDictionary)
        }
      case None => Some(updateDictionary)
    }
  }

  @JSExport
  def isUpdateDictionarySelected(updateDictionary: Dictionary): Boolean = {
    selectedUpdateDictionary.exists(_.getId == updateDictionary.getId)
  }

  @JSExport
  def isConvertDisabled(): Boolean = {
    scope.mode match {
      case "create" =>
        scope.languageId.isEmpty || scope.names.forall(_.str.isEmpty)
      case "update" =>
        selectedUpdateDictionary.isEmpty
    }
  }

  private[this] def createDictionaryName() = {
    backend.createTranslationGist("Dictionary") flatMap { gist =>
      val atomRequests = scope.names.toSeq.map { name =>
        backend.createTranslationAtom(gist, name)
      }
      Future.sequence(atomRequests) map { _ =>
        gist
      } recoverWith {
        case e => Future.failed(e)
      }
    }
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
    val languages = Utils.flattenLanguages(tree).toJSArray
    languages.map { language =>
      language.getId -> getDepth(language, tree).get
    }.toMap
  }

  load(() => {

    backend.getCurrentUser map { user =>
      val query = DictionaryQuery()
      query.author = Some(user.id)
      backend.getDictionaries(query) map { dictionaries =>
        allDictionaries = dictionaries
      }
    }

    backend.getLanguages flatMap { tree =>
      indentation = indentations(tree)
      scope.languages = Utils.flattenLanguages(tree).toJSArray
      // load list of locales
      backend.getLocales map { locales =>
        // generate localized names
        scope.locales = locales.toJSArray
        backend.validateEafCorpus(markupUrl.get).map { result =>
          scope.validated = result
          scope.complete = false
        } recover { case e =>
          scope.validated = false
        }
      } recover { case e => error(e) }
    }
  })

  override protected def onStartRequest(): Unit = {
    scope.progressBar = true
  }

  override protected def onCompleteRequest(): Unit = {
    scope.progressBar = false
  }
}
