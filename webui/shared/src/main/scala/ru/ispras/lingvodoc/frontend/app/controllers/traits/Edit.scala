package ru.ispras.lingvodoc.frontend.app.controllers.traits

import com.greencatsoft.angularjs.Controller
import com.greencatsoft.angularjs.core.{Event, RootScope, Scope}
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import org.scalajs.dom.{FormData, console}
import org.scalajs.dom.raw.{BlobPropertyBag, HTMLButtonElement, HTMLInputElement}
import ru.ispras.lingvodoc.frontend.app.controllers.common.{DictionaryTable, Value}
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.ExecutionContext
import scala.scalajs.js
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}

trait Edit {
  this: Controller[_] =>

  implicit val executionContext: ExecutionContext

  protected[this] def backend: BackendService
  protected[this] def modal: ModalService
  protected[this] def rootScope: RootScope

  protected[this] def dictionaryId: CompositeId
  protected[this] def perspectiveId: CompositeId
  protected[this] def dictionaryTable: DictionaryTable


  protected[this] var enabledInputs: Seq[String] = Seq[String]()
  protected[this] var editInputs: Seq[String] = Seq[String]()

  protected[this] var createdLexicalEntries: Seq[LexicalEntry] = Seq[LexicalEntry]()

  protected[this] def getCurrentLocale: Int

  @JSExport
  def addNewLexicalEntry(): Unit = {
    backend.createLexicalEntry(dictionaryId, perspectiveId) onComplete {
      case Success(entryId) =>
        backend.getLexicalEntry(dictionaryId, perspectiveId, entryId) onComplete {
          case Success(entry) =>
            dictionaryTable.addEntry(entry)
            createdLexicalEntries = createdLexicalEntries :+ entry
          case Failure(e) =>
        }
      case Failure(e) => throw ControllerException("Attempt to create a new lexical entry failed", e)
    }
  }

  @JSExport
  def createdByUser(lexicalEntry: LexicalEntry): Boolean = {
    createdLexicalEntries.contains(lexicalEntry)
  }


  @JSExport
  def enableInput(id: String): Unit = {
    if (!isInputEnabled(id)) {
      enabledInputs = enabledInputs :+ id
    }
  }

  @JSExport
  def disableInput(id: String): Unit = {
    if (isInputEnabled(id)) {
      enabledInputs = enabledInputs.filterNot(_.equals(id))
    }
  }

  @JSExport
  def isInputEnabled(id: String): Boolean = {
    enabledInputs.contains(id)
  }

  @JSExport
  def editEntity(id: String, entity: Entity): Unit = {
    editInputs = editInputs :+ entity.getId
  }

  @JSExport
  def isEditActive(entity: Entity): Boolean = {
    editInputs.contains(entity.getId)
  }

  private[this] def saveTextValue(inputId: String, entry: LexicalEntry, field: Field, textValue: String, parent: UndefOr[Value]): Unit = {

    val entryId = CompositeId.fromObject(entry)
    val entity = EntityData(field.clientId, field.objectId, getCurrentLocale)
    entity.content = Some(Left(textValue))

    // self
    parent map {
      parentValue =>
        entity.selfClientId = Some(parentValue.getEntity.clientId)
        entity.selfObjectId = Some(parentValue.getEntity.objectId)
    }

    backend.createEntity(dictionaryId, perspectiveId, entryId, entity) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, perspectiveId, entryId, entityId) onComplete {
          case Success(newEntity) =>

            parent.toOption match {
              case Some(x) => dictionaryTable.addEntity(x, newEntity)
              case None => dictionaryTable.addEntity(entry, newEntity)
            }

            disableInput(inputId)

          case Failure(ex) => console.log(ex.getMessage)
        }
      case Failure(ex) => console.log(ex.getMessage)
    }
  }


  @JSExport
  def saveTextValue(inputId: String, entry: LexicalEntry, field: Field, event: Event, parent: UndefOr[Value]): Unit = {
    val e = event.asInstanceOf[org.scalajs.dom.raw.Event]
    val target = e.target.asInstanceOf[HTMLButtonElement]
    val p = target.parentElement.parentElement

    val result = (0 until p.childNodes.length).toList.find(index => {
      p.childNodes.item(index).isInstanceOf[HTMLInputElement]
    }).map(i => p.childNodes.item(i).asInstanceOf[HTMLInputElement])

    result.foreach(node =>
      saveTextValue(inputId, entry, field, node.value, parent)
    )
  }


  @JSExport
  def saveTextValueKeydown(inputId: String, entry: LexicalEntry, field: Field, event: Event, parent: UndefOr[Value]): Unit = {
    val e = event.asInstanceOf[org.scalajs.dom.raw.KeyboardEvent]
    val textValue = e.target.asInstanceOf[HTMLInputElement].value

    if (e.keyCode == 13) {
      saveTextValue(inputId, entry, field, textValue, parent)
    }
  }

  @JSExport
  def saveFileValue(inputId: String, entry: LexicalEntry, field: Field, file: org.scalajs.dom.raw.File, parent: UndefOr[Value]): Unit = {

    val entryId = CompositeId.fromObject(entry)

    val entity = EntityData(field.clientId, field.objectId, Utils.getLocale().getOrElse(2))
    entity.content = Some(Right(FileContent(file.name, file.`type`, "")))

    // self
    parent map {
      parentValue =>
        entity.selfClientId = Some(parentValue.getEntity.clientId)
        entity.selfObjectId = Some(parentValue.getEntity.objectId)
    }

    import scala.scalajs.js.JSConverters._
    import upickle.default._
    import ru.ispras.lingvodoc.frontend.extras.facades.File

    val entityString = write(entity)
    val entityBlob = new org.scalajs.dom.raw.Blob((entityString::Nil).toJSArray.asInstanceOf[js.Array[js.Any]])
    val entityFile = new File((entityBlob::Nil).toJSArray, "entity.json")

    val formData = new FormData()
    formData.append("entity", entityFile)
    formData.append("content", file)

    backend.createEntity(dictionaryId, perspectiveId, entryId, formData) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, perspectiveId, entryId, entityId) onComplete {
          case Success(newEntity) =>
            rootScope.$apply(() => {
              parent.toOption match {
                case Some(x) => dictionaryTable.addEntity(x, newEntity)
                case None => dictionaryTable.addEntity(entry, newEntity)
              }
              disableInput(inputId)
            })
          case Failure(ex) => console.log(ex.getMessage)
        }
      case Failure(ex) => console.log(ex.getMessage)
    }
  }

  @JSExport
  def editGroupingTag(entry: LexicalEntry, field: Field, values: js.Array[Value]): Unit = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/editGroupingTag.html"
    options.controller = "EditGroupingTagModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionaryClientId = dictionaryId.clientId,
          dictionaryObjectId = dictionaryId.objectId,
          perspectiveClientId = perspectiveId.clientId,
          perspectiveObjectId = perspectiveId.objectId,
          lexicalEntry = entry.asInstanceOf[js.Object],
          field = field.asInstanceOf[js.Object],
          values = values.asInstanceOf[js.Object],
          edit = true
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Unit](options)
  }
}
