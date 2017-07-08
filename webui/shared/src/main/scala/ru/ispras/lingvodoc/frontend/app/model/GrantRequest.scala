package ru.ispras.lingvodoc.frontend.app.model

import upickle.Js

case class GrantRequest(
                         issuerTranslationGistId: CompositeId,
                         translationGistId: CompositeId,
                         issuerUrl: String,
                         grantUrl: String,
                         grantNumber: String,
                         begin: String,
                         end: String,
                         owners: Seq[Int],
                         metadata: Seq[String]
                       )


object GrantRequest {

  implicit val writer = upickle.default.Writer[GrantRequest] {
    grant: GrantRequest =>

      Js.Obj(
        ("issuer_translation_gist_client_id", Js.Num(grant.issuerTranslationGistId.clientId)),
        ("issuer_translation_gist_object_id", Js.Num(grant.issuerTranslationGistId.objectId)),
        ("translation_gist_client_id", Js.Num(grant.translationGistId.clientId)),
        ("translation_gist_object_id", Js.Num(grant.translationGistId.objectId)),
        ("issuer_url", Js.Str(grant.issuerUrl)),
        ("grant_url", Js.Str(grant.grantUrl)),
        ("grant_number", Js.Str(grant.grantNumber)),
        ("begin", Js.Str(grant.begin)),
        ("end", Js.Str(grant.end)),
        ("owners", Js.Arr(grant.owners.map(i => Js.Num(i)): _*)),
        ("additional_metadata", Js.Arr())
      )
  }

  implicit val reader = upickle.default.Reader[GrantRequest] {
    case js: Js.Obj =>
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

      GrantRequest(issuerTranslationGistId, translationGistId, issuerUrl, grantUrl, grantNumber, begin, end, owners, Seq[String]())
  }
}

