package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Event, RouteParams, Scope, Timeout}
import ru.ispras.lingvodoc.frontend.app.services._
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import org.scalajs.dom.console
import org.scalajs.dom.raw.HTMLInputElement
import ru.ispras.lingvodoc.frontend.app.controllers.common._
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{LoadingPlaceholder, Pagination, SimplePlay}
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.Future
import scala.scalajs.js.URIUtils._
import scala.scalajs.js.UndefOr


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
  var selectedEntries: js.Array[String] = js.native
  var pageLoaded: Boolean = js.native
}

@JSExport
@injectable("EditDictionaryController")
class EditDictionaryController(scope: EditDictionaryScope, params: RouteParams, modal: ModalService, userService: UserService, backend: BackendService, val timeout: Timeout) extends
  AbstractController[EditDictionaryScope](scope) with AngularExecutionContextProvider with SimplePlay with Pagination with LoadingPlaceholder {

  private[this] val dictionaryClientId = params.get("dictionaryClientId").get.toString.toInt
  private[this] val dictionaryObjectId = params.get("dictionaryObjectId").get.toString.toInt
  private[this] val perspectiveClientId = params.get("perspectiveClientId").get.toString.toInt
  private[this] val perspectiveObjectId = params.get("perspectiveObjectId").get.toString.toInt

  private[this] val dictionaryId = CompositeId(dictionaryClientId, dictionaryObjectId)
  private[this] val perspectiveId = CompositeId(perspectiveClientId, perspectiveObjectId)

  private[this] var enabledInputs: Seq[String] = Seq[String]()

  private[this] var createdLexicalEntries: Seq[LexicalEntry] = Seq[LexicalEntry]()

  private[this] var dataTypes: Seq[TranslationGist] = Seq[TranslationGist]()
  private[this] var fields: Seq[Field] = Seq[Field]()
  private[this] var perspectiveRoles: Option[PerspectiveRoles] = Option.empty[PerspectiveRoles]


  scope.filter = true

  // Current page number. Defaults to 1
  scope.pageNumber = params.get("page").toOption.getOrElse(1).toString.toInt
  scope.pageCount = 0
  scope.size = 20

  scope.selectedEntries = js.Array[String]()
  scope.pageLoaded = false

  @JSExport
  def filterKeypress(event: Event) = {
    val e = event.asInstanceOf[org.scalajs.dom.raw.KeyboardEvent]
    if (e.keyCode == 13) {
      val query = e.target.asInstanceOf[HTMLInputElement].value
      loadSearch(query)
    }
  }


  @JSExport
  def loadSearch(query: String) = {
    backend.search(query, Some(CompositeId(perspectiveClientId, perspectiveObjectId)), tagsOnly = false) map {
      results =>
        console.log(results.toJSArray)
        val entries = results map (_.lexicalEntry)
        scope.dictionaryTable = DictionaryTable.build(fields, dataTypes, entries)
    }
  }

  @JSExport
  def viewSoundMarkup(soundAddress: String, markupAddress: String) = {
    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/soundMarkup.html";
    options.windowClass = "sm-modal-window"
    options.controller = "SoundMarkupController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          soundAddress = soundAddress.asInstanceOf[js.Object],
          markupAddress = markupAddress.asInstanceOf[js.Object],
          dictionaryClientId = dictionaryClientId.asInstanceOf[js.Object],
          dictionaryObjectId = dictionaryObjectId.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[Unit](options)
  }

  @JSExport
  def getActionLink(action: String) = {
    "#/dictionary/" +
      encodeURIComponent(dictionaryClientId.toString) + '/' +
      encodeURIComponent(dictionaryObjectId.toString) + "/perspective/" +
      encodeURIComponent(perspectiveClientId.toString) + "/" +
      encodeURIComponent(perspectiveObjectId.toString) + "/" +
      action
  }


  @JSExport
  def viewPraatSoundMarkup(soundValue: Value, markupValue: Value) = {

    val soundAddress = soundValue.getContent()

    backend.convertPraatMarkup(CompositeId.fromObject(markupValue.getEntity())) onComplete {
      case Success(elan) =>
        val options = ModalOptions()
        options.templateUrl = "/static/templates/modal/soundMarkup.html";
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
        ).asInstanceOf[js.Dictionary[js.Any]]
        val instance = modal.open[Unit](options)
      case Failure(e) =>
    }
  }


  @JSExport
  def toggleSelectedEntries(id: String) = {
    if (scope.selectedEntries.contains(id)) {
      scope.selectedEntries = scope.selectedEntries.filterNot(_ == id)
    } else {
      scope.selectedEntries.push(id)
    }
  }

  @JSExport
  def mergeEntries() = {
    val entries = scope.selectedEntries.flatMap {
      id => scope.dictionaryTable.rows.find(_.entry.getId == id) map (_.entry)
    }
  }

  @JSExport
  def addNewLexicalEntry() = {
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
    backend.removeEntity(dictionaryId, perspectiveId, CompositeId.fromObject(lexicalEntry), CompositeId.fromObject(entity))
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
  def isRemovable(entry: LexicalEntry, entity: Entity): Boolean = {
    perspectiveRoles match {
      case Some(roles) =>
        userService.get() match {
          case Some(user) =>
            roles.users.getOrElse("Can delete lexical entries", Seq[Int]()).contains(user.id)
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
    ).asInstanceOf[js.Dictionary[js.Any]]

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
    ).asInstanceOf[js.Dictionary[js.Any]]

    val instance = modal.open[Unit](options)
    instance.result map { _ =>

    }
  }

  @JSExport
  override def getPageLink(page: Int): String = {
    s"#/dictionary/$dictionaryClientId/$dictionaryObjectId/perspective/$perspectiveClientId/$perspectiveObjectId/edit/$page"
  }

  override protected def onLoaded[T](result: T): Unit = {}

  override protected def onError(reason: Throwable): Unit = {}

  override protected def preRequestHook(): Unit = {
    scope.pageLoaded = false
  }

  override protected def postRequestHook(): Unit = {
    scope.pageLoaded = true
  }


  doAjax(() => {
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
            backend.getLexicalEntriesCount(dictionaryId, perspectiveId) flatMap { count =>
              scope.pageCount = scala.math.ceil(count.toDouble / scope.size).toInt
              val offset = getOffset(scope.pageNumber, scope.size)
              backend.getLexicalEntries(dictionaryId, perspectiveId, LexicalEntriesType.All, offset, scope.size) flatMap { entries =>
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
