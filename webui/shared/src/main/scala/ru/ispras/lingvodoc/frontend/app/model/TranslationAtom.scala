package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js
import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class TranslationAtom(@key("client_id") override val clientId: Int,
                      @key("object_id") override val objectId: Int,
                      @key("parent_client_id") var parentClientId: Int,
                      @key("parent_object_id") var parentObjectId: Int,
                      @key("content") var content: String,
                      @key("locale_id") var localeId: Int) extends Object(clientId, objectId){

}
