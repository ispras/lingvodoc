package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout, Location}
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.controllers.common.{FieldEntry, Layer, Translatable}
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.{Future, Promise}
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.scalajs.js.{Dynamic, Object}
import scala.util.{Failure, Success}

@js.native
trait CreateCorpusScope extends Scope {
  var locales: js.Array[Locale] = js.native
  var languages: js.Array[Language] = js.native
  var language: Option[Language] = js.native
  var languageId: String = js.native
  //var files: js.Array[File] = js.native
  var fileId: String = js.native
  var creationMode: String = js.native
  var names: js.Array[LocalizedString] = js.native
  var layers: js.Array[Layer] = js.native
  var fields: js.Array[Field] = js.native
  var dictionaryId: Option[CompositeId] = js.native
  var step: Int = js.native
}

@injectable("CreateCorpusController")
class CreateCorpusController(scope: CreateCorpusScope,
                             modal: ModalService,
                             location: Location,
                             backend: BackendService,
                             val timeout: Timeout,
                             val exceptionHandler: ExceptionHandler)
  extends AbstractController[CreateCorpusScope](scope)
    with AngularExecutionContextProvider {

  private[this] var dataTypes: js.Array[TranslationGist] = js.Array[TranslationGist]()
  private[this] var indentation = Map[String, Int]()


  // Scope initialization
  scope.locales = js.Array[Locale]()
  scope.languages = js.Array[Language]()
  scope.names = js.Array[LocalizedString]()
  scope.language = None
  scope.languageId = ""
  //scope.files = js.Array[File]()
  scope.fileId = ""
  scope.creationMode = "create"
  scope.layers = js.Array[Layer]()
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

    val instance = modal.open[Language](options)

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
  def languagePadding(language: Language) = {
    "&nbsp;&nbsp;&nbsp;" * indentation.getOrElse(language.getId, 0)
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
      redirectToDashboard()
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

  private[this] def redirectToDashboard(): Unit = {
    import scala.scalajs.js.timers._
    setTimeout(5000) {
      location.path("/corpora")
      scope.$apply()
    }
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
        indentation = indentations(tree)
        scope.languages = Utils.flattenLanguages(tree).toJSArray
      case Failure(e) =>
    }

//    backend.userFiles onComplete {
//      case Success(files) => scope.files = files.toJSArray
//      case Failure(e) =>
//    }

  }
}
