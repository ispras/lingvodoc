package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Event, RouteParams, Scope}
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, LexicalEntriesType, ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom.console
import org.scalajs.dom.raw.HTMLInputElement
import ru.ispras.lingvodoc.frontend.app.controllers.common.{DictionaryTable, GroupValue, TextValue, Value}
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.scalajs.js.Array


@js.native
trait EditDictionaryScope extends Scope {

  var dictionaryClientId: Int = js.native
  var dictionaryObjectId: Int = js.native
  var perspectiveClientId: Int = js.native
  var perspectiveObjectId: Int = js.native



  var count: Int = js.native
  var offset: Int = js.native
  var size: Int = js.native
  var dictionaryTable: DictionaryTable = js.native

  var filter: String = js.native

  var enabledInputs: js.Array[Any] = js.native

}

@JSExport
@injectable("EditDictionaryController")
class EditDictionaryController(scope: EditDictionaryScope, params: RouteParams, modal: ModalService, backend: BackendService) extends
AbstractController[EditDictionaryScope](scope) {

  scope.dictionaryClientId = params.get("dictionaryClientId").get.toString.toInt
  scope.dictionaryObjectId = params.get("dictionaryObjectId").get.toString.toInt
  scope.perspectiveClientId = params.get("perspectiveClientId").get.toString.toInt
  scope.perspectiveObjectId = params.get("perspectiveObjectId").get.toString.toInt

  scope.count = 0
  scope.offset = 0
  scope.size = 20

  private[this] val dictionary = Dictionary.emptyDictionary(scope.dictionaryClientId, scope.dictionaryObjectId)
  private[this] val perspective = Perspective.emptyPerspective(scope.perspectiveClientId, scope.perspectiveObjectId)

  private[this] var enabledInputs: Seq[(String, String)] = Seq[(String, String)]()

  load()

  @JSExport
  def play(soundAddress: String, soundMarkupAddress: String) = {
    console.log(s"playing $soundAddress with markup $soundMarkupAddress")
  }

  @JSExport
  def viewSoundMarkup(soundAddress: String, soundMarkupAddress: String) = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/soundMarkup.html"
    options.controller = "SoundMarkupController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          soundAddress = soundAddress.asInstanceOf[js.Object],
          dictionaryClientId = scope.dictionaryClientId.asInstanceOf[js.Object],
          dictionaryObjectId = scope.dictionaryObjectId.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[Unit](options)
  }

  @JSExport
  def addNewLexicalEntry() = {
    backend.createLexicalEntry(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective)) onComplete {
      case Success(entryId) =>
        backend.getLexicalEntry(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective), entryId) onComplete {
          case Success(entry) =>
            scope.dictionaryTable.addEntry(entry)
          case Failure(e) =>
        }
      case Failure(e) => throw ControllerException("Attempt to create a new lexical entry failed", e)
    }
  }

  @JSExport
  def dataTypeString(dataType: TranslationGist): String = {
    dataType.atoms.find(a => a.localeId == 2) match {
      case Some(atom) =>
        atom.content
      case None => throw new ControllerException("")
    }
  }

  @JSExport
  def enableInput(entry: LexicalEntry, field: Field) = {
    if (!isInputEnabled(entry, field))
      enabledInputs = enabledInputs :+ (entry.getId, field.getId)
  }

  @JSExport
  def disableInput(entry: LexicalEntry, field: Field) = {
    if (isInputEnabled(entry, field))
      enabledInputs = enabledInputs.filterNot(p => p._1 == entry.getId && p._2 == field.getId)
  }

  @JSExport
  def isInputEnabled(entry: LexicalEntry, field: Field): Boolean = {
    enabledInputs.exists(input => input._1 == entry.getId && input._2 == field.getId)
  }

  @JSExport
  def saveTextValue(entry: LexicalEntry, field: Field, event: Event) = {
    val e = event.asInstanceOf[org.scalajs.dom.raw.Event]
    val textValue = e.target.asInstanceOf[HTMLInputElement].value

    val dictionaryId = CompositeId.fromObject(dictionary)
    val perspectiveId = CompositeId.fromObject(perspective)
    val entryId = CompositeId.fromObject(entry)

    val entity = EntityData(field.clientId, field.objectId, Utils.getLocale().getOrElse(2))
    entity.content = Some(textValue)
    backend.createEntity(dictionaryId, perspectiveId, entryId, entity) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, perspectiveId, entryId, entityId) onComplete {
          case Success(newEntity) =>
            scope.dictionaryTable.addEntity(entry, newEntity)
            disableInput(entry, field)
          case Failure(ex) => console.log(ex.getMessage)
        }
      case Failure(ex) => console.log(ex.getMessage)
    }
  }

  @JSExport
  def editLinkedPerspective(entry: LexicalEntry, field: Field, values: js.Array[Value]) = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/editLinkedDictionary.html"
    options.controller = "EditDictionaryModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionaryClientId = scope.dictionaryClientId.asInstanceOf[js.Object],
          dictionaryObjectId = scope.dictionaryObjectId.asInstanceOf[js.Object],
          perspectiveClientId = scope.perspectiveClientId,
          perspectiveObjectId = scope.perspectiveObjectId,
          linkPerspectiveClientId = field.link.get.clientId,
          linkPerspectiveObjectId = field.link.get.objectId,
          lexicalEntry = entry.asInstanceOf[js.Object],
          field = field.asInstanceOf[js.Object],
          links = values.map { _.asInstanceOf[GroupValue].link }
        )
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[Seq[Entity]](options)
    instance.result map { entities =>
      entities.foreach(e => scope.dictionaryTable.addEntity(entry, e))
    }
  }


  private[this] def load() = {

    backend.dataTypes() onComplete {
      case Success(dataTypes) =>
        backend.getFields(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective)) onComplete {
          case Success(fields) =>
            backend.getLexicalEntriesCount(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective)) onComplete {
              case Success(count) =>
                scope.count = count
                backend.getLexicalEntries(CompositeId.fromObject(dictionary), CompositeId.fromObject(perspective), LexicalEntriesType.All, scope.offset, scope.size) onComplete {
                  case Success(entries) =>
                    scope.dictionaryTable = DictionaryTable.build(fields, dataTypes, entries)
                  case Failure(e) => console.log(e.getMessage)
                }
              case Failure(e) => console.log(e.getMessage)
            }
          case Failure(e) => console.log(e.getMessage)
        }
      case Failure(e) => console.log(e.getMessage)
    }
  }


}
