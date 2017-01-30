package ru.ispras.lingvodoc.frontend.app.model

import derive.key
import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class File(@key("client_id") override val clientId: Int,
                @key("object_id") override val objectId: Int,
                @key("name") name: String,
                @key("data_type") dataType: String,
                @key("created_at") createdAt: DateTime,
                @key("content") url: String) extends Object(clientId, objectId) {
}




