package ru.ispras.lingvodoc.frontend.app.controllers.modal

import com.greencatsoft.angularjs.core.{ExceptionHandler, Scope, Timeout}
import com.greencatsoft.angularjs.{AbstractController, AngularExecutionContextProvider, injectable}
import io.plasmap.pamphlet._

import ru.ispras.lingvodoc.frontend.app.controllers.traits.LoadingPlaceholder
import ru.ispras.lingvodoc.frontend.app.model._
import ru.ispras.lingvodoc.frontend.app.services.BackendService
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalOptions, ModalService}


import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport


@js.native
trait PerspectiveMapScope extends Scope {
  var pageLoaded: Boolean = js.native
}

@injectable("PerspectiveMapController")
class PerspectiveMapController(scope: PerspectiveMapScope,
                               instance: ModalInstance[Option[LatLng]],
                               backend: BackendService,
                               val timeout: Timeout,
                               val exceptionHandler: ExceptionHandler,
                               params: js.Dictionary[js.Function0[js.Any]])
  extends AbstractController[PerspectiveMapScope](scope)
    with AngularExecutionContextProvider {

  //private[this] val perspective = params("perspective").asInstanceOf[Perspective]
  //private[this] var metaData: Option[MetaData] = Option.empty[MetaData]
  private[this] var location: Option[LatLng] = params("location").asInstanceOf[Option[LatLng]]

  private[this] val defaultIconOptions = IconOptions.iconUrl("static/images/marker-icon-default.png").iconSize(Leaflet.point(50, 41)).iconAnchor(Leaflet.point(13, 41)).build
  private[this] val defaultIcon = Leaflet.icon(defaultIconOptions)

  //initializeMap()

  private[this] def createMarker(latLng: LatLng): Marker = {

    val markerOptions = js.Dynamic.literal("icon" -> defaultIcon).asInstanceOf[MarkerOptions]
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

    // add marker with left click
    leafletMap.onClick(e => {
      if (location.isEmpty) {

        val latLng = LatLng(e.latlng.lat, e.latlng.lng)
        val marker = createMarker(latLng)

        marker.onClick(e => {
          location = Option.empty[LatLng]
          leafletMap.removeLayer(marker)
        })

        marker.addTo(leafletMap)
        location = Some(latLng)
      }
    })

    // add already existing location
    location.foreach { latLng =>
      val markerOptions = js.Dynamic.literal("icon" -> defaultIcon).asInstanceOf[MarkerOptions]
      val marker = Leaflet.marker(Leaflet.latLng(latLng.lat, latLng.lng), markerOptions)

      marker.onClick(e => {
        location = Option.empty[LatLng]
        leafletMap.removeLayer(marker)
      })
      marker.addTo(leafletMap)
    }
  }

  @JSExport
  def save() = {
    instance.close(location)
  }

  @JSExport
  def cancel() = {
    instance.dismiss(())
  }

  import scala.scalajs.js.timers._
  setTimeout(2000) {
    initializeMap()
  }
}
