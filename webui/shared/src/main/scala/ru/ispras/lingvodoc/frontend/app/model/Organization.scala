package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class Organization(@key("organization_id") id: Int, @key("name") name: String, @key("about") about: String, @key ("users") users: Seq[Int])
