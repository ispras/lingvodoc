package ru.ispras.lingvodoc.frontend.app.controllers.webui

import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import org.scalajs.dom.raw.HTMLInputElement
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseController
import ru.ispras.lingvodoc.frontend.app.controllers.common._
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{LoadingPlaceholder, Pagination, SimplePlay}
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services._
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.URIUtils._
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}



@js.native
trait EditDictionaryScope extends Scope {
  var filter: Boolean = js.native
  var path: String = js.native
  var size: Int = js.native
  var pageNumber: Int = js.native
  // number of currently open page
  var pageCount: Int = js.native
  // total number of pages
  var dictionaryTable: DictionaryTable = js.native
  var pageLoaded: Boolean = js.native
}

@injectable("EditDictionaryController")
class EditDictionaryController(scope: EditDictionaryScope,
                               params: RouteParams,
                               modal: ModalService,
                               userService: UserService,
                               backend: BackendService,
                               timeout: Timeout,
                               val exceptionHandler: ExceptionHandler)
  extends BaseController(scope, modal, timeout)
    with AngularExecutionContextProvider
    with SimplePlay
    with Pagination {

  private[this] val dictionaryClientId = params.get("dictionaryClientId").get.toString.toInt
  private[this] val dictionaryObjectId = params.get("dictionaryObjectId").get.toString.toInt
  private[this] val perspectiveClientId = params.get("perspectiveClientId").get.toString.toInt
  private[this] val perspectiveObjectId = params.get("perspectiveObjectId").get.toString.toInt
  private[this] val sortBy = params.get("sortBy").map(_.toString).toOption


  private[this] val dictionaryId = CompositeId(dictionaryClientId, dictionaryObjectId)
  private[this] val perspectiveId = CompositeId(perspectiveClientId, perspectiveObjectId)

  private[this] var enabledInputs: Seq[String] = Seq[String]()
  private[this] var editInputs: Seq[String] = Seq[String]()

  private[this] var createdLexicalEntries: Seq[LexicalEntry] = Seq[LexicalEntry]()

  private[this] var dataTypes: Seq[TranslationGist] = Seq[TranslationGist]()
  private[this] var fields: Seq[Field] = Seq[Field]()
  private[this] var perspectiveRoles: Option[PerspectiveRoles] = Option.empty[PerspectiveRoles]
  private[this] var selectedEntries = Seq[String]()

  scope.filter = true

  // Current page number. Defaults to 1
  scope.pageNumber = params.get("page").toOption.getOrElse(1).toString.toInt
  scope.pageCount = 0
  scope.size = 20


  scope.pageLoaded = false

  @JSExport
  def filterKeypress(event: Event): Unit = {
    val e = event.asInstanceOf[org.scalajs.dom.raw.KeyboardEvent]
    if (e.keyCode == 13) {
      val query = e.target.asInstanceOf[HTMLInputElement].value
      loadSearch(query)
    }
  }


  @JSExport
  def loadSearch(query: String): Unit = {
    backend.search(query, Some(CompositeId(perspectiveClientId, perspectiveObjectId)), tagsOnly = false) map {
      results =>
        val entries = results map (_.lexicalEntry)
        scope.dictionaryTable = DictionaryTable.build(fields, dataTypes, entries)
    }
  }

  @JSExport
  def viewSoundMarkup(soundValue: Value, markupValue: Value): Unit = {

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
              dictionaryClientId = dictionaryClientId.asInstanceOf[js.Object],
              dictionaryObjectId = dictionaryObjectId.asInstanceOf[js.Object]
            )
          }
        ).asInstanceOf[js.Dictionary[Any]]
        val instance = modal.open[Unit](options)
      case Failure(e) =>
    }
  }

  @JSExport
  def viewMarkup(markupValue: Value): Unit = {

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
              dictionaryClientId = dictionaryClientId.asInstanceOf[js.Object],
              dictionaryObjectId = dictionaryObjectId.asInstanceOf[js.Object]
            )
          }
        ).asInstanceOf[js.Dictionary[Any]]
        val instance = modal.open[Unit](options)
      case Failure(e) =>
    }
  }

  @JSExport
  def getActionLink(action: String): String = {
    "#/dictionary/" +
      encodeURIComponent(dictionaryClientId.toString) + '/' +
      encodeURIComponent(dictionaryObjectId.toString) + "/perspective/" +
      encodeURIComponent(perspectiveClientId.toString) + "/" +
      encodeURIComponent(perspectiveObjectId.toString) + "/" +
      action
  }

  @JSExport
  def toggleSelectedEntries(id: String): Unit = {
    if (selectedEntries.contains(id)) {
      selectedEntries = selectedEntries.filterNot(_ == id)
    } else {
      selectedEntries = selectedEntries :+ id
    }
  }

  @JSExport
  def selectedEntriesCount(): Int = {
    selectedEntries.length
  }

  @JSExport
  def mergeEntries(): Unit =
  {
    console.log("mergeEntries")

    val entry_list = selectedEntries flatMap { id =>
      scope.dictionaryTable.rows.find(_.entry.getId == id) map (_.entry) }

    val entry_id_list = entry_list map { entry =>
      CompositeId(entry.clientId, entry.objectId) }

    backend.bulkMerge(Seq.fill(1)(entry_id_list)).map
    {
      case entry_id_seq =>
        val entry_id = entry_id_seq(0)

        /* If we successfully merged lexical entries, we remove them from the table and try to show the new
         * lexical entry. */

        selectedEntries = Seq[String]()

        entry_list foreach { entry =>
          scope.dictionaryTable.removeEntry(entry) }

        backend.getLexicalEntry(dictionaryId, perspectiveId, entry_id) onComplete
        {
          case Success(entry) =>
            scope.dictionaryTable.addEntry(entry)
            createdLexicalEntries = createdLexicalEntries :+ entry

          case Failure(e) => error(e)
        }
    }

    .recover { case e: Throwable => error(e) }
  }

  @JSExport
  def removeEntries(): Unit = {
    val entries = selectedEntries.flatMap {
      id => scope.dictionaryTable.rows.find(_.entry.getId == id) map (_.entry)
    }

    val reqs = entries.map { entry =>
      backend.removeLexicalEntry(dictionaryId, perspectiveId, CompositeId.fromObject(entry))
    }

    Future.sequence(reqs) map { _ =>
      entries.foreach { entry =>
        scope.dictionaryTable.removeEntry(entry)
      }
    }
  }



  @JSExport
  def addNewLexicalEntry(): Unit = {
    backend.createLexicalEntry(dictionaryId, perspectiveId) onComplete {
      case Success(entryId) =>
        backend.getLexicalEntry(dictionaryId, perspectiveId, entryId) onComplete {
          case Success(entry) =>
            scope.dictionaryTable.addEntry(entry)
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
  def removeEntry(lexicalEntry: LexicalEntry) = {
    lexicalEntry.markedForDeletion = true
  }

  @JSExport
  def removeEntity(lexicalEntry: LexicalEntry, entity: Entity) = {
    backend.removeEntity(dictionaryId, perspectiveId, CompositeId.fromObject(lexicalEntry), CompositeId.fromObject(entity)) map { _=>
      entity.markedForDeletion = true
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
  def editEntity(id: String, entity: Entity): Unit = {
    editInputs = editInputs :+ entity.getId
  }

  @JSExport
  def isEditActive(entity: Entity): Boolean = {
    editInputs.contains(entity.getId)
  }

  @JSExport
  def updateTextEntity(entry: LexicalEntry, entity: Entity, field: Field, event: Event): Unit = {
    val e = event.asInstanceOf[org.scalajs.dom.raw.Event]
    val newTextValue = e.target.asInstanceOf[HTMLInputElement].value
    val oldTextValue = entity.content

    if (newTextValue != oldTextValue) {

      backend.removeEntity(dictionaryId, perspectiveId, CompositeId.fromObject(entry), CompositeId.fromObject(entity)) map { removedEntity =>
        entity.markedForDeletion = true

        val newEntity = EntityData(field.clientId, field.objectId, Utils.getLocale().getOrElse(2))
        newEntity.content = Some(Left(newTextValue))

        backend.createEntity(dictionaryId, perspectiveId, CompositeId.fromObject(entry), newEntity) onComplete {
          case Success(entityId) =>
            backend.getEntity(dictionaryId, perspectiveId, CompositeId.fromObject(entry), entityId) onComplete {
              case Success(updatedEntity) =>
                scope.dictionaryTable.updateEntity(entry, entity, updatedEntity)
              case Failure(ex) => error(ControllerException("Probably you don't have permissions to edit entities", ex))
            }
          case Failure(ex) => error(ControllerException("Probably you don't have permissions to edit entities", ex))
        }
      }
    }
    editInputs = editInputs.filterNot(_ == entity.getId)
  }



  @JSExport
  def isRemovable(entry: LexicalEntry, entity: Entity): Boolean = {
    perspectiveRoles match {
      case Some(roles) =>
        userService.get() match {
          case Some(user) =>
            roles.users.getOrElse("Can deactivate lexical entries", Seq[Int]()).contains(user.id)
          case None => false
        }
      case None => false
    }
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

    backend.createEntity(dictionaryId, perspectiveId, entryId, entity) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, perspectiveId, entryId, entityId) onComplete {
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

    backend.createEntity(dictionaryId, perspectiveId, entryId, entity) onComplete {
      case Success(entityId) =>
        backend.getEntity(dictionaryId, perspectiveId, entryId, entityId) onComplete {
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
          dictionaryClientId = dictionaryClientId.asInstanceOf[js.Object],
          dictionaryObjectId = dictionaryObjectId.asInstanceOf[js.Object],
          perspectiveClientId = perspectiveClientId,
          perspectiveObjectId = perspectiveObjectId,
          linkPerspectiveClientId = field.link.get.clientId,
          linkPerspectiveObjectId = field.link.get.objectId,
          lexicalEntry = entry.asInstanceOf[js.Object],
          field = field.asInstanceOf[js.Object],
          links = values.map {
            _.asInstanceOf[GroupValue].link
          }
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Seq[Entity]](options)
    instance.result map { entities =>
      entities.foreach(e => scope.dictionaryTable.addEntity(entry, e))
    }
  }

  @JSExport
  def editGroupingTag(entry: LexicalEntry, field: Field, values: js.Array[Value]) = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/editGroupingTag.html"
    options.controller = "EditGroupingTagModalController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionaryClientId = dictionaryClientId,
          dictionaryObjectId = dictionaryObjectId,
          perspectiveClientId = perspectiveClientId,
          perspectiveObjectId = perspectiveObjectId,
          lexicalEntry = entry.asInstanceOf[js.Object],
          field = field.asInstanceOf[js.Object],
          values = values.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Unit](options)
    instance.result map { _ =>

    }
  }

  @JSExport
  override def getPageLink(page: Int): String = {
    s"#/dictionary/$dictionaryClientId/$dictionaryObjectId/perspective/$perspectiveClientId/$perspectiveObjectId/edit/$page"
  }

  @JSExport
  def getFullPageLink(page: Int): String = {
    var url = getPageLink(page)
    sortBy foreach(s => url = url + "/" + s)
    url
  }

  @JSExport
  def getSortByPageLink(sort: String): String = {
    getPageLink(scope.pageNumber) + "/" + sort
  }

  @JSExport
  def phonology(): Unit = {
    backend.phonology(perspectiveId) map { blob =>
      val options = ModalOptions()
      options.templateUrl = "/static/templates/modal/message.html"
      options.windowClass = "sm-modal-window"
      options.controller = "MessageController"
      options.backdrop = false
      options.keyboard = false
      options.size = "lg"
      options.resolve = js.Dynamic.literal(
        params = () => {
          js.Dynamic.literal(
            "title" -> "",
            "message" -> "Background task created. Check tasks menu for details."
          )
        }
      ).asInstanceOf[js.Dictionary[Any]]
      modal.open[Unit](options)
    } recover { case e: Throwable =>
      error(e)
    }
  }

  override protected def onStartRequest(): Unit = {
    scope.pageLoaded = false
  }

  override protected def onCompleteRequest(): Unit = {
    scope.pageLoaded = true
  }


  load(() => {
    backend.perspectiveSource(perspectiveId) flatMap {
      sources =>
        scope.path = sources.reverse.map {
          _.source match {
            case language: Language => language.translation
            case dictionary: Dictionary => dictionary.translation
            case perspective: Perspective => perspective.translation
          }
        }.mkString(" >> ")

        backend.dataTypes() flatMap { d =>
          dataTypes = d
          backend.getFields(dictionaryId, perspectiveId) flatMap { f =>
            fields = f
            backend.getLexicalEntriesCount(dictionaryId, perspectiveId, LexicalEntriesType.All) flatMap { count =>
              scope.pageCount = scala.math.ceil(count.toDouble / scope.size).toInt
              val offset = getOffset(scope.pageNumber, scope.size)
              backend.getLexicalEntries(dictionaryId, perspectiveId, LexicalEntriesType.All, offset, scope.size, sortBy) flatMap { entries =>
                scope.dictionaryTable = DictionaryTable.build(fields, dataTypes, entries)

                backend.getPerspectiveRoles(dictionaryId, perspectiveId) map { roles =>
                  perspectiveRoles = Some(roles)
                  roles
                } recover {
                  case e: Throwable => Future.failed(e)
                }
              } recover {
                case e: Throwable => Future.failed(e)
              }
            } recover {
              case e: Throwable => Future.failed(e)
            }
          } recover {
            case e: Throwable => Future.failed(e)
          }
        } recover {
          case e: Throwable => Future.failed(e)
        }
    } recover {
      case e: Throwable => Future.failed(e)
    }
  })
}
