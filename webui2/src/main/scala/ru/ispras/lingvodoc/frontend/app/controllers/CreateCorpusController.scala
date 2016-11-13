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
import scala.scalajs.js.{Dynamic, Object, UndefOr}
import scala.util.{Failure, Success}


@js.native
trait CreateCorpusScope extends Scope {
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
  //var dataTypes: js.Array[TranslationGist] = js.native
  var dictionaryId: Option[CompositeId] = js.native
  var step: Int = js.native
}

@injectable("CreateCorpusController")
class CreateCorpusController(scope: CreateCorpusScope, modal: ModalService, backend: BackendService, val timeout: Timeout)
  extends AbstractController[CreateCorpusScope](scope)
    with AngularExecutionContextProvider {

  private[this] var dataTypes: js.Array[TranslationGist] = js.Array[TranslationGist]()

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
  //scope.fields = js.Array[Field]()
  //scope.dataTypes = js.Array[TranslationGist]()
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

          backend.createDictionary(scope.names, language, isCorpora = true) map {
            dictionaryId =>
              scope.dictionaryId = Some(dictionaryId)
              scope.step = 2
          }

        case None =>
        // TODO: Add user friendly error message
      }
    } else {
      // import sqlite dictionary
      scope.languages.find(language => language.getId == scope.languageId) foreach { language =>
        backend.createTranslationGist("Dictionary") map { gistId =>
          Future.sequence(scope.names.filter(_.str.nonEmpty).toSeq.map(name => backend.createTranslationAtom(gistId, name))) map { _ =>
            scope.files.find(_.getId == scope.fileId) foreach { file =>
              backend.convertDialeqtDictionary(CompositeId.fromObject(language), CompositeId.fromObject(file), gistId) map { _ =>
                scope.step = 3
              }
            }
          }
        }
      }
    }
  }

  @JSExport
  def addLayer() = {
    parseFields(scope.fields) foreach { f =>
      val layer = Layer(js.Array[LocalizedString](LocalizedString(Utils.getLocale().getOrElse(2), "")), f.toJSArray)
      scope.layers = scope.layers :+ layer
    }
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
  def getLayerDisplayName(layer: Layer) = {
    val localeId = Utils.getLocale().getOrElse(2)
    layer.names.find(name => name.localeId == localeId) match {
      case Some(name) => name.str
      case None => ""
    }
  }

//  @JSExport
//  def getLinkedLayerDisplayName(layer: Layer) = {
//    val localeId = Utils.getLocale().getOrElse(2)
//
//    val indexBasedName = scope.layers.zipWithIndex.find(x => layer.equals(x._1)) match {
//      case Some(x) => "#" + (x._2 + 1).toString
//      case None => ""
//    }
//
//    layer.names.find(name => name.localeId == localeId) match {
//      case Some(name) => if (name.str.trim.nonEmpty) {
//        name.str
//      } else {
//        indexBasedName
//      }
//      case None => indexBasedName
//    }
//  }

//  @JSExport
//  def linkedLayersEnabled(): Boolean = {
//    scope.layers.size > 1
//  }

//  @JSExport
//  def linkFieldSelected(fieldEntry: FieldEntry): Boolean = {
//    fields.find(field => field.getId == fieldEntry.fieldId) match {
//      case Some(field) =>
//        dataTypes.find(dataType => dataType.clientId == field.dataTypeTranslationGistClientId && dataType.objectId == field.dataTypeTranslationGistObjectId) match {
//          case Some(dataType) => dataType.atoms.exists(atom => atom.content.equals("Link") && atom.localeId == 2)
//          case None => false
//        }
//      case None => false
//    }
//  }

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

  private[this] def fieldToJS(field: Field): Object with Dynamic = {
    js.Dynamic.literal("client_id" -> field.clientId, "object_id" -> field.objectId)
  }


  private[this] def createPerspectives(): Future[Seq[CompositeId]] = {
    val getField: (String) => Option[Field] = (fieldId: String) => {
      scope.fields.find(_.getId == fieldId)
    }

    //
    val con = scope.layers.toSeq.map { layer =>
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

                  val isLink = dataTypes.find(dataType => dataType.clientId == field.dataTypeTranslationGistClientId && dataType.objectId == field.dataTypeTranslationGistObjectId) match {
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

  @JSExport
  def finish() = {
    createPerspectives() foreach { _ =>
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

  private[this] def parseField(field: Field): Future[FieldEntry] = {

    val p = Promise[FieldEntry]

    backend.translationGist(field.translationGistClientId, field.translationGistObjectId) onComplete {
      case Success(gist) =>
        val fieldNames = gist.atoms.map(atom => LocalizedString(atom.localeId, atom.content))
        val fieldEntry = FieldEntry(fieldNames)

        fieldEntry.fieldId = field.getId

        if (field.fields.nonEmpty) {
          fieldEntry.hasSubfield = true
          fieldEntry.subfieldId = field.fields.head.getId
        }

        field.link.foreach { link =>
          fieldEntry.linkedLayerId = CompositeId(link.clientId, link.objectId).getId
        }

        fieldEntry.dataType = dataTypes.find(d => d.clientId == field.dataTypeTranslationGistClientId && d.objectId == field.dataTypeTranslationGistObjectId)

        p.success(fieldEntry)

      case Failure(e) =>
    }

    p.future
  }

  private[this] def parseFields(fields: Seq[Field]): Future[Seq[FieldEntry]] = {
    val fieldEntries = fields.map(field => parseField(field))
    Future.sequence(fieldEntries)
  }

  /**
    * Loads data from backend
    */
  def load(): Unit = {

    backend.dataTypes() map { d =>
      dataTypes = d.toJSArray
    }

    backend.corporaFields() map { f =>
      scope.fields = f.toJSArray
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
