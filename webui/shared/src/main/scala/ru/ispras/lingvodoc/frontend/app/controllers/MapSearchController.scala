package ru.ispras.lingvodoc.frontend.app.controllers

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import io.plasmap.pamphlet.{Circle, CircleOptions, IconOptions, Leaflet, LeafletMap, LeafletMapOptions, Marker, MarkerOptions, TileLayerOptions}
import ru.ispras.lingvodoc.frontend.app.controllers.traits.{LoadingPlaceholder, SimplePlay}
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalOptions, ModalService}


import scala.scalajs.js
import scala.scalajs.js.JSConverters._
import scala.scalajs.js.annotation.{JSExport, JSExportAll}
import org.scalajs.dom.console
import ru.ispras.lingvodoc.frontend.app.controllers.common.{DictionaryTable, GroupValue, Value}

import scala.concurrent.Future
import scala.scalajs.js.UndefOr
import scala.util.Random

@JSExportAll
case class SearchQuery(var query: String = "", var fieldId: String = "", var orFlag: Boolean = false)

@js.native
trait MapSearchScope extends Scope {
  var adoptedSearch: String = js.native
  var etymologySearch: String = js.native
  var search: js.Array[SearchQuery] = js.native
  var selectedPerspectives: js.Array[Perspective] = js.native
  var searchResults: js.Array[DictionaryTable] = js.native
  var size: Int = js.native
  var pageNumber: Int = js.native
  var resultEntriesCount: Int = js.native
  var progressBar: Boolean = js.native
}

@injectable("MapSearchController")
class MapSearchController(scope: MapSearchScope, val backend: BackendService, modal: ModalService, val timeout: Timeout, val exceptionHandler: ExceptionHandler)
  extends AbstractController[MapSearchScope](scope)
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
  private[this] var foundEntries = Seq[Seq[LexicalEntry]]()

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
  scope.searchResults = js.Array[DictionaryTable]()
  scope.size = 10
  scope.pageNumber = 1
  scope.resultEntriesCount = -1
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
      }).asInstanceOf[js.Dictionary[Any]]
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

    scope.progressBar = true
    scope.resultEntriesCount = -1
    foundEntries = Seq[Seq[LexicalEntry]]()

    val adopted = scope.adoptedSearch match {
      case "checked" => true
      case "unchecked" => false
      case "clear" => false
    }

    val etymology = scope.etymologySearch match {
      case "checked" => true
      case "unchecked" => false
      case "clear" => false
    }

    val searchStrings = scope.search.toSeq.filter(_.query.nonEmpty).map { s =>
      fields.find(_.getId == s.fieldId) match {
        case Some(field) => SearchString(s.query, s.orFlag, field.translation)
        case None => SearchString(s.query, s.orFlag, "")
      }
    }

    if (searchStrings.nonEmpty) {
      clearHighlighting()
      backend.advanced_search(AdvancedSearchQuery(adopted, etymology, searchStrings, scope.selectedPerspectives.map(CompositeId.fromObject(_)))) map { entries =>
        // highlight results
        scope.resultEntriesCount = entries.size
        entries.foreach { e => highlightPerspective(CompositeId(e.parentClientId, e.parentObjectId)) }
        foundEntries = entries.groupBy(e => CompositeId(e.parentClientId, e.parentObjectId).getId).values.toSeq
        getPage(1)
      }
    }
  }

  @JSExport
  def getPage(p: Int): Unit = {
    scope.progressBar = true
    val offset = (p - 1) * scope.size
    val entries = foundEntries.slice(offset, offset + scope.size)

    // get perspectives
    Future.sequence(entries.map { e => backend.getPerspective(CompositeId(e.head.parentClientId, e.head.parentObjectId)) }) map { perspectives =>
      searchPerspectives = perspectives

      // get dictionaries
      Future.sequence(perspectives.map { p => backend.getDictionary(CompositeId(p.parentClientId, p.parentObjectId)) }) map { dictionaries =>
        searchDictionaries = dictionaries

        // get fields
        Future.sequence(perspectives.map { p =>
          backend.getFields(CompositeId(p.parentClientId, p.parentObjectId), CompositeId.fromObject(p)).map { fields =>
            DictionaryTable.build(fields, dataTypes, entries.find(e => e.head.parentClientId == p.clientId && e.head.parentObjectId == p.objectId).get)
          }
        }).foreach { tables =>
          scope.searchResults = tables.toJSArray
          scope.progressBar = false
          scope.pageNumber = p
        }
      }
    }
  }

  @JSExport
  def range() = {
    (1 to scala.math.ceil(foundEntries.size.toDouble / scope.size).toInt by 1).toSeq.toJSArray
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
  def viewLinkedPerspective(entry: LexicalEntry, field: Field, values: js.Array[Value]) = {


    perspectives.find(p => p.clientId == entry.parentClientId && p.objectId == entry.parentObjectId).flatMap { perspective =>
      dictionaries.find(d => d.clientId == perspective.parentClientId && d.objectId == perspective.parentObjectId).map { dictionary =>

        val options = ModalOptions()
        options.templateUrl = "/static/templates/modal/viewLinkedDictionary.html"
        options.controller = "ViewDictionaryModalController"
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
        instance.result map { _ => }
      }
    }
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
              values = values.asInstanceOf[js.Object],
              edit = false)
          }).asInstanceOf[js.Dictionary[Any]]

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
    val cssId = "searchMap"
    val conf = LeafletMapOptions.zoomControl(true).scrollWheelZoom(true).build
    val leafletMap = Leaflet.map(cssId, conf)
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

    val rng = Random

    var c = Seq[(Double, Double)]()

    perspectivesMeta.filter(_.metaData.location.nonEmpty).foreach { meta =>

      val perspectiveId = CompositeId(meta.clientId, meta.objectId)
      val dictionary = getDictionary(perspectiveId)
      val perspective = getPerspective(perspectiveId)

      val latLng = meta.metaData.location.get.location

      val markerOptions = js.Dynamic.literal("icon" -> defaultIcon).asInstanceOf[MarkerOptions]

      // TODO: Add support for marker cluster
      val p = if (c.exists(p => p._1 == latLng.lat && p._2 == latLng.lng)) {
        val latK = (-0.005) + (0.005 - (-0.005)) * rng.nextDouble
        val lngK = (-0.005) + (0.005 - (-0.005)) * rng.nextDouble
        Leaflet.latLng(latLng.lat + latK, latLng.lng + lngK)
      } else {
        c = c :+ (latLng.lat, latLng.lng)
        Leaflet.latLng(latLng.lat, latLng.lng)
      }

      val marker: Marker = Leaflet.marker(p, markerOptions).asInstanceOf[Marker]

      // prevents context menu from showing
      marker.on("contextmenu", (e: js.Any) => {

      })

      // marker click handler
      marker.onMouseDown(e => {
        e.originalEvent.button match {
          // left button click
          case 0 =>
            dictionary.foreach { d =>
              perspective.foreach { p =>
                showInfo(d, p, meta.metaData)
              }
            }
          // right button click
          case 2 =>
            perspective.foreach { p =>

              if (!scope.selectedPerspectives.exists(_.getId == p.getId)) {
                scope.selectedPerspectives.push(p)
                marker.setIcon(selectedIcon)

              } else {
                scope.selectedPerspectives = scope.selectedPerspectives.filterNot(_.getId == p.getId)
                marker.setIcon(defaultIcon)
              }
            }
        }
      })

      perspective.foreach { p =>
        allMarkers = allMarkers + (p.getId -> marker)
      }

      marker.addTo(leafletMap)
    }
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
            backend.allPerspectivesMeta map { pm =>
              perspectivesMeta = pm
            }
          }
        }
      }
    }
  })
}
