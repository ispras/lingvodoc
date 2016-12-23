package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class PerspectiveRoleList(@key("Can create perspective roles and assign collaborators") var canCreatePerspectiveRolesAndAssignCollaborators: Seq[Int],
                               @key("Can delete lexical entries") var canDeleteLexicalEntries: Seq[Int],
                               @key("Can get perspective role list") var canGetPerspectiveRole: Seq[Int],
                               @key("Can deactivate lexical entries") var canDeactivateLexicalEntries: Seq[Int],
                               @key("Can view unpublished lexical entries") var canViewUnpublishedLexicalEntries: Seq[Int],
                               @key("Can view published lexical entries") var canViewPublishedLexicalEntries: Seq[Int],
                               @key("Can delete perspective") var canDeletePerspective: Seq[Int],
                               @key("Can approve lexical entries and publish") var canApproveLexicalEntriesAndPublish: Seq[Int],
                               @key("Can create lexical entries") var canCreateLexicalEntries: Seq[Int],
                               @key("Can edit perspective") var canEditPerspective: Seq[Int],
                               @key("Can resign users from perspective editors") var canResignUsersFromPerspectiveEditors: Seq[Int])