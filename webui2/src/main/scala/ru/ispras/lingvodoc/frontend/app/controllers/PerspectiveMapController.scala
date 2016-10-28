package ru.ispras.lingvodoc.frontend.app.controllers


import com.greencatsoft.angularjs.core.{Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import io.plasmap.pamphlet._
import org.scalajs.dom._
import ru.ispras.lingvodoc.frontend.app.controllers.traits.LoadingPlaceholder
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalInstance}

import scala.scalajs.js.JSConverters._
import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport


@js.native
trait PerspectiveMapScope extends Scope {
  var pageLoaded: Boolean = js.native
}

@injectable("PerspectiveMapController")
class PerspectiveMapController(scope: PerspectiveMapScope,
                               instance: ModalInstance[Unit],
                               backend: BackendService,
                               val timeout: Timeout,
                               params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[PerspectiveMapScope](scope)
  with AngularExecutionContextProvider
  with LoadingPlaceholder {

  private[this] val perspective = params("perspective").asInstanceOf[Perspective]
  private[this] var metaData: Option[MetaData] = Option.empty[MetaData]
  private[this] var locations: Seq[LatLng] = Seq[LatLng]()


  private[this] def createMarker(latLng: LatLng): Marker = {
    val iconOptions = IconOptions.iconUrl("static/images/marker-icon.png").build
    val icon = Leaflet.icon(iconOptions)
    val markerOptions = js.Dynamic.literal("icon" -> icon).asInstanceOf[MarkerOptions]
    Leaflet.marker(Leaflet.latLng(latLng.lat, latLng.lng), markerOptions).asInstanceOf[Marker]
  }


  private[this] def initializeMap() = {
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

    leafletMap.onClick(e => {
      if (locations.isEmpty) {

        val latLng = LatLng(e.latlng.lat, e.latlng.lng)
        val marker = createMarker(latLng)

        marker.onClick(e => {
          locations = locations.filterNot{location =>
            Math.abs(latLng.lat - e.latlng.lat) <= 0.001 && Math.abs(latLng.lng - e.latlng.lng) <= 0.001
          }
          leafletMap.removeLayer(marker)
        })

        locations = locations :+ latLng

        marker.addTo(leafletMap)
      }
    })

    metaData.foreach { meta =>
      meta.location foreach { location =>

        val latLng = location.location
        val iconOptions = IconOptions.iconUrl("static/images/marker-icon.png").build
        val icon = Leaflet.icon(iconOptions)
        val markerOptions = js.Dynamic.literal("icon" -> icon).asInstanceOf[MarkerOptions]
        val marker = Leaflet.marker(Leaflet.latLng(latLng.lat, latLng.lng), markerOptions)

        marker.onClick(e => {
          locations = locations.filterNot{location =>
            Math.abs(latLng.lat - e.latlng.lat) <= 0.001 && Math.abs(latLng.lng - e.latlng.lng) <= 0.001
          }

          leafletMap.removeLayer(marker)
        })

        locations = locations :+ latLng

        marker.addTo(leafletMap)
      }
    }



  }

  @JSExport
  def save() = {
    locations.headOption foreach { location =>
      metaData.foreach { meta =>
        val updatedMetaData = meta.copy(location = Some(Location("location", location)))
        backend.setPerspectiveMeta(CompositeId(perspective.parentClientId, perspective.parentObjectId), CompositeId(perspective.clientId, perspective.objectId), updatedMetaData) map { _ =>
          instance.dismiss(())
        }
      }
    }
  }

  @JSExport
  def cancel() = {
    instance.dismiss(())
  }


  override protected def onLoaded[T](result: T): Unit = {}

  override protected def onError(reason: Throwable): Unit = {}

  override protected def preRequestHook(): Unit = {}

  override protected def postRequestHook(): Unit = {
    initializeMap()
  }

  doAjax(() => {
    backend.getPerspectiveMeta(perspective) map { meta =>
      metaData = Some(meta)
    } recover {
      case e: Throwable => console.log("2321321")
    }
  })

}
