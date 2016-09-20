package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js.annotation.JSExportAll


@JSExportAll
case class UserListEntry(@key("id") id: Int,
                         @key("login") login: String,
                         @key("name") name: String,
                         @key("intl_name") intlName: String)

