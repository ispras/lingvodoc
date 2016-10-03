package ru.ispras.lingvodoc.frontend.app.controllers


import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.{AbstractController, injectable}
import google.maps
import google.maps.LatLng
import org.scalajs.dom._
import ru.ispras.lingvodoc.frontend.app.services.{BackendService, ModalInstance, ModalService}

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport


@js.native
trait PerspectiveMapScope extends Scope {
  var labels: js.Array[Location] = js.native
  var map: maps.Map = js.native
}

@injectable("PerspectiveMapController")
class PerspectiveMapController(scope: PerspectiveMapScope,
                               modal: ModalService,
                               instance: ModalInstance[Unit],
                               backend: BackendService) extends AbstractController[PerspectiveMapScope](scope) {

  private[this] val mapElementId: String = "map-canvas"
  private[this] var displayedLabels: Seq[LatLng] = Seq[LatLng]()

  scope.labels = js.Array()


  @JSExport
  def ok() = {
    instance.dismiss(())
  }

  // display markers
  @JSExport
  def drawLocations() = {

  }


  @JSExport
  def initializeMap() = {

    // Initialize Google Maps
    val opts = google.maps.MapOptions(
      center = new LatLng(51.201203, -1.724370),
      zoom = 8,
      panControl = false,
      streetViewControl = false,
      mapTypeControl = false)

    scope.map = new google.maps.Map(document.getElementById(mapElementId), opts)

    // Google maps event handlers
    google.maps.event.addListener(scope.map, "click", () => {

    })

    // FIXME: An extremely ugly workaround to prevent incorrect initialization of google maps object
    // Better way: somehow hook bs.modal.shown event
    // Even better: do not re-create google maps object and re-use an old one as google documentation suggests
    // setTimeout(() => {
    //   google.maps.event.trigger(scope.map, "resize")
    //   drawLocations()
    // }, 2000)

    // there is no saveTimeout in 0.6.10 version of scalajs plugin, here is a workaround
    scala.scalajs.js.timers.setTimeout(2000)
    {
      google.maps.event.trigger(scope.map, "resize")
      drawLocations()
    }
  }
}
