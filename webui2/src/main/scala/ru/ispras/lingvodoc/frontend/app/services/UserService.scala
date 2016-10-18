package ru.ispras.lingvodoc.frontend.app.services

import com.greencatsoft.angularjs.{Factory, Service, injectable}
import ru.ispras.lingvodoc.frontend.app.model.User

import scala.scalajs.js.annotation.JSExport


/**
 * Service to share information about current user across multiple
 * controllers.
 */
@injectable("UserService")
class UserService(backendService: BackendService) extends Service {

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

  def get(): Option[User] = user
}

@injectable("UserService")
class UserServiceFactory(backendService: BackendService) extends Factory[UserService] {
  override def apply(): UserService = {
    new UserService(backendService)
  }
}
