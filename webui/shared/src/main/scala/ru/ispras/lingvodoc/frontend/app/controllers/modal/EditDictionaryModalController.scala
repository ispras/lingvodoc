package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.core.{Event, ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom._
import org.scalajs.dom.raw.HTMLInputElement
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseModalController
import ru.ispras.lingvodoc.frontend.app.controllers.common.{DictionaryTable, GroupValue, Value}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{LinkEntities, SimplePlay}
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services._
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}


@js.native
trait EditDictionaryModalScope extends Scope {
  var path: String = js.native
  var linkedPath: String = js.native
  var dictionaryTable: DictionaryTable = js.native
  var linkedDictionaryTable: DictionaryTable = js.native
  var count: Int = js.native
  var offset: Int = js.native
  var size: Int = js.native
  var pageCount: Int = js.native
  var edit: Boolean = js.native
}

@injectable("EditDictionaryModalController")
class EditDictionaryModalController(scope: EditDictionaryModalScope,
                                    val modal: ModalService,
                                    instance: ModalInstance[Seq[Entity]],
                                    backend: BackendService,
                                    timeout: Timeout,
                                    val exceptionHandler: ExceptionHandler,
                                    params: js.Dictionary[js.Function0[js.Any]])
  extends BaseModalController(scope, modal, instance, timeout, params)
    with SimplePlay
    with LinkEntities {

  protected[this] val dictionaryId: CompositeId = params("dictionaryId").asInstanceOf[CompositeId]
  protected[this] val perspectiveId: CompositeId = params("perspectiveId").asInstanceOf[CompositeId]
  private[this] val lexicalEntry = params("lexicalEntry").asInstanceOf[LexicalEntry]
  private[this] val field = params("field").asInstanceOf[Field]
  private[this] val entities = params("entities").asInstanceOf[js.Array[Entity]]


  private[this] val linkPerspectiveId = field.link.map { link =>
    CompositeId(link.clientId, link.objectId)
  }.ensuring(_.nonEmpty, "Field has no linked perspective!").get

  private[this] var perspectiveTranslation: Option[TranslationGist] = None

  private[this] var enabledInputs: Seq[String] = Seq[String]()

  override def spectrogramId: String = "#spectrogram-modal"

  scope.count = 0
  scope.offset = 0
  scope.size = 5
  scope.pageCount = 1
  scope.edit = true

  private[this] var createdEntities = Seq[Entity]()

  private[this] var dataTypes = Seq[TranslationGist]()
  private[this] var perspectiveFields = Seq[Field]()
  private[this] var linkedPerspectiveFields = Seq[Field]()

  load()

  @JSExport
  def viewSoundMarkup(soundValue: Value, markupValue: Value) = {

    val soundAddress = soundValue.getContent()

    backend.convertMarkup(CompositeId.fromObject(markupValue.getEntity())) onComplete {
      case Success(elan) =>
        val options = ModalOptions()
        options.templateUrl = "/static/templates/modal/soundMarkup.html"
        options.windowClass = "sm-modal-window"
        options.controller = "SoundMarkupController"
        options.backdrop = false
        options.keyboard = false
        options.size = "lg"
        options.resolve = js.Dynamic.literal(
          params = () => {
            js.Dynamic.literal(
              soundAddress = soundAddress.asInstanceOf[js.Object],
              markupData = elan.asInstanceOf[js.Object],
              dictionaryClientId = dictionaryId.clientId.asInstanceOf[js.Object],
              dictionaryObjectId = dictionaryId.objectId.asInstanceOf[js.Object]
            )
          }
        ).asInstanceOf[js.Dictionary[Any]]
        val instance = modal.open[Unit](options)
      case Failure(e) =>
    }
  }

  @JSExport
  def viewMarkup(markupValue: Value) = {

    backend.convertMarkup(CompositeId.fromObject(markupValue.getEntity())) onComplete {
      case Success(elan) =>
        val options = ModalOptions()
        options.templateUrl = "/static/templates/modal/soundMarkup.html"
        options.windowClass = "sm-modal-window"
        options.controller = "SoundMarkupController"
        options.backdrop = false
        options.keyboard = false
        options.size = "lg"
        options.resolve = js.Dynamic.literal(
          params = () => {
            js.Dynamic.literal(
              markupData = elan.asInstanceOf[js.Object],
              markupAddress = markupValue.getEntity().content.asInstanceOf[js.Object],
              dictionaryClientId = dictionaryId.clientId.asInstanceOf[js.Object],
              dictionaryObjectId = dictionaryId.objectId.asInstanceOf[js.Object]
            )
          }
        ).asInstanceOf[js.Dictionary[Any]]
        val instance = modal.open[Unit](options)
      case Failure(e) =>
    }
  }

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
                backend.getEntity(dictionaryId, perspectiveId, CompositeId.fromObject(lexicalEntry), entityId) onComplete {
                // backend.getEntity(dictionaryId, perspectiveId, entryId, entityId) onComplete {
                  case Success(newEntity) =>
                    createdEntities = createdEntities :+ newEntity
                    lexicalEntry.entities.push(newEntity)
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
  def loadPage(page: Int) = {
    val offset = (page - 1) * scope.size
    backend.getLexicalEntries(dictionaryId, linkPerspectiveId, LexicalEntriesType.All, offset, scope.size) onComplete {
      case Success(entries) =>
        scope.offset = offset
        scope.linkedDictionaryTable = DictionaryTable.build(linkedPerspectiveFields, dataTypes, entries)
      case Failure(e) => console.error(e.getMessage)
    }
  }

  @JSExport
  def range(min: Int, max: Int, step: Int) = {
    (min to max by step).toSeq.toJSArray
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
  def addLinkToLexicalEntry(entry: LexicalEntry) = {
    // add link to this lexical entry
    scope.dictionaryTable.addEntry(entry)
    // create corresponding entity in main perspective
    val entity = EntityData(field.clientId, field.objectId, 2)
    entity.linkClientId = Some(entry.clientId)
    entity.linkObjectId = Some(entry.objectId)
    backend.createEntity(dictionaryId, perspectiveId, CompositeId.fromObject(lexicalEntry), entity) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, perspectiveId, CompositeId.fromObject(lexicalEntry), entityId) onComplete {
          case Success(newEntity) =>
            lexicalEntry.entities.push(newEntity)
            createdEntities = createdEntities :+ newEntity
          case Failure(ex) => throw ControllerException("Attempt to get link entity failed", ex)
        }
      case Failure(ex) => throw ControllerException("Attempt to create link entity failed", ex)
    }
  }


  @JSExport
  def enableInput(id: String) = {
    if (!isInputEnabled(id)) {
      enabledInputs = enabledInputs :+ id
    }
  }

  @JSExport
  def disableInput(id: String) = {
    if (isInputEnabled(id)) {
      enabledInputs = enabledInputs.filterNot(_.equals(id))
    }
  }

  @JSExport
  def isInputEnabled(id: String): Boolean = {
    enabledInputs.contains(id)
  }

  @JSExport
  def saveTextValue(inputId: String, entry: LexicalEntry, field: Field, event: Event, parent: UndefOr[Value]) = {

    val e = event.asInstanceOf[org.scalajs.dom.raw.Event]
    val textValue = e.target.asInstanceOf[HTMLInputElement].value

    val entryId = CompositeId.fromObject(entry)

    val entity = EntityData(field.clientId, field.objectId, Utils.getLocale().getOrElse(2))
    entity.content = Some(Left(textValue))

    // self
    parent map {
      parentValue =>
        entity.selfClientId = Some(parentValue.getEntity.clientId)
        entity.selfObjectId = Some(parentValue.getEntity.objectId)
    }

    backend.createEntity(dictionaryId, linkPerspectiveId, entryId, entity) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, linkPerspectiveId, entryId, entityId) onComplete {
          case Success(newEntity) =>

            parent.toOption match {
              case Some(x) => scope.dictionaryTable.addEntity(x, newEntity)
              case None => scope.dictionaryTable.addEntity(entry, newEntity)
            }

            disableInput(inputId)

          case Failure(ex) => console.log(ex.getMessage)
        }
      case Failure(ex) => console.log(ex.getMessage)
    }
  }

  @JSExport
  def saveFileValue(inputId: String, entry: LexicalEntry, field: Field, fileName: String, fileType: String, fileContent: String, parent: UndefOr[Value]) = {


    val entryId = CompositeId.fromObject(entry)

    val entity = EntityData(field.clientId, field.objectId, Utils.getLocale().getOrElse(2))
    entity.content = Some(Right(FileContent(fileName, fileType, fileContent)))

    // self
    parent map {
      parentValue =>
        entity.selfClientId = Some(parentValue.getEntity.clientId)
        entity.selfObjectId = Some(parentValue.getEntity.objectId)
    }

    backend.createEntity(dictionaryId, linkPerspectiveId, entryId, entity) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, linkPerspectiveId, entryId, entityId) onComplete {
          case Success(newEntity) =>

            parent.toOption match {
              case Some(x) => scope.dictionaryTable.addEntity(x, newEntity)
              case None => scope.dictionaryTable.addEntity(entry, newEntity)
            }

            disableInput(inputId)

          case Failure(ex) => console.log(ex.getMessage)
        }
      case Failure(ex) => console.log(ex.getMessage)
    }

  }

  @JSExport
  def linkedPerspectiveName(): String = {
    perspectiveTranslation match {
      case Some(gist) =>
        val localeId = Utils.getLocale().getOrElse(2)
        gist.atoms.find(_.localeId == localeId) match {
          case Some(atom) => atom.content
          case None => ""
        }
      case None => ""
    }
  }

  @JSExport
  def isLexicalEntryLinked(entry: LexicalEntry): Boolean = {
    (dataTypes.find(d => d.atoms.exists(atom => atom.localeId == 2 && atom.content == "Link")) map {
      linkDataType =>
        val linkFields = perspectiveFields.filter(field => field.dataTypeTranslationGistClientId == linkDataType.clientId && field.dataTypeTranslationGistObjectId == linkDataType.objectId)

        val linkEntities = linkFields.flatMap {
          field =>
            lexicalEntry.entities.filter(e => e.fieldClientId == field.clientId && e.fieldObjectId == field.objectId)
        }

        linkEntities.exists { e => e.link match {
          case Some(link) => link.clientId == entry.clientId && link.objectId == entry.objectId
          case None => false
        }}
    }).get
  }


  @JSExport
  def close(): Unit = {
    instance.close(createdEntities)
  }


  private[this] def load() = {

    backend.perspectiveSource(linkPerspectiveId) onComplete {
      case Success(sources) =>
        scope.linkedPath = sources.reverse.map { _.source match {
          case language: Language => language.translation
          case dictionary: Dictionary => dictionary.translation
          case perspective: Perspective => perspective.translation
        }}.mkString(" >> ")
      case Failure(e) => error(e)
    }

    backend.perspectiveSource(perspectiveId) onComplete {
      case Success(sources) =>
        scope.path = sources.reverse.map { _.source match {
          case language: Language => language.translation
          case dictionary: Dictionary => dictionary.translation
          case perspective: Perspective => perspective.translation
        }}.mkString(" >> ")
      case Failure(e) => error(e)
    }

    backend.getPerspective(linkPerspectiveId) map {
      p =>
        backend.translationGist(CompositeId(p.translationGistClientId, p.translationGistObjectId)) map {
          gist =>
            perspectiveTranslation = Some(gist)
        }
    }

    backend.dataTypes() map { allDataTypes =>
      dataTypes = allDataTypes
      // get fields of main perspective
      backend.getFields(dictionaryId, perspectiveId) map { fields =>
        perspectiveFields = fields
        // get fields of this perspective
        backend.getFields(dictionaryId, linkPerspectiveId) map { linkedFields =>
          linkedPerspectiveFields = linkedFields
          val reqs =  entities.flatMap(_.link).toSeq.map { link =>
            backend.getLexicalEntry(dictionaryId, linkPerspectiveId, CompositeId(link.clientId, link.objectId)) map { entry =>
              Option(entry)
            } recover { case e: Throwable =>
              Option.empty[LexicalEntry]
            }
          }
          Future.sequence(reqs) map { lexicalEntries =>
            scope.dictionaryTable = DictionaryTable.build(linkedFields, dataTypes, lexicalEntries.flatten)
          } recover {
            case e: Throwable => error(e)
          }
        } recover {
          case e: Throwable => error(e)
        }
      } recover {
        case e: Throwable => error(e)
      }
    } recover {
      case e: Throwable => error(e)
    }
  }


  override protected def onModalClose(): Unit = {
    waveSurfer foreach {w =>
      w.destroy()}
    super.onModalClose()
  }

  override protected def onStartRequest(): Unit = {}

  override protected def onCompleteRequest(): Unit = {}

  override protected[this] def dictionaryTable: DictionaryTable = scope.dictionaryTable

}
