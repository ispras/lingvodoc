package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import io.plasmap.pamphlet._
import ru.ispras.lingvodoc.frontend.app.controllers.traits.LoadingPlaceholder
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalOptions, ModalService}

import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.{JSExport, JSExportAll}
import org.scalajs.dom.console




@JSExportAll
case class SearchQuery(var query: String = "", var fieldId: String = "", var orFlag: Boolean = false)




@js.native
trait MapSearchScope extends Scope {
  var adoptedSearch: String = js.native
  var etymologySearch: String = js.native
  var search: js.Array[SearchQuery] = js.native
}

@injectable("MapSearchController")
class MapSearchController(scope: MapSearchScope, val backend: BackendService, modal: ModalService, val timeout: Timeout)
  extends AbstractController[MapSearchScope](scope)
    with AngularExecutionContextProvider
  with LoadingPlaceholder{

  private[this] var dictionaries = Seq[Dictionary]()
  private[this] var perspetives = Seq[Perspective]()
  private[this] var perspectivesMeta = Seq[PerspectiveMeta]()
  private[this] var dataTypes = Seq[TranslationGist]()
  private[this] var fields = Seq[Field]()

  scope.adoptedSearch = "unchecked"
  scope.etymologySearch = "unchecked"
  scope.search = js.Array(SearchQuery())


  private[this] def getPerspective(perspectiveId: CompositeId): Option[Perspective] = {
    perspetives.find(_.getId == perspectiveId.getId)
  }

  private[this] def getDictionary(perspectiveId: CompositeId): Option[Dictionary] = {
    perspetives.find(_.getId == perspectiveId.getId).flatMap { perspective =>
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
          meta = meta.asInstanceOf[js.Object]
        )
      }
    ).asInstanceOf[js.Dictionary[js.Any]]
    val instance = modal.open[Unit](options)
  }


  @JSExport
  def getSearchFields(): js.Array[Field] = {
    fields.toJSArray
  }

  @JSExport
  def addSearchField(): Unit = {
    scope.search.push(SearchQuery())
  }

  @JSExport
  def doSearch() = {

  }


  override protected def onLoaded[T](result: T): Unit = {}

  override protected def onError(reason: Throwable): Unit = {}

  override protected def preRequestHook(): Unit = {}

  override protected def postRequestHook(): Unit = {

    perspectivesMeta.filter(_.metaData.location.nonEmpty).foreach { meta =>

      val perspectiveId = CompositeId(meta.clientId, meta.objectId)
      val dictionary = getDictionary(perspectiveId)
      val perspective = getPerspective(perspectiveId)

      val latLng = meta.metaData.location.get.location
      val iconOptions = IconOptions.iconUrl("static/images/marker-icon.png").build
      val icon = Leaflet.icon(iconOptions)
      val markerOptions = js.Dynamic.literal("icon" -> icon).asInstanceOf[MarkerOptions]
      val marker = Leaflet.marker(Leaflet.latLng(latLng.lat, latLng.lng), markerOptions)

      marker.onClick(e => {
        dictionary.foreach { d =>
          perspective.foreach { p =>
            showInfo(d, p, meta.metaData)
          }
        }
      })

      marker.addTo(leafletMap)
    }
  }

  val cssId = "map"
  val conf = LeafletMapOptions.zoomControl(true).scrollWheelZoom(true).build
  val leafletMap = Leaflet.map(cssId, conf).setView(Leaflet.latLng(51.505f, -0.09f), 13)
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
            perspetives = p
            backend.allPerspectivesMeta map { pm =>
              perspectivesMeta = pm
            }
          }
        }
      }
    }
  })
}
