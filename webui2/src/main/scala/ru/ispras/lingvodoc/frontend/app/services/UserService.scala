package ru.ispras.lingvodoc.frontend.app.services

import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}
import ru.ispras.lingvodoc.frontend.app.model.User
import org.scalajs.dom.console

/**
 * Service to share information about current user across multiple
 * controllers.
 */
@JSExport
object UserService {

  @JSExport
  var user: User = null
}
