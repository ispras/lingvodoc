package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class Locale(@key("id") id: Int,
                  @key("shortcut") shortcut: String,
                  @key("intl_name") name: String,
                  @key("created_at") createdAt: String)
