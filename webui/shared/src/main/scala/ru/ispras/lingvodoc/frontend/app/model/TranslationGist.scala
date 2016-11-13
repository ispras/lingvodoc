package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class TranslationGist(@key("client_id") override val clientId: Int,
                      @key("object_id") override val objectId: Int,
                      @key("created_at") var createAt: Double,
                      @key("type") var gistType: String,
                      @key("contains") var atoms: js.Array[TranslationAtom]) extends Object(clientId, objectId) {

}
