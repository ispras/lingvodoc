package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import ru.ispras.lingvodoc.frontend.app.services.{ModalInstance, ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.controllers.common.{FieldEntry, Layer, Translatable}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.LoadingPlaceholder
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService

import scala.concurrent.{Future, Promise}
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.scalajs.js
import scala.scalajs.js.{Dynamic, Object}
import scala.scalajs.js.annotation.JSExport
import scala.scalajs.js.JSConverters._
import scala.util.{Failure, Success}

@js.native
trait PerspectivePropertiesScope extends Scope {
  var dictionary: Dictionary = js.native
  var perspective: Perspective = js.native
  var locales: js.Array[Locale] = js.native
  var layers: js.Array[Layer] = js.native
  var fields: js.Array[Field] = js.native
  var pageLoaded: Boolean = js.native

}


@injectable("PerspectivePropertiesController")
class PerspectivePropertiesController(scope: PerspectivePropertiesScope,
                                      instance: ModalInstance[Perspective],
                                      modal: ModalService,
                                      backend: BackendService,
                                      val timeout: Timeout,
                                      val exceptionHandler: ExceptionHandler,
                                      params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[PerspectivePropertiesScope](scope)
    with AngularExecutionContextProvider
    with LoadingPlaceholder {

  private[this] val dictionary = params("dictionary").asInstanceOf[Dictionary]
  private[this] val perspective = params("perspective").asInstanceOf[Perspective]
  private[this] var perspectiveTranslationGist: Option[TranslationGist] = None
  private[this] var dataTypes = js.Array[TranslationGist]()
  private[this] var perspectives = Seq[Perspective]()
  private[this] var perspectiveTranslations = Map[Perspective, TranslationGist]()

  // Scope initialization
  scope.dictionary = dictionary.copy()
  scope.perspective = perspective.copy()
  scope.locales = js.Array[Locale]()
  scope.layers = js.Array[Layer]()
  scope.fields = js.Array[Field]()
  scope.pageLoaded = false


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
  def selectField(fieldEntry: FieldEntry): Any = {
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
    val currentLocale1 = scope.locales.find(_.id == currentTranslation.localeId)

    if (currentLocale1.isEmpty) {
      console.log("empty")
      console.log(currentTranslation.localeId)


    }

    val currentLocale = currentLocale1.get
    val otherTranslations = translations.filterNot(translation => translation.equals(currentTranslation))
    val availableLocales = scope.locales.filterNot(_.equals(currentLocale)).filter(locale => !otherTranslations.exists(translation => translation.localeId == locale.id)).toList
    (currentLocale :: availableLocales).toJSArray
  }

  @JSExport
  def createNewField(fieldEntry: FieldEntry): Future[Future[Unit]] = {

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
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[FieldEntry](options)

    instance.result map {
      f => createField(f) map {
        nf => fieldEntry.fieldId = nf.getId
      }
    }
  }

  @JSExport
  def availablePerspectives(layer: Layer): js.Array[Perspective] = {
    perspectives.filterNot(_.getId == perspective.getId).toJSArray
  }


  @JSExport
  def editLocation(): Future[Unit] = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/perspectiveMap.html"
    options.controller = "PerspectiveMapController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(perspective = perspective.asInstanceOf[js.Object])
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[FieldEntry](options)

    instance.result map { _ => }
  }


  @JSExport
  def ok(): Unit = {
    // update translations
    val layer = scope.layers.head
    perspectiveTranslationGist foreach {
      gist =>
        val modifiedTranslations = gist.atoms.filter(atom => layer.names.exists(ls => ls.localeId == atom.localeId && ls.str != atom.content)) map { atom =>
          layer.names.find(ls => ls.localeId == atom.localeId) foreach {
            translation =>
              atom.content = translation.str
          }
          atom
        }

        val addedTranslations = layer.names.filterNot(name => gist.atoms.exists(_.localeId == name.localeId))
        val updatedTranslations = modifiedTranslations.filter(_.content.nonEmpty)

        val addRequests = addedTranslations.map { str =>
          backend.createTranslationAtom(CompositeId.fromObject(gist), str)
        }.toSeq

        val updatedRequests = updatedTranslations.map { atom =>
          backend.updateTranslationAtom(atom)
        }
    }

    updatePerspective(layer)

    instance.close(scope.perspective)
  }

  @JSExport
  def cancel() = {
    instance.dismiss(())
  }



  private[this] def fieldToJS(field: Field): Object with Dynamic = {
    js.Dynamic.literal("client_id" -> field.clientId, "object_id" -> field.objectId)
  }


  private[this] def updatePerspective(layer: Layer) = {

    val getField: (String) => Option[Field] = (fieldId: String) => {
      scope.fields.find(_.getId == fieldId)
    }

    perspectiveTranslationGist foreach {
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

                  perspectives.find(_.getId == entry.linkedLayerId) match {
                    case Some(linkedPerspective) =>
                      Some(js.Dynamic.literal("client_id" -> field.clientId,
                      "object_id" -> field.objectId,
                      "contains" -> contains,
                      "link" -> js.Dynamic.literal("client_id" -> linkedPerspective.clientId,
                        "object_id" -> linkedPerspective.objectId)))
                    case None => None

                  }
                }
              case None => None
            }
        }
        backend.updateFields(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective), fields.toSeq)
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

  private[this] def parsePerspective(perspective: Perspective, fields: Seq[Field]): Future[Layer] = {
    val p = Promise[Layer]()
    backend.translationGist(perspective.translationGistClientId, perspective.translationGistObjectId) map { gist =>
      perspectiveTranslationGist = Some(gist)
      val layerNames = gist.atoms.map(atom => LocalizedString(atom.localeId, atom.content))
      parseFields(fields) map {
        entries => Layer(layerNames, entries.toJSArray)
      } map(layer => p.success(layer))
    }
    p.future
  }


  doAjax(() => {

    // load list of locales
    backend.getLocales map { locales =>
      // generate localized names
      scope.locales = locales.toJSArray
      // load data types
      backend.dataTypes() flatMap { d =>
        dataTypes = d.toJSArray

        backend.getDictionaryPerspectives(dictionary, onlyPublished = false) flatMap { ps =>
          perspectives = ps
          val reqs = ps.map { p =>
            backend.translationGist(p.translationGistClientId, p.translationGistObjectId) map {
              gist => perspectiveTranslations = perspectiveTranslations + (p -> gist)
            }
          }

          Future.sequence(reqs) flatMap { _ =>
            // load all known fields
            backend.fields() flatMap { f =>
              scope.fields = f.toJSArray

              // load list of fields
              backend.getFields(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective)) flatMap { fields =>
                parsePerspective(perspective, fields).map { layer =>
                  scope.layers.push(layer)
                }
              }
            }
          }
        }
      }
    }
  })

  override protected def onLoaded[T](result: T): Unit = {}

  override protected def onError(reason: Throwable): Unit = {}

  override protected def preRequestHook(): Unit = {
    scope.pageLoaded = false
  }

  override protected def postRequestHook(): Unit = {
    scope.pageLoaded = true
  }
}
