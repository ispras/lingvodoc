package ru.ispras.lingvodoc.frontend.app.model

import upickle.default._
import upickle.Js

import scala.scalajs.js.annotation.{JSExport, JSExportAll}

import derive.key


object RequestType extends Enumeration {
  val GrantPermission, AddDictionaryToGrant, ParticipateOrganization, AdministrateOrganization = Value
}


class Subject()

@JSExportAll
case class GrantPermission(@key("grant_id") grantId: Int, @key("user_id") userId: Int) extends Subject

@JSExportAll
case class AddDictionaryToGrant(@key("grant_id") grantId: Int, @key("client_id") clientId: Int, @key("object_id") objectId: Int) extends Subject

@JSExportAll
case class OrganizationRequest(@key("org_id") organiztionId: Int, @key("user_id") userId: Int) extends Subject


@JSExportAll
case class UserRequest(id: Int,
                       senderId: Int,
                       recipientId: Int,
                       broadcastUuid: String,
                       `type`: RequestType.Value,
                       subject: Subject,
                       message: String)

object UserRequest {
  implicit val writer = upickle.default.Writer[UserRequest] {
    grant: UserRequest =>
      Js.Obj(
        ("id", Js.Num(grant.id))
      )
  }

  implicit val reader = upickle.default.Reader[UserRequest] {
    case js: Js.Obj =>

      val id = js("id").num.toInt
      val senderId = js("sender_id").num.toInt
      val recipientId = js("sender_id").num.toInt
      val broadcastUuid = js("broadcast_uuid").str

      val `type` = js("type").str match {
        case "grant_permission" =>
          RequestType.GrantPermission
        case "add_dict_to_grant" =>
          RequestType.AddDictionaryToGrant
        case "participate_org" =>
          RequestType.ParticipateOrganization
        case "administrate_org" =>
          RequestType.AdministrateOrganization
      }

      val s = js("subject")

      val subject: Subject = `type` match {
        case RequestType.GrantPermission =>
          readJs[GrantPermission](s)
        case RequestType.AddDictionaryToGrant =>
          readJs[AddDictionaryToGrant](s)
        case RequestType.ParticipateOrganization =>
          readJs[OrganizationRequest](s)
        case RequestType.AdministrateOrganization =>
          readJs[OrganizationRequest](s)
      }

      val message = js("message").str

      UserRequest(id, senderId, recipientId, broadcastUuid, `type`, subject, message)
  }
}


