package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class Field(@key("client_id") override val clientId: Int,
                 @key("object_id") override val objectId: Int,
                 @key("translation") var translation: String,
                 @key("translation_gist_client_id") var translationGistClientId: Int,
                 @key("translation_gist_object_id") var translationGistObjectId: Int,
                 @key("data_type_translation_gist_client_id") var dataTypeTranslationGistClientId: Int,
                 @key("data_type_translation_gist_object_id") var dataTypeTranslationGistObjectId: Int,
                 @key("is_translatable") var isTranslatable: Boolean,
                 @key("created_at") var createdAt: String) extends Object(clientId, objectId) {
}
