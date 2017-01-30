package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js
import scala.scalajs.js.Date
import scala.scalajs.js.annotation.JSExportAll


@JSExportAll
case class Dictionary(@key("client_id") override val clientId: Int,
                      @key("object_id") override val objectId: Int,
                      @key("parent_client_id") var parentClientId: Int,
                      @key("parent_object_id") var parentObjectId: Int,
                      @key("created_at") var createdAt: DateTime,
                      @key("translation") var translation: String,
                      @key("translation_gist_client_id") var translationGistClientId: Int,
                      @key("translation_gist_object_id") var translationGistObjectId: Int,
                      @key("state_translation_gist_client_id") var stateTranslationGistClientId: Int,
                      @key("state_translation_gist_object_id") var stateTranslationGistObjectId: Int) extends Object(clientId, objectId) {

  var perspectives = js.Array[Perspective]()
}

object Dictionary {
  def emptyDictionary(clientId: Int, objectId: Int): Dictionary = {
    Dictionary(clientId, objectId, Int.MinValue, Int.MinValue, new DateTime(new Date(0)), "", Int.MinValue, Int.MinValue, Int.MinValue, Int.MinValue)
  }
}
