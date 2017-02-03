package ru.ispras.lingvodoc.frontend.app.model

import derive.key

import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class Task(@key("id") id: String,
                @key("current_stage") currentStage: Int,
                @key("total_stages") totalStages: Int,
                @key("progress") progress: Int,
                @key("result_link")  resultLink: String = "",
                @key("task_family") taskFamily: String,
                @key("task_details") taskDetails: String,
                @key("status") status: String)

