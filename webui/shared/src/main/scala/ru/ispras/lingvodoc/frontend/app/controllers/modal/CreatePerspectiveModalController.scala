package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalOptions, ModalService}
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
trait CreatePerspectiveScope extends Scope {
  var dictionary: Dictionary = js.native
  var locales: js.Array[Locale] = js.native
  var layers: js.Array[Layer] = js.native
  var fields: js.Array[Field] = js.native
}


@injectable("CreatePerspectiveModalController")
class CreatePerspectiveModalController(scope: CreatePerspectiveScope,
                                       instance: ModalInstance[Unit],
                                       modal: ModalService,
                                       backend: BackendService,
                                       val timeout: Timeout,
                                       val exceptionHandler: ExceptionHandler,
                                       params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[CreatePerspectiveScope](scope) with AngularExecutionContextProvider {

  private[this] val dictionary = params("dictionary").asInstanceOf[Dictionary]
  private[this] var dataTypes = js.Array[TranslationGist]()
  private[this] var perspectives = Seq[Perspective]()
  private[this] var perspectiveTranslations = Map[Perspective, TranslationGist]()

  // Scope initialization
  scope.dictionary = dictionary.copy()
  scope.locales = js.Array[Locale]()
  scope.layers = js.Array[Layer]()
  scope.fields = js.Array[Field]()

  // create empty layer
  scope.layers.push(Layer(js.Array[LocalizedString](LocalizedString(Utils.getLocale().getOrElse(2), "")), js.Array[FieldEntry]()))

  load()

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
  def getLinkedPerspectiveDisplayName(p: Perspective): String = {
    val localeId = Utils.getLocale().getOrElse(2)

    perspectiveTranslations.get(p) match {
      case Some(gist) =>
        gist.atoms.find(name => name.localeId == localeId) match {
          case Some(name) => if (name.content.trim.nonEmpty) {
            name.content
          } else {
            p.getId
          }
          case None => p.getId
        }
      case None => p.getId
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
        dataTypes.find(dataType => dataType.clientId == field.dataTypeTranslationGistClientId && dataType.objectId == field.dataTypeTranslationGistObjectId) match {
          case Some(dataType) => dataType.atoms.exists(atom => atom.content.equals("Link") && atom.localeId == 2)
          case None => false
        }
      case None => false
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
          dataTypes = dataTypes.asInstanceOf[js.Object])
      }
    ).asInstanceOf[js.Dictionary[Any]]

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

  @JSExport
  def ok() = {
    compilePerspective(scope.layers.head) map { f =>
      f map {
        _ => instance.close(())
      }
    }
  }

  @JSExport
  def cancel() = {
    instance.dismiss(())
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

  private[this] def compilePerspective(layer: Layer) = {

    val getField: (String) => Option[Field] = (fieldId: String) => {
      scope.fields.find(_.getId == fieldId)
    }

    //
    val req = createPerspectiveTranslationGist(layer).map {
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

    Future.sequence(req :: Nil).map {
      ff => console.log(ff.toJSArray)
        backend.createPerspectives(CompositeId.fromObject(dictionary), ff)
    }
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


  private[this] def load() = {

    // load data types
    backend.dataTypes() map {
      d =>
        dataTypes = d.toJSArray

        backend.getDictionaryPerspectives(dictionary, onlyPublished = false) onComplete {
          case Success(ps) =>
            perspectives = ps
            ps.foreach { p =>
              backend.translationGist(p.translationGistClientId, p.translationGistObjectId) map {
                gist => perspectiveTranslations = perspectiveTranslations + (p -> gist)
              }
            }
          case Failure(e) =>
        }

        // load all known fields
        backend.fields() onComplete {
          case Success(f) =>
            scope.fields = f.toJSArray
          case Failure(e) =>
        }
    }

    // load list of locales
    backend.getLocales onComplete {
      case Success(locales) =>
        // generate localized names
        scope.locales = locales.toJSArray
      case Failure(e) =>
    }
  }
}