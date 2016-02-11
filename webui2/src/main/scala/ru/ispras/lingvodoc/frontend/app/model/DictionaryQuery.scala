package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class DictionaryQuery(@key("author") author: Int, @key("user_created") userCreated: Seq[Int])
