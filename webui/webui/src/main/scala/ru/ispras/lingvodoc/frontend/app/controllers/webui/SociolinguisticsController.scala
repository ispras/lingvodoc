package ru.ispras.lingvodoc.frontend.app.controllers.webui

import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import io.plasmap.pamphlet._
import ru.ispras.lingvodoc.frontend.app.controllers.SearchQuery
import ru.ispras.lingvodoc.frontend.app.controllers.common.{DictionaryTable, Value}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{LoadingPlaceholder, SimplePlay}
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalOptions, ModalService}

import scala.concurrent.Future
import scala.scalajs.js
import scala.scalajs.js.UndefOr
import scala.scalajs.js.annotation.{JSExport, JSExportAll}
import scala.util.Random
import scala.scalajs.js.JSConverters._


@JSExportAll
case class Query(var question: UndefOr[String], var answer: UndefOr[String])


@js.native
trait SociolinguisticsScope extends Scope {
  var adoptedSearch: String = js.native
  var etymologySearch: String = js.native
  var search: js.Array[SearchQuery] = js.native
  var selectedPerspectives: js.Array[Perspective] = js.native
  var searchResults: js.Array[DictionaryTable] = js.native
  var questions: js.Array[String] = js.native
  var answers: js.Array[String] = js.native
  var queries: js.Array[Query] = js.native
  var progressBar: Boolean = js.native
}

@injectable("SociolinguisticsController")
class SociolinguisticsController(scope: SociolinguisticsScope, val backend: BackendService, modal: ModalService, val timeout: Timeout, val exceptionHandler: ExceptionHandler)
  extends AbstractController[SociolinguisticsScope](scope)
    with AngularExecutionContextProvider
    with SimplePlay
    with LoadingPlaceholder {

  private[this] var dictionaries = Seq[Dictionary]()
  private[this] var perspectives = Seq[Perspective]()
  private[this] var perspectivesMeta = Seq[PerspectiveMeta]()
  private[this] var dataTypes = Seq[TranslationGist]()
  private[this] var fields = Seq[Field]()
  private[this] var searchDictionaries = Seq[Dictionary]()
  private[this] var searchPerspectives = Seq[Perspective]()
  private[this] var allMarkers = Map[String, Marker]()
  private[this] var highlightMarkers = Seq[Marker]()
  private[this] var sociolinguisticsEntries = Seq[SociolinguisticsEntry]()

  // create map
  private[this] val leafletMap = createMap()
  private[this] val defaultIconOptions = IconOptions.iconUrl("static/images/marker-icon-default.png").iconSize(Leaflet.point(50, 41)).iconAnchor(Leaflet.point(13, 41)).build
  private[this] val defaultIcon = Leaflet.icon(defaultIconOptions)

  private[this] val selectedIconOptions = IconOptions.iconUrl("static/images/marker-icon-selected.png").iconSize(Leaflet.point(50, 41)).iconAnchor(Leaflet.point(13, 41)).build
  private[this] val selectedIcon = Leaflet.icon(selectedIconOptions)

  private[this] val resultIconOptions = IconOptions.iconUrl("static/images/marker-icon-selected.png").iconSize(Leaflet.point(100, 82)).iconAnchor(Leaflet.point(26, 82)).build
  private[this] val resultIcon = Leaflet.icon(resultIconOptions)

  // scope initialization
  scope.adoptedSearch = "unchecked"
  scope.etymologySearch = "unchecked"
  scope.search = js.Array(SearchQuery())
  scope.selectedPerspectives = js.Array[Perspective]()
  scope.questions = js.Array[String]()
  scope.answers = js.Array[String]()
  scope.queries = js.Array[Query](Query(Option.empty[String].orUndefined, Option.empty[String].orUndefined))
  scope.progressBar = false

  private[this] def getPerspective(perspectiveId: CompositeId): Option[Perspective] = {
    perspectives.find(_.getId == perspectiveId.getId)
  }

  private[this] def getDictionary(perspectiveId: CompositeId): Option[Dictionary] = {
    perspectives.find(_.getId == perspectiveId.getId).flatMap { perspective =>
      dictionaries.find(d => d.clientId == perspective.parentClientId && d.objectId == perspective.parentObjectId)
    }
  }

  private[this] def showInfo(dictionary: Dictionary, perspective: Perspective, meta: MetaData) = {

    val options = ModalOptions()
    options.templateUrl = "/static/templates/modal/viewInfoBlobs.html"
    options.controller = "ViewInfoBlobsController"
    options.backdrop = false
    options.keyboard = false
    options.size = "lg"
    options.resolve = js.Dynamic.literal(
      params = () => {
        js.Dynamic.literal(
          dictionary = dictionary.asInstanceOf[js.Object],
          perspective = perspective.asInstanceOf[js.Object],
          meta = meta.asInstanceOf[js.Object])
      }).asInstanceOf[js.Dictionary[js.Any]]
    val instance = modal.open[Unit](options)
  }

  @JSExport
  def addQuery(): Unit = {
    scope.queries.push(Query(Option.empty[String].orUndefined, Option.empty[String].orUndefined))
  }

  @JSExport
  def doSearch() = {

  }

  @JSExport
  def getSearchSource(entry: LexicalEntry): UndefOr[String] = {
    searchPerspectives.find(p => p.clientId == entry.parentClientId && p.objectId == entry.parentObjectId).flatMap { perspective =>
      searchDictionaries.find(d => d.clientId == perspective.parentClientId && d.objectId == perspective.parentObjectId).map { dictionary =>
        s"${dictionary.translation} / ${perspective.translation}"
      }
    }.orUndefined
  }

  @JSExport
  def viewGroupingTag(entry: LexicalEntry, field: Field, values: js.Array[Value]): Unit = {

    perspectives.find(p => p.clientId == entry.parentClientId && p.objectId == entry.parentObjectId).flatMap { perspective =>
      dictionaries.find(d => d.clientId == perspective.parentClientId && d.objectId == perspective.parentObjectId).map { dictionary =>

        val options = ModalOptions()
        options.templateUrl = "/static/templates/modal/viewGroupingTag.html"
        options.controller = "EditGroupingTagModalController"
        options.backdrop = false
        options.keyboard = false
        options.size = "lg"
        options.resolve = js.Dynamic.literal(
          params = () => {
            js.Dynamic.literal(
              dictionaryClientId = dictionary.clientId,
              dictionaryObjectId = dictionary.objectId,
              perspectiveClientId = perspective.clientId,
              perspectiveObjectId = perspective.objectId,
              lexicalEntry = entry.asInstanceOf[js.Object],
              field = field.asInstanceOf[js.Object],
              values = values.asInstanceOf[js.Object])
          }).asInstanceOf[js.Dictionary[js.Any]]

        val instance = modal.open[Unit](options)
        instance.result map { _ =>

        }
      }
    }
    ()
  }

  private[this] def highlightPerspective(perspectiveId: CompositeId): Unit = {
    allMarkers.get(perspectiveId.getId) foreach { marker =>
      marker.setIcon(resultIcon)
    }
  }

  private[this] def clearHighlighting(): Unit = {
    allMarkers.foreach {
      case (id, marker) =>
        if (scope.selectedPerspectives.exists(_.getId == id)) {
          marker.setIcon(selectedIcon)
        } else {
          marker.setIcon(defaultIcon)
        }
    }
  }

  private[this] def createMap(): LeafletMap = {
    // map object initialization
    val cssId = "map"
    val conf = LeafletMapOptions.zoomControl(true).scrollWheelZoom(true).build
    val leafletMap = Leaflet.map(cssId, conf) //.setView(Leaflet.latLng(51.505f, -0.09f), 13)
    val MapId = "lingvodoc_ispras_ru"
    val Attribution = "Map data &copy; <a href=\"http://openstreetmap.org\">OpenStreetMap</a> contributors, <a href=\"http://creativecommons.org/licenses/by-sa/2.0/\">CC-BY-SA</a>, Imagery © <a href=\"http://mapbox.com\">Mapbox</a>"

    // 61.5240° N, 105.3188° E
    val x = 61.5240f
    val y = 105.3188f
    val z = 3

    val uri = s"http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    val tileLayerOptions = TileLayerOptions
      .attribution(Attribution)
      .subdomains(scalajs.js.Array("a", "b", "c"))
      .mapId(MapId)
      .detectRetina(true).build

    val tileLayer = Leaflet.tileLayer(uri, tileLayerOptions)
    tileLayer.addTo(leafletMap)
    leafletMap.setView(Leaflet.latLng(x, y), z)
    leafletMap
  }

  override protected def onLoaded[T](result: T): Unit = {}

  override protected def onError(reason: Throwable): Unit = {}

  override protected def preRequestHook(): Unit = {}

  override protected def postRequestHook(): Unit = {


  }

  doAjax(() => {
    // load list of data types
    backend.dataTypes() flatMap { d =>
      dataTypes = d
      // load list of fields
      backend.fields() flatMap { f =>
        fields = f.toJSArray

        backend.getDictionaries(DictionaryQuery()) flatMap { d =>
          dictionaries = d
          backend.perspectives() flatMap { p =>
            perspectives = p
            backend.allPerspectivesMeta flatMap { pm =>
              perspectivesMeta = pm
              backend.sociolinguistics() flatMap { s =>
                sociolinguisticsEntries = s
                backend.sociolinguisticsQuestions() flatMap { questions =>
                  scope.questions = questions.toJSArray
                  backend.sociolinguisticsAnswers() map { answers =>
                    scope.answers = answers.toJSArray
                  }
                }
              }

            }
          }
        }
      }
    }
  })
}