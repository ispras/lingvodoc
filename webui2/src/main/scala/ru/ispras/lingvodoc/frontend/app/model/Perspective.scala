package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class Perspective(@key("client_id") override val clientId: Int,
                       @key("object_id") override val objectId: Int,
                       @key("parent_client_id") parentClientId: Int,
                       @key("parent_object_id") parentObjectId: Int,
                       @key("translation") var translation: String,
                       @key("translation_string") var translationString: String,
                       @key("status") var status: String,
                       @key("is_template") var isTemplate: Boolean,
                       @key("marked_for_deletion") var markedForDeletion: Boolean) extends Object(clientId, objectId) {

  var fields: js.Array[Field] = js.Array()
  var blobs: js.Array[Blob] = js.Array()
  var location: Option[LatLng] = None
}
