package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core._
import com.greencatsoft.angularjs.extensions.{ModalOptions, ModalService}
import com.greencatsoft.angularjs.{AngularExecutionContextProvider, injectable}
import org.scalajs.dom.raw.HTMLInputElement
import ru.ispras.lingvodoc.frontend.app.controllers.base.BaseController
import ru.ispras.lingvodoc.frontend.app.controllers.common._
import ru.ispras.lingvodoc.frontend.app.controllers.traits._
import ru.ispras.lingvodoc.frontend.app.exceptions.ControllerException
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, LexicalEntriesType}
import ru.ispras.lingvodoc.frontend.app.utils.Utils

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.URIUtils._
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.JSExport
import scala.scalajs.js.JSConverters._



@js.native
trait ViewDictionaryScope extends Scope {
  var filter: Boolean = js.native
  var path: String = js.native
  var size: Int = js.native
  var pageNumber: Int = js.native
  var pageCount: Int = js.native
  var dictionaryTable: DictionaryTable = js.native
  var selectedEntries: js.Array[String] = js.native
  var locales: js.Array[Locale] = js.native
  var pageLoaded: Boolean = js.native
}

@injectable("ViewDictionaryController")
class ViewDictionaryController(scope: ViewDictionaryScope,
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
    backend.search(query, Some(CompositeId(perspectiveClientId, perspectiveObjectId)), tagsOnly = false, published = Some(true)) map { results =>
        val entries = results.map(_.lexicalEntry).filterNot(_.markedForDeletion)
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
  def getTranslationLanguage(entity: Entity, field: Field): UndefOr[String] = {
    if (field.isTranslatable) {
      scope.locales.toSeq.find(_.id == entity.localeId).map(_.shortcut).orUndefined
    } else {
      Option.empty[String].orUndefined
    }
  }

  @JSExport
  def viewGroupingTag(entry: LexicalEntry, field: Field, values: js.Array[Value]): Unit = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/viewGroupingTag.html"
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
          values = values.asInstanceOf[js.Object],
          edit = false,
          published = true
        )
      }
    ).asInstanceOf[js.Dictionary[Any]]

    val instance = modal.open[Unit](options)
    instance.result map { _ =>

    }
  }

  load(() => {

    backend.getLocales() map { locales =>
      scope.locales = locales.toJSArray
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
            backend.getLexicalEntriesCount(dictionaryId, perspectiveId, LexicalEntriesType.Published) flatMap { count =>
              scope.pageCount = scala.math.ceil(count.toDouble / scope.size).toInt
              val offset = getOffset(scope.pageNumber, scope.size)
              backend.getLexicalEntries(dictionaryId, perspectiveId, LexicalEntriesType.Published, offset, scope.size, sortBy) flatMap { entries =>

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
    s"#/dictionary/$dictionaryClientId/$dictionaryObjectId/perspective/$perspectiveClientId/$perspectiveObjectId/view/$page"
  }

  override protected def onStartRequest(): Unit = {
    scope.pageLoaded = false

  }

  override protected def onCompleteRequest(): Unit = {
    scope.pageLoaded = true
  }

  override protected[this] def dictionaryTable: DictionaryTable = scope.dictionaryTable

  override protected def onOpen(): Unit = {}

  override protected def onClose(): Unit = {
    waveSurfer foreach {w =>
      w.destroy()}
  }
}
