package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class PerspectiveRoles(@key("roles_users") var users: Map[String, Seq[Int]], @key("roles_organizations") var organizations: Map[String, Seq[Int]])
