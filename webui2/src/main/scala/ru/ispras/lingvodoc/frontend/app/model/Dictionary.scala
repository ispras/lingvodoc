package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class Dictionary(@key("client_id") override val clientId: Int,
                      @key("object_id") override val objectId: Int,
                      @key("parent_client_id") var parentClientId: Int,
                      @key("parent_object_id") var parentObjectId: Int,
                      @key("translation") var translation: String,
                      @key("translation_string") var translationString: String,
                      @key("status") var status: String) extends Object(clientId, objectId) {

  var perspectives = js.Array[Perspective]()


}

object Dictionary {
  def emptyDictionary(clientId: Int, objectId: Int): Dictionary = {
    Dictionary(clientId, objectId, Int.MinValue, Int.MinValue, "", "", "")
  }
}
