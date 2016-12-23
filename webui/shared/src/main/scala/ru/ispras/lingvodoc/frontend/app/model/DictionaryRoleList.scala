package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class DictionaryRoleList(@key("Can edit dictionary options") var canEditDictionaryOptions: Seq[Int],
                              @key("Can create perspectives") var canCreatePerspectives: Seq[Int],
                              @key("Can resign users from dictionary editors") var canResignUsersFromDictionaryEditors: Seq[Int],
                              @key("Can get dictionary role list") var canGetDictionaryRoleList: Seq[Int],
                              @key("Can delete dictionary") var canDeleteDictionary: Seq[Int],
                              @key("Can create dictionary roles and assign collaborators") var canCreateDictionaryRolesAndAssignCollaborators: Seq[Int],
                              @key("Can merge dictionaries and perspectives") var canMergeDictionariesAndPerspectives: Seq[Int])




