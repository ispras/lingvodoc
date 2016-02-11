package ru.ispras.lingvodoc.frontend.app.model

import scala.scalajs.js.annotation.JSExportAll


/*
client_id: 2
contains: []
content: "CONV1"
entity_type: "Morphem Translation"
level: "leveloneentity"
locale_id: 1
marked_for_deletion: false
object_id: 1984
parent_client_id: 2
parent_object_id: 370
published: true
 */


@JSExportAll
case class Value(override val clientId: Int,
                 override val objectId: Int,
                 var parentClientId: Int,
                 var parentObjectId: Int,
                 var published: Boolean,
                 var markedForDeletion: Boolean) extends Object(clientId, objectId) {

}
