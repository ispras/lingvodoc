package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Event => _, _}
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import org.scalajs.dom._
import org.scalajs.dom.raw.HTMLInputElement
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseController
import ru.ispras.lingvodoc.frontend.app.controllers.common.{DictionaryTable, Value}
import ru.ispras.lingvodoc.frontend.app.controllers.traits._
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, LexicalEntriesType}

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.URIUtils._
import scala.scalajs.js.annotation.JSExport


@js.native
trait ContributionsScope extends Scope {
  //var filter: Boolean = js.native
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

@injectable("ContributionsController")
class ContributionsController(scope: ContributionsScope,
                              params: RouteParams,
                              val modal: ModalService,
                              val backend: BackendService,
                              timeout: Timeout,
                              val exceptionHandler: ExceptionHandler)
  extends BaseController(scope, modal, timeout)
    with AngularExecutionContextProvider
    with SimplePlay
    with Pagination
    with LinkEntities
    with ViewMarkup {

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


  // Current page number. Defaults to 1
  scope.pageNumber = params.get("page").toOption.getOrElse(1).toString.toInt
  scope.pageCount = 0
  scope.size = 20

  scope.selectedEntries = js.Array[String]()
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
  def dataTypeString(dataType: TranslationGist): String = {
    dataType.atoms.find(a => a.localeId == 2) match {
      case Some(atom) =>
        atom.content
      case None => throw new ControllerException("")
    }
  }

  @JSExport
  def accept(entry: LexicalEntry, value: Value): Unit = {
    val entity = value.getEntity()
    if (!entity.accepted) {
      backend.acceptEntities(dictionaryId, perspectiveId, CompositeId.fromObject(entity) :: Nil) map { _ =>
          scope.$apply(() => {
            entity.accepted = true
          })
      }
    }
  }

  @JSExport
  def acceptDisabled(value: Value): Boolean = {
    value.getEntity.accepted
  }

  @JSExport
  def acceptGroupingTag(entry: LexicalEntry, field: Field, values: js.Array[Value]): Unit = {

      val options = ModalOptions()
      options.templateUrl = "/static/templates/modal/acceptGroupingTag.html"
      options.controller = "ContributionsGroupingTagModalController"
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
            backend.getLexicalEntriesCount(dictionaryId, perspectiveId, LexicalEntriesType.NotAccepted) flatMap { count =>
              scope.pageCount = scala.math.ceil(count.toDouble / scope.size).toInt
              val offset = getOffset(scope.pageNumber, scope.size)
              backend.getLexicalEntries(dictionaryId, perspectiveId, LexicalEntriesType.NotAccepted, offset, scope.size, sortBy) flatMap { entries =>
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

  @JSExport
  override def getPageLink(page: Int): String = {
    s"#/dictionary/$dictionaryClientId/$dictionaryObjectId/perspective/$perspectiveClientId/$perspectiveObjectId/contributions/$page"
  }

  override protected[this] def dictionaryTable: DictionaryTable = scope.dictionaryTable

  override protected def onStartRequest(): Unit = {
    scope.pageLoaded = false
  }

  override protected def onCompleteRequest(): Unit = {
    scope.pageLoaded = true
  }

  override protected def onOpen(): Unit = {}

  override protected def onClose(): Unit = {
    waveSurfer foreach {w =>
      w.destroy()}
  }
}
