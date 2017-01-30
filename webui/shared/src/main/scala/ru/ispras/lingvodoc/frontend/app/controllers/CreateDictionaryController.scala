package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{ExceptionHandler, Location, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.controllers.common.{FieldEntry, Layer, Translatable}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.LanguageEdit
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, UserService}
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.{Future, Promise}
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.scalajs.js.{Dynamic, Object, UndefOr}
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
  var updateDictionaryName: String = js.native
  var updateDictionaries: js.Array[Dictionary] = js.native
  var step: Int = js.native
}

@injectable("CreateDictionaryController")
class CreateDictionaryController(scope: CreateDictionaryScope,
                                 modal: ModalService,
                                 location: Location,
                                 backend: BackendService,
                                 userService: UserService,
                                 val timeout: Timeout,
                                 val exceptionHandler: ExceptionHandler)
  extends AbstractController[CreateDictionaryScope](scope)
    with AngularExecutionContextProvider
    with LanguageEdit {

  private[this] var allDictionaries: Seq[Dictionary] = Seq[Dictionary]()
  private[this] var selectedUpdateDictionary: Option[Dictionary] = Option.empty[Dictionary]


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
  scope.updateDictionaryName = ""
  scope.updateDictionaries = js.Array[Dictionary]()
  scope.step = 1


  // load data from backend
  load()

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

    if (scope.creationMode == "update") {
      selectedUpdateDictionary.isEmpty
    } else {
      scope.languageId.isEmpty || scope.names.forall(name => {
        name.str.isEmpty
      })
    }
  }

  @JSExport
  def step2NextDisabled(): Boolean = {
    scope.layers.isEmpty
  }


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

    val instance = modal.open[Language](options)

    instance.result foreach { _ =>
      backend.getLanguages onComplete {
        case Success(tree: Seq[Language]) =>
          computeIndentation(tree)
          scope.languages = Utils.flattenLanguages(tree).toJSArray
        case Failure(_) =>
      }
    }
  }





  @JSExport
  def createDictionary2(): Any = {


    scope.creationMode match {
      case "create" =>
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

      case "import" =>
        scope.languages.find(language => language.getId == scope.languageId) foreach { language =>
          backend.createTranslationGist("Dictionary") map { gistId =>
            Future.sequence(scope.names.filter(_.str.nonEmpty).toSeq.map(name => backend.createTranslationAtom(gistId, name))) map { _ =>
              scope.files.find(_.getId == scope.fileId) foreach { file =>
                backend.convertDialeqtDictionary(CompositeId.fromObject(language), CompositeId.fromObject(file), gistId) map { _ =>
                  scope.step = 3
                  redirectToDashboard()
                }
              }
            }
          }
        }

      case "update" =>
        scope.files.find(_.getId == scope.fileId) foreach { file =>
          selectedUpdateDictionary.foreach { dictionary =>
            backend.convertDialeqtDictionary(CompositeId.fromObject(file), CompositeId.fromObject(dictionary)) map { _ =>
              scope.step = 3
              redirectToDashboard()
            }
          }
        }
    }
  }

  @JSExport
  def addLayer(): Unit = {
    val layer = Layer(js.Array[LocalizedString](LocalizedString(Utils.getLocale().getOrElse(2), "")), js.Array[FieldEntry]())
    scope.layers = scope.layers :+ layer
  }

  @JSExport
  def addFieldType(layer: Layer): Unit = {
    layer.fieldEntries = layer.fieldEntries :+ FieldEntry(js.Array[LocalizedString](LocalizedString(Utils.getLocale().getOrElse(2), "")))
  }

  @JSExport
  def removeFieldType(layer: Layer, fieldType: FieldEntry): Unit = {
    layer.fieldEntries = layer.fieldEntries.filterNot(d => d.equals(fieldType))
  }

  @JSExport
  def addNameTranslation[T <: Translatable](obj: T): Unit = {
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
  def selectField(fieldEntry: FieldEntry): Unit = {
    if (fieldEntry.fieldId.equals("add_new_field")) {
      fieldEntry.fieldId = ""
      createNewField(fieldEntry)
    }
  }

  @JSExport
  def moveFieldTypeUp(layer: Layer, fieldType: FieldEntry): Unit = {
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
  def moveFieldTypeDown(layer: Layer, fieldType: FieldEntry): Unit = {
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
  def getLayerDisplayName(layer: Layer): String = {
    val localeId = Utils.getLocale().getOrElse(2)
    layer.names.find(name => name.localeId == localeId) match {
      case Some(name) => name.str
      case None => ""
    }
  }

  @JSExport
  def getLinkedLayerDisplayName(layer: Layer): String = {
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
  def finish(): Unit = {
    compilePerspective(scope.layers) foreach { _ =>
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

  @JSExport
  def createNewField(fieldEntry: FieldEntry): Unit = {

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
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[FieldEntry](options)

    instance.result foreach {
      f => createField(f) foreach {
        nf => fieldEntry.fieldId = nf.getId
      }
    }
  }

  @JSExport
  def availableLayers(layer: Layer): js.Array[Layer] = {
    scope.layers.filterNot(_.equals(layer)).toJSArray
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


  scope.$watch("fileId", (selectedFileId: UndefOr[String], _: js.Any) => {
    selectedFileId.toOption foreach { id =>
      scope.files.find(_.getId == id) foreach { file =>
        backend.getDialeqtDictionaryName(CompositeId.fromObject(file)) map { dictionaryName =>
          console.log(dictionaryName)
          scope.names.find(_.localeId == 1) foreach { name =>
            name.str = dictionaryName
          }
        }
      }
    }
  })


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
                    if (scope.layers.exists(l => l.internalId == entry.linkedLayerId)) {
                      Some(js.Dynamic.literal("client_id" -> field.clientId, "object_id" -> field.objectId, "contains" -> contains, "link" -> js.Dynamic.literal("fake_id" -> entry.linkedLayerId)))
                    } else {
                      None
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

  private[this] def redirectToDashboard(): Unit = {
    import scala.scalajs.js.timers._
    setTimeout(5000) {
      location.path("/dashboard")
      scope.$apply()
    }
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
      case Failure(_) =>
    }

    // load list of locales
    backend.getLocales onComplete {
      case Success(locales) =>
        // generate localized names
        scope.locales = locales.toJSArray
        scope.names = locales.map(locale => LocalizedString(locale.id, "")).toJSArray

      case Failure(_) =>
    }

    backend.getLanguages onComplete {
      case Success(tree: Seq[Language]) =>
        computeIndentation(tree)
        scope.languages = Utils.flattenLanguages(tree).toJSArray
      case Failure(_) =>
    }

    backend.userFiles map { files =>
      scope.files = files.filter(_.dataType == "dialeqt_dictionary").toJSArray
    }


    backend.getCurrentUser map { user =>
      val query = DictionaryQuery()
      query.author = Some(user.id)
      backend.getDictionaries(query) map { dictionaries =>
        allDictionaries = dictionaries
      }
    }
  }
}
