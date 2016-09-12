package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Event, Scope}
import com.greencatsoft.angularjs.{AbstractController, injectable}
import org.scalajs.dom._
import org.scalajs.dom.raw.HTMLInputElement
import ru.ispras.lingvodoc.frontend.app.controllers.common.DictionaryTable
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, LexicalEntriesType, ModalInstance, ModalService}
import ru.ispras.lingvodoc.frontend.app.utils.LingvodocExecutionContext.Implicits.executionContext
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait EditDictionaryModalScope extends Scope {
  var dictionaryTable: DictionaryTable = js.native
  var count: Int = js.native
  var offset: Int = js.native
  var size: Int = js.native
}

@injectable("EditDictionaryModalController")
class EditDictionaryModalController(scope: EditDictionaryModalScope,
                                    modal: ModalService,
                                    instance: ModalInstance[Seq[Entity]],
                                    backend: BackendService,
                                    params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[EditDictionaryModalScope](scope) {

  private[this] val dictionaryClientId = params("dictionaryClientId").asInstanceOf[Int]
  private[this] val dictionaryObjectId = params("dictionaryObjectId").asInstanceOf[Int]
  private[this] val perspectiveClientId = params("perspectiveClientId").asInstanceOf[Int]
  private[this] val perspectiveObjectId = params("perspectiveObjectId").asInstanceOf[Int]
  private[this] val linkPerspectiveClientId = params("linkPerspectiveClientId").asInstanceOf[Int]
  private[this] val linkPerspectiveObjectId = params("linkPerspectiveObjectId").asInstanceOf[Int]
  private[this] val lexicalEntry = params("lexicalEntry").asInstanceOf[LexicalEntry]
  private[this] val field = params("field").asInstanceOf[Field]
  private[this] val links = params("links").asInstanceOf[js.Array[Link]]

  private[this] val dictionaryId = CompositeId(dictionaryClientId, dictionaryObjectId)
  private[this] val perspectiveId = CompositeId(perspectiveClientId, perspectiveObjectId)
  private[this] val linkPerspectiveId = CompositeId(linkPerspectiveClientId, linkPerspectiveObjectId)

  private[this] var enabledInputs: Seq[(String, String)] = Seq[(String, String)]()


  scope.count = 0
  scope.offset = 0
  scope.size = 20


  private[this] var createdEntities = Seq[Entity]()


  load()

  @JSExport
  def addNewLexicalEntry() = {

    backend.createLexicalEntry(dictionaryId, linkPerspectiveId) onComplete {
      case Success(entryId) =>
        backend.getLexicalEntry(dictionaryId, linkPerspectiveId, entryId) onComplete {
          case Success(entry) =>
            scope.dictionaryTable.addEntry(entry)
            // create corresponding entity in main perspective
            val entity = EntityData(field.clientId, field.objectId, 2)
            entity.linkClientId = Some(entry.clientId)
            entity.linkObjectId = Some(entry.objectId)
            backend.createEntity(dictionaryId, perspectiveId, CompositeId.fromObject(lexicalEntry), entity) onComplete {
              case Success(entityId) =>
                backend.getEntity(dictionaryId, perspectiveId, entryId, entityId) onComplete {
                  case Success(newEntity) =>
                    createdEntities = createdEntities :+ newEntity
                  case Failure(ex) => throw ControllerException("Attempt to get link entity failed", ex)
                }
              case Failure(ex) => throw ControllerException("Attempt to create link entity failed", ex)
            }

          case Failure(e) => throw ControllerException("Attempt to get linked lexical entry failed", e)
        }
      case Failure(e) => throw ControllerException("Attempt to create linked lexical entry failed", e)
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

    val entryId = CompositeId.fromObject(entry)

    val entity = EntityData(field.clientId, field.objectId, Utils.getLocale().getOrElse(2))
    entity.content = Some(textValue)
    backend.createEntity(dictionaryId, linkPerspectiveId, entryId, entity) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, linkPerspectiveId, entryId, entityId) onComplete {
          case Success(newEntity) =>
            scope.dictionaryTable.addEntity(entry, newEntity)
            disableInput(entry, field)
          case Failure(ex) => console.log(ex.getMessage)
        }
      case Failure(ex) => console.log(ex.getMessage)
    }
  }

  @JSExport
  def close() = {
    instance.close(createdEntities)
  }



  private[this] def load() = {

    backend.dataTypes() onComplete {
      case Success(dataTypes) =>
        backend.getFields(dictionaryId, linkPerspectiveId) onComplete {
          case Success(fields) =>
            val reqs = links.toSeq.map { link => backend.getLexicalEntry(dictionaryId, linkPerspectiveId, CompositeId(link.clientId, link.objectId)) }
            Future.sequence(reqs) onComplete {
              case Success(lexicalEntries) =>
                scope.dictionaryTable = DictionaryTable.build(fields, dataTypes, lexicalEntries)
              case Failure(e) =>
            }
          case Failure(e) => console.log(e.getMessage)
        }
      case Failure(e) => console.log(e.getMessage)
    }
  }
}
