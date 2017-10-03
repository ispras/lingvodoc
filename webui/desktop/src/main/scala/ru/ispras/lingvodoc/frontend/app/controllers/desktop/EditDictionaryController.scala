package ru.ispras.lingvodoc.frontend.app.controllers.desktop

import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import org.scalajs.dom.raw.HTMLInputElement
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseController
import ru.ispras.lingvodoc.frontend.app.controllers.common._
import ru.ispras.lingvodoc.frontend.app.controllers.traits._
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services._
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.URIUtils._
import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}
import scala.scalajs.js.JSConverters._
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
  var locales: js.Array[Locale] = js.native
  var translationLocaleId: Int = js.native
  var pageLoaded: Boolean = js.native
}

@injectable("EditDictionaryController")
class EditDictionaryController(scope: EditDictionaryScope,
                               params: RouteParams,
                               val modal: ModalService,
                               userService: UserService,
                               val backend: BackendService,
                               timeout: Timeout,
                               val exceptionHandler: ExceptionHandler)
  extends BaseController(scope, modal, timeout)
    with AngularExecutionContextProvider
    with SimplePlay
    with Pagination
    with LinkEntities
    with Edit
    with ViewMarkup
    with Tools {

  private[this] val dictionaryClientId = params.get("dictionaryClientId").get.toString.toInt
  private[this] val dictionaryObjectId = params.get("dictionaryObjectId").get.toString.toInt
  private[this] val perspectiveClientId = params.get("perspectiveClientId").get.toString.toInt
  private[this] val perspectiveObjectId = params.get("perspectiveObjectId").get.toString.toInt
  private[this] val sortBy = params.get("sortBy").map(_.toString).toOption

  protected[this] val dictionaryId = CompositeId(dictionaryClientId, dictionaryObjectId)
  protected[this] val perspectiveId = CompositeId(perspectiveClientId, perspectiveObjectId)

  private[this] var dataTypes: Seq[TranslationGist] = Seq[TranslationGist]()
  private[this] var fields: Seq[Field] = Seq[Field]()
  private[this] var perspectiveRoles: Option[PerspectiveRoles] = Option.empty[PerspectiveRoles]
  private[this] var selectedEntries: Seq[String] = Seq[String]()

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
  def mergeEntries(): Unit = {}

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
  def removeEntry(lexicalEntry: LexicalEntry): Unit = {
    lexicalEntry.markedForDeletion = true
  }

  @JSExport
  def removeEntity(lexicalEntry: LexicalEntry, entity: Entity): Unit = {
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
  def updateTextEntity(entry: LexicalEntry, entity: Entity, field: Field, event: Event): Unit = {
    val e = event.asInstanceOf[org.scalajs.dom.raw.Event]
    val newTextValue = e.target.asInstanceOf[HTMLInputElement].value
    val oldTextValue = entity.content

    if (newTextValue != oldTextValue) {

      backend.removeEntity(dictionaryId, perspectiveId, CompositeId.fromObject(entry), CompositeId.fromObject(entity)) map { _ =>
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
  def getTranslationLanguage(entity: Entity, field: Field): UndefOr[String] = {
    if (field.isTranslatable) {
      scope.locales.toSeq.find(_.id == entity.localeId).map(_.shortcut).orUndefined
    } else {
      Option.empty[String].orUndefined
    }
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
  def getSortByPageLink(field: Field): String = {
    getPageLink(scope.pageNumber) + "/" + field.getId
  }

  override protected def onStartRequest(): Unit = {
    scope.pageLoaded = false
  }

  override protected def onCompleteRequest(): Unit = {
    scope.pageLoaded = true
  }


  load(() => {

    backend.getLocales() map { locales =>
      scope.locales = locales.toJSArray
      scope.translationLocaleId = Utils.getLocale().getOrElse(2)
    }

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

  override protected[this] def getCurrentLocale: Int = scope.translationLocaleId

  override protected[this] def dictionaryTable: DictionaryTable = scope.dictionaryTable
}
