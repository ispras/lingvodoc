package ru.ispras.lingvodoc.frontend.app.controllers


import com.greencatsoft.angularjs.{injectable, AbstractController}
import com.greencatsoft.angularjs.core.Scope
import com.greencatsoft.angularjs.extensions.{ModalInstance, ModalService}
import google.maps
import google.maps.LatLng
import google.maps.Data.Feature
import google.maps.LatLng
import org.scalajs.dom._
import ru.ispras.lingvodoc.frontend.app.model.Location

import scala.scalajs.js
import js.annotation.JSExport
import scala.scalajs.js.JSConverters._
import org.scalajs.dom
import ru.ispras.lingvodoc.frontend.app.services.BackendService

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

    scope.labels = scope.labels :+ Location(51.601203, -1.711370) :+ Location(51.801203, -1.774370) :+ Location(52.201203, -1.734370)


    console.log(scope.labels)

    scope.labels.toSeq.foreach {
      location =>
        val position = new LatLng(location.lat, location.lng)
        val marker = new google.maps.Marker(google.maps.MarkerOptions(
          position = position,
          map = scope.map,
          title = "Marker"
        ))
    }
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
