package ru.ispras.lingvodoc.frontend.api.exceptions

case class BackendException(message: String) extends  Exception(message)