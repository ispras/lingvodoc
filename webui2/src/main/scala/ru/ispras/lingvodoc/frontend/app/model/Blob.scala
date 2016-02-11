package ru.ispras.lingvodoc.frontend.app.model

import derive.key

case class Blob(@key("client_id") override val clientId: Int,
                    @key("object_id") override val objectId: Int,
                    @key("name") name: String,
                    @key("data_type") dataType: String,
                    @key("content") url: String) extends Object(clientId, objectId) {
}