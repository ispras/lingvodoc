package ru.ispras.lingvodoc.frontend.app.model


import derive.key

case class SearchString(@key("searchstring") searchString: String, @key("search_by_or") searchByOr: Boolean, @key("entity_type") entityType: String)
