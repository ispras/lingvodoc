package ru.ispras.lingvodoc.frontend.app.model

import derive.key
import scala.scalajs.js.annotation.JSExportAll

@JSExportAll
case class AdvancedSearchQuery(@key("adopted") adopted: Boolean,
                               @key("with_etymology") withEtymology: Boolean,
                               @key("searchstrings") searchStrings: Seq[SearchString],
                               @key("perspectives") perspectives: Seq[CompositeId])
