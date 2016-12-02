import sbt._
import org.scalajs.sbtplugin.ScalaJSPlugin.AutoImport._
import sbt.Keys._

object Dependencies {

  object lib {
    def jquery = "org.webjars" % "jquery" % "2.2.1" force()
    def angular = "org.webjars" % "angularjs" % "1.5.8"
    def bootstrap = "org.webjars" % "bootstrap" % "3.3.7"
    def bootstrapUI = "org.webjars" % "angular-ui-bootstrap" % "1.3.3"
    def validator = "org.webjars.bower" % "bootstrap-validator" % "0.10.2"
    def scalajsDom = "org.scala-js" %%%! "scalajs-dom" % "0.9.1" force()
    def upickle = "com.lihaoyi" %%%! "upickle" % "0.3.9"
    def scalaAngular = "com.greencatsoft" %%%! "scalajs-angular" % "0.8-SNAPSHOT"
    def pamphlet = "io.plasmap" %%%! "pamphlet" % "0.9-SNAPSHOT"
    def scalaXml = "org.scala-lang.modules" % "scala-xml_2.11" % "1.0.5"
    def scalaJquery = "be.doeraene" %%%! "scalajs-jquery" % "0.9.0"
  }

  object js {
    def jquery = "org.webjars" % "jquery" % "2.2.1"
    def angularjs = "org.webjars" % "angularjs" % "1.5.8"
    def bootstrap = "org.webjars" % "bootstrap" % "3.3.6"
    def bootstrapUI = "org.webjars" % "angular-ui-bootstrap" % "1.3.3"
    def bootstrapUITpls = "org.webjars" % "angular-ui-bootstrap" % "1.3.3"
    def validator = "org.webjars.bower" % "bootstrap-validator" % "0.10.2"
  }
}




