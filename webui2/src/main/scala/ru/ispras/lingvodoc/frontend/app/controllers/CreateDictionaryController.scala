package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.api.exceptions.BackendException
import ru.ispras.lingvodoc.frontend.app.controllers.common.{FieldEntry, Layer, Translatable}
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalOptions, ModalService}
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.{Future, Promise}
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.scalajs.js.{Dynamic, Object}
import scala.util.{Failure, Success}


@js.native
trait CreateDictionaryScope extends Scope {
  var locales: js.Array[Locale] = js.native
  var languages: js.Array[Language] = js.native
  var language: Option[Language] = js.native
  var languageId: String = js.native
  var files: js.Array[File] = js.native
  var fileId: String = js.native
  var creationMode: String = js.native
  var names: js.Array[LocalizedString] = js.native
  var layers: js.Array[Layer] = js.native
  var fields: js.Array[Field] = js.native
  var dataTypes: js.Array[TranslationGist] = js.native
  var dictionaryId: Option[CompositeId] = js.native
  var step: Int = js.native
}

@injectable("CreateDictionaryController")
class CreateDictionaryController(scope: CreateDictionaryScope, modal: ModalService, backend: BackendService, val timeout: Timeout) extends AbstractController[CreateDictionaryScope](scope) with AngularExecutionContextProvider {

  // Scope initialization
  scope.locales = js.Array[Locale]()
  scope.languages = js.Array[Language]()
  scope.names = js.Array[LocalizedString]()
  scope.language = None
  scope.languageId = ""
  scope.files = js.Array[File]()
  scope.fileId = ""
  scope.creationMode = "create"
  scope.layers = js.Array[Layer]()
  scope.fields = js.Array[Field]()
  scope.dataTypes = js.Array[TranslationGist]()
  scope.dictionaryId = None

  scope.step = 1


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
    * Returns TRUE if all names are empty and no language is selected
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
  def step2NextDisabled(): Boolean = {
    scope.layers.isEmpty
  }


  @JSExport
  def newLanguage() = {

  }

  @JSExport
  def createDictionary2() = {

    if (scope.creationMode == "create") {


      scope.languages.find(language => language.getId == scope.languageId) match {
        case Some(language) =>

          backend.createDictionary(scope.names, language) map {
            dictionaryId =>
              scope.dictionaryId = Some(dictionaryId)
              scope.step = 2
          }

        case None =>
        // TODO: Add user friendly error message
      }
    } else {

      scope.languages.find(language => language.getId == scope.languageId) match {
        case Some(language) =>

          scope.files.find(_.getId == scope.fileId) match {
            case Some(file) => backend.convertDictionary(CompositeId.fromObject(language), CompositeId.fromObject(file)) map {
              dictionaryId =>
                scope.dictionaryId = Some(dictionaryId)
                scope.step = 2
            }
            case None =>
            // TODO: Add user friendly error message
          }

        case None =>
        // TODO: Add user friendly error message
      }
    }
  }

  @JSExport
  def addLayer() = {
    val layer = Layer(js.Array[LocalizedString](LocalizedString(Utils.getLocale().getOrElse(2), "")), js.Array[FieldEntry]())
    scope.layers = scope.layers :+ layer
  }

  @JSExport
  def addFieldType(layer: Layer) = {
    layer.fieldEntries = layer.fieldEntries :+ FieldEntry(js.Array[LocalizedString](LocalizedString(Utils.getLocale().getOrElse(2), "")))
  }

  @JSExport
  def removeFieldType(layer: Layer, fieldType: FieldEntry) = {
    layer.fieldEntries = layer.fieldEntries.filterNot(d => d.equals(fieldType))
  }

  @JSExport
  def addNameTranslation[T <: Translatable](obj: T) = {
    val currentLocaleId = Utils.getLocale().getOrElse(2)
    if (obj.names.exists(_.localeId == currentLocaleId)) {
      // pick next available locale
      scope.locales.filterNot(locale => obj.names.exists(name => name.localeId == locale.id)).toList match {
        case firstLocale :: otherLocales =>
          obj.names = obj.names :+ LocalizedString(firstLocale.id, "")
        case Nil =>
      }
    } else {
      // add translation with current locale pre-selected
      obj.names = obj.names :+ LocalizedString(currentLocaleId, "")
    }
  }

  @JSExport
  def selectField(fieldEntry: FieldEntry) = {
    if (fieldEntry.fieldId.equals("add_new_field")) {
      fieldEntry.fieldId = ""
      createNewField(fieldEntry)
    }
  }

  @JSExport
  def moveFieldTypeUp(layer: Layer, fieldType: FieldEntry) = {
    def aux(lx: List[FieldEntry], acc: List[FieldEntry]): List[FieldEntry] = {
      lx match {
        case Nil => acc
        case a :: b :: xs if b.equals(fieldType) => aux(xs, a :: b :: acc)
        case x :: xs => aux(xs, x :: acc)
      }
    }
    layer.fieldEntries = aux(layer.fieldEntries.toList, Nil).reverse.toJSArray
  }

  @JSExport
  def moveFieldTypeDown(layer: Layer, fieldType: FieldEntry) = {
    def aux(lx: List[FieldEntry], acc: List[FieldEntry]): List[FieldEntry] = {
      lx match {
        case Nil => acc
        case a :: b :: xs if a.equals(fieldType) => aux(xs, a :: b :: acc)
        case x :: xs => aux(xs, x :: acc)
      }
    }
    layer.fieldEntries = aux(layer.fieldEntries.toList, Nil).reverse.toJSArray
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
  def getLinkedLayerDisplayName(layer: Layer) = {
    val localeId = Utils.getLocale().getOrElse(2)

    val indexBasedName = scope.layers.zipWithIndex.find(x => layer.equals(x._1)) match {
      case Some(x) => "#" + (x._2 + 1).toString
      case None => ""
    }

    layer.names.find(name => name.localeId == localeId) match {
      case Some(name) => if (name.str.trim.nonEmpty) {
        name.str
      } else {
        indexBasedName
      }
      case None => indexBasedName
    }
  }

  @JSExport
  def linkedLayersEnabled(): Boolean = {
    scope.layers.size > 1
  }

  @JSExport
  def linkFieldSelected(fieldEntry: FieldEntry): Boolean = {
    scope.fields.find(field => field.getId == fieldEntry.fieldId) match {
      case Some(field) =>
        scope.dataTypes.find(dataType => dataType.clientId == field.dataTypeTranslationGistClientId && dataType.objectId == field.dataTypeTranslationGistObjectId) match {
          case Some(dataType) => dataType.atoms.exists(atom => atom.content.equals("Link") && atom.localeId == 2)
          case None => false
        }
      case None => false
    }
  }

  @JSExport
  def finish() = {
    compilePerspective(scope.layers) foreach { _ =>
      scope.step = 3
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
  def createNewField(fieldEntry: FieldEntry) = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/createField.html"
    options.controller = "CreateFieldController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(entry = fieldEntry.asInstanceOf[js.Object],
          locales = scope.locales.asInstanceOf[js.Object],
          dataTypes = scope.dataTypes.asInstanceOf[js.Object])
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[FieldEntry](options)

    instance.result map {
      f => createField(f) map {
        nf => fieldEntry.fieldId = nf.getId
      }
    }
  }

  @JSExport
  def availableLayers(layer: Layer): js.Array[Layer] = {
    scope.layers.filterNot(_.equals(layer)).toJSArray
  }

  private[this] def fieldToJS(field: Field): Object with Dynamic = {
    js.Dynamic.literal("client_id" -> field.clientId, "object_id" -> field.objectId)
  }

  private[this] def createPerspectiveTranslationGist(layer: Layer): Future[CompositeId] = {
    val p = Promise[CompositeId]()
    backend.createTranslationGist("Perspective") onComplete {
      case Success(gistId) =>
        // create translation atoms
        // TODO: add some error checks
        val seqs = layer.names map {
          name => backend.createTranslationAtom(gistId, name)
        }
        // make sure all translations created successfully
        Future.sequence(seqs.toSeq) onComplete {
          case Success(_) =>
            p.success(gistId)
          case Failure(e) =>
            console.error(e.getMessage)
            p.failure(e)
        }
      case Failure(e) =>
        console.error(e.getMessage)
        p.failure(e)

    }
    p.future
  }

  private[this] def compilePerspective(layers: Seq[Layer]): Future[Seq[CompositeId]] = {

    val getField: (String) => Option[Field] = (fieldId: String) => {
      scope.fields.find(_.getId == fieldId)
    }

    //
    val con = layers.map { layer =>
      createPerspectiveTranslationGist(layer).map {
        gist =>
          val fields = layer.fieldEntries.flatMap {
            entry =>
              getField(entry.fieldId) match {
                case Some(field) =>

                  val contains = (getField(entry.subfieldId) match {
                    case Some(x) => (x :: Nil).toJSArray
                    case None => js.Array[Field]()
                  }).map(c => fieldToJS(c))

                  val isLink = scope.dataTypes.find(dataType => dataType.clientId == field.dataTypeTranslationGistClientId && dataType.objectId == field.dataTypeTranslationGistObjectId) match {
                    case Some(dataType) => dataType.atoms.exists(atom => atom.content.equals("Link") && atom.localeId == 2)
                    case None => false
                  }
                  if (!isLink) {
                    Some(js.Dynamic.literal("client_id" -> field.clientId, "object_id" -> field.objectId, "contains" -> contains))
                  } else {
                    scope.layers.exists(l => l.internalId == entry.linkedLayerId) match {
                      case true => Some(js.Dynamic.literal("client_id" -> field.clientId, "object_id" -> field.objectId, "contains" -> contains, "link" -> js.Dynamic.literal("fake_id" -> entry.linkedLayerId)))
                      case false => None
                    }
                  }
                case None => None
              }
          }
          js.Dynamic.literal("fake_id" -> layer.internalId,
            "translation_gist_client_id" -> gist.clientId,
            "translation_gist_object_id" -> gist.objectId,
            "fields" -> fields)
      }
    }

    Future.sequence(con) flatMap { backend.createPerspectives(scope.dictionaryId.get, _) }
  }

  private[this] def createField(fieldType: FieldEntry): Future[Field] = {
    val p = Promise[Field]()
    // create gist
    backend.createTranslationGist("Field") onComplete {
      case Success(gistId) =>
        // create translation atoms
        // TODO: add some error checks
        val seqs = fieldType.names map {
          name => backend.createTranslationAtom(gistId, name)
        }

        // make sure all translations created successfully
        Future.sequence(seqs.toSeq) onComplete {
          case Success(_) =>
            // and finally create field
            backend.createField(gistId, CompositeId.fromObject(fieldType.dataType.get)) map {
              fieldId =>
                // get field data
                backend.getField(fieldId) map {
                  field =>
                    // add field to list of all available fields
                    scope.fields = scope.fields :+ field
                    p.success(field)
                }
            }
          case Failure(e) =>
            console.error(e.getMessage)
            p.failure(e)
        }
      case Failure(e) =>
        console.error(e.getMessage)
        p.failure(e)
    }
    p.future
  }

  /**
    * Loads data from backend
    */
  def load(): Unit = {

    backend.dataTypes() map {
      dataTypes => scope.dataTypes = dataTypes.toJSArray
    }

    // load list of fields
    backend.fields() onComplete {
      case Success(fields) =>
        scope.fields = fields.toJSArray
      case Failure(e) =>
    }

    // load list of locales
    backend.getLocales onComplete {
      case Success(locales) =>
        // generate localized names
        scope.locales = locales.toJSArray
        scope.names = locales.map(locale => LocalizedString(locale.id, "")).toJSArray

      case Failure(e) =>
    }

    backend.getLanguages onComplete {
      case Success(tree: Seq[Language]) =>
        scope.languages = Utils.flattenLanguages(tree).toJSArray
      case Failure(e) =>
    }

    backend.userFiles onComplete {
      case Success(files) => scope.files = files.toJSArray
      case Failure(e) =>
    }

  }
}
