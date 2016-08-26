package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{AnchorScroll, Location, Scope}
import com.greencatsoft.angularjs.{AbstractController, injectable}
import ru.ispras.lingvodoc.frontend.app.model.{Dictionary, Language, Locale, LocalizedString}
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalOptions, ModalService}
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

import scala.concurrent.{Future, Promise}
import scala.scalajs.js.JSConverters._
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.controllers.common.{FieldType, Layer, Translatable}
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.scalajs.js
import scala.scalajs.js.annotation.{JSExport, JSExportAll}
import scala.util.{Failure, Success}



@js.native
trait CreateDictionaryScope extends Scope {
  var locales: js.Array[Locale] = js.native
  var languages: js.Array[Language] = js.native
  var language: Option[Language] = js.native
  var languageId: String = js.native
  var creationMode: String = js.native
  var names: js.Array[LocalizedString] = js.native
  var layers: js.Array[Layer] = js.native
  var step: Int = js.native
}


@injectable("CreateDictionaryController")
class CreateDictionaryController(scope: CreateDictionaryScope, modal: ModalService, backend: BackendService) extends AbstractController[CreateDictionaryScope](scope) {

  // Scope initialization
  scope.locales = js.Array[Locale]()
  scope.languages = js.Array[Language]()
  scope.names = js.Array[LocalizedString]()
  scope.language = None
  scope.languageId = ""
  scope.creationMode = "create"
  scope.layers = js.Array[Layer]()
  scope.step = 2



  // load data from backend
  load()


  @JSExport
  def getCurrentLocale() = {
    val localeId = Utils.getLocale().getOrElse(2)
    scope.locales.find(l => l.id == localeId)
  }

  @JSExport
  def getLocaleName(localeId: Int): String = {
    scope.locales.find(l => l.id == localeId) match {
      case Some(locale) => locale.name
      case None => "Unknown locale"
    }
  }

  /**
    * Returns TRUE is all names are empty and no language is selected
    *
    * @return
    */
  @JSExport
  def step1NextDisabled(): Boolean = {
    scope.languageId.isEmpty || scope.names.forall(name => {
      name.str.isEmpty
    })
  }


  @JSExport
  def newLanguage() = {


  }

  @JSExport
  def createDictionary2() = {


    scope.languages.find(language => language.getId == scope.languageId) match {
      case Some(language) =>
        scope.step = 2
      case None =>
      // TODO: Add user friendly error message
    }
  }

  @JSExport
  def addLayer() = {
    val layer = Layer(js.Array[LocalizedString](LocalizedString(Utils.getLocale().getOrElse(2), "")), js.Array[FieldType]())
    scope.layers = scope.layers :+ layer
  }

  @JSExport
  def addFieldType(layer: Layer) = {
    layer.fieldTypes = layer.fieldTypes :+ FieldType(js.Array[LocalizedString](LocalizedString(Utils.getLocale().getOrElse(2), "")))
  }

  @JSExport
  def removeFieldType(layer: Layer, fieldType: FieldType) = {
    layer.fieldTypes = layer.fieldTypes.filterNot(d => d.equals(fieldType))
  }

  @JSExport
  def addNameTranslation[T <: Translatable](obj: T) = {
    val currentLocaleId = Utils.getLocale().getOrElse(2)
    if (obj.names.exists(_.localeId == currentLocaleId)) {
      // pick next available locale
      scope.locales.filterNot(locale => obj.names.exists(name => name.localeId == locale.id)).toList match {
        case firstLocale::otherLocales =>
          obj.names = obj.names :+ LocalizedString(firstLocale.id, "")
        case Nil =>
      }
    } else {
      // add translation with current locale pre-selected
      obj.names = obj.names :+ LocalizedString(currentLocaleId, "")
    }
  }


  @JSExport
  def moveFieldTypeUp(layer: Layer, fieldType: FieldType) = {
    def aux(lx: List[FieldType], acc: List[FieldType]): List[FieldType] = {
      lx match {
        case Nil => acc
        case a :: b :: xs if b.equals(fieldType) => aux(xs, a :: b :: acc)
        case x :: xs => aux(xs, x :: acc)
      }
    }
    layer.fieldTypes = aux(layer.fieldTypes.toList, Nil).reverse.toJSArray
  }

  @JSExport
  def moveFieldTypeDown(layer: Layer, fieldType: FieldType) = {
    def aux(lx: List[FieldType], acc: List[FieldType]): List[FieldType] = {
      lx match {
        case Nil => acc
        case a :: b :: xs if a.equals(fieldType) => aux(xs, a :: b :: acc)
        case x :: xs => aux(xs, x :: acc)
      }
    }
    layer.fieldTypes = aux(layer.fieldTypes.toList, Nil).reverse.toJSArray
  }


  @JSExport
  def getLayerDisplayName(layer: Layer) = {
    val localeId = Utils.getLocale().getOrElse(2)
    layer.names.find(name => name.localeId == localeId) match {
      case Some(name) => name.str
      case None => ""
    }
  }

  @JSExport
  def getAvailableLocales(translations: js.Array[LocalizedString], currentTranslation: LocalizedString): js.Array[Locale] = {
    val currentLocale = scope.locales.find(_.id == currentTranslation.localeId).get
    val otherTranslations = translations.filterNot(translation => translation.equals(currentTranslation))
    val availableLocales = scope.locales.filterNot(_.equals(currentLocale)).filter(locale => !otherTranslations.exists(translation => translation.localeId == locale.id)).toList
    (currentLocale :: availableLocales).toJSArray
  }

  @JSExport
  def createNewFieldType() = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/createFieldType.html"
    options.controller = "CreateFieldTypeController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(locales = scope.locales.asInstanceOf[js.Object])
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[FieldType](options)

    instance.result map {
      case field: FieldType => console.log((field :: Nil).toJSArray)
    }
  }




  /**
    * Converts language tree to flat list of languages
    *
    * @param languagesTree
    * @return
    */
  private[this] def flatLanguages(languagesTree: js.Array[Language]): Seq[Language] = {

    val flatSubLanguages = new ((Language) => Seq[Language]) {
      override def apply(language: Language): Seq[Language] = {
        var languages = Seq[Language]()
        for (childLanguage <- language.languages) {
          val ch = apply(childLanguage)
          languages = languages ++ ch
        }
        languages = languages :+ language
        languages
      }
    }
    var languages = Seq[Language]()
    for (language <- languagesTree) {
      languages = languages ++ flatSubLanguages(language)
    }

    languages
  }


  /**
    * Loads data from backend
    */
  def load(): Unit = {

    // load list of locales
    backend.getLocales onComplete {
      case Success(locales) =>
        // generate localized names
        scope.locales = locales.toJSArray
        scope.names = locales.map(locale => LocalizedString(locale.id, "")).toJSArray

      case Failure(e) =>
    }

    // get list of languages
    backend.getLanguages onComplete {
      case Success(tree: Seq[Language]) =>
        // translate every language in list
        Future.sequence(flatLanguages(tree.toJSArray).map(language => {
          backend.translateLanguage(language, Utils.getLocale().getOrElse(2))
        })) onComplete {
          case Success(translatedLanguages) =>
            scope.languages = translatedLanguages.toJSArray
          case Failure(e) =>
        }
      case Failure(e) =>
    }
  }
}
