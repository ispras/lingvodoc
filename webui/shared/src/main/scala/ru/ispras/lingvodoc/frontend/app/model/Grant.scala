package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class Grant(id: Int,
                 issuerTranslationGistId: CompositeId,
                 issuer: String,
                 translationGistId: CompositeId,
                 translation: String,
                 issuerUrl: String,
                 grantUrl: String,
                 grantNumber: String,
                 begin: String,
                 end: String,
                 owners: Seq[Int],
                 metadata: Seq[String]
                )


object Grant {

  implicit val writer = upickle.default.Writer[Grant] {
    grant: Grant =>

      Js.Obj(
        ("id", Js.Num(grant.id)),
        ("issuer_translation_gist_client_id", Js.Num(grant.issuerTranslationGistId.clientId)),
        ("issuer_translation_gist_object_id", Js.Num(grant.issuerTranslationGistId.objectId)),
        ("issuer", Js.Str(grant.issuer)),
        ("translation_gist_client_id", Js.Num(grant.translationGistId.clientId)),
        ("translation_gist_object_id", Js.Num(grant.translationGistId.objectId)),
        ("translation", Js.Str(grant.translation)),
        ("issuer_url", Js.Str(grant.issuerUrl)),
        ("grant_url", Js.Str(grant.grantUrl)),
        ("grant_number", Js.Str(grant.grantNumber)),
        ("begin", Js.Str(grant.begin)),
        ("end", Js.Str(grant.end)),
        ("owners", Js.Arr(grant.owners.map(i => Js.Num(i)):_*)),
        ("additional_metadata", Js.Arr())
      )
  }

  implicit val reader = upickle.default.Reader[Grant] {
    case js: Js.Obj =>
      val id = js("id").num.toInt
      val issuerTranslationGistId = CompositeId(
        js("issuer_translation_gist_client_id").num.toInt,
        js("issuer_translation_gist_object_id").num.toInt
      )
      val issuer = js("issuer").str

      val translationGistId = CompositeId(
        js("translation_gist_client_id").num.toInt,
        js("translation_gist_object_id").num.toInt
      )

      val translation = js("translation").str

      val issuerUrl = js("issuer_url").str

      val grantUrl = js("grant_url").str

      val grantNumber = js("grant_number").str

      val begin = js("begin").str

      val end = js("end").str

      val owners = js("owners").arr.map(_.num.toInt)

      Grant(id, issuerTranslationGistId, issuer, translationGistId, translation, issuerUrl, grantUrl, grantNumber, begin, end, owners, Seq[String]())
  }
}

