package ru.ispras.lingvodoc.frontend.app.controllers.soundmarkupviewdata

import org.scalajs.jquery._

import scala.annotation.meta.field
import scala.scalajs.js
import scala.scalajs.js.annotation.JSExport

@JSExport("ELANDocumentJS")
class ELANDocumentJS(
  @(JSExport @field) var tiers: js.Dictionary[TierJS]
                     ) {
  def mergeTiers(newTiers: js.Dictionary[TierJS]) = {
    jQuery.extend(tiers, newTiers)
  }
}

@JSExport("TierJS")
class TierJS (
               @(JSExport @field) var annotations: js.Dictionary[AnnotationJS]
             )

@JSExport("AnnotationJS")
class AnnotationJS(
                  @(JSExport @field) var text: String,
                  @(JSExport @field) var startOffset: Double,
                  @(JSExport @field) var endOffset: Double,
                  @(JSExport @field) var durationOffset: Double
                  )

@JSExport("Point")
class Point(_x: Double, _y: Double) {
  @JSExport
  val x: Double = _x
  @JSExport
  var y: Double = _y
  @JSExport
  def abs: Double = Math.sqrt(x*x + y*y)
  @JSExport
  def sum: Double = x + y
  @JSExport
  def sum_=(v: Double): Unit = y = v - x
}