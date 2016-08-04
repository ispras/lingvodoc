package ru.ispras.lingvodoc.frontend.app.services

import com.greencatsoft.angularjs.{Factory, Service, injectable}

import scala.scalajs.js.annotation.JSExport
import scala.util.{Failure, Success}
import ru.ispras.lingvodoc.frontend.app.model.User
import org.scalajs.dom.console

/**
 * Service to share information about current user across multiple
 * controllers.
 */
@injectable("UserService")
class UserService extends Service {

  private[this] var user: Option[User] = None

  @JSExport
  def setUser(u: User) = {
    user = Some(u)
  }

  @JSExport
  def removeUser() = {
    user = None
  }

  @JSExport
  def getUser() = {
    user.get
  }

  @JSExport
  def hasUser(): Boolean = {
    user.nonEmpty
  }
}

@injectable("UserService")
class UserServiceFactory() extends Factory[UserService] {
  override def apply(): UserService = {
    console.log("factory!")
    new UserService()
  }
}
