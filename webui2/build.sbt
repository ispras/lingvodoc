//name := "lingvodoc2 frontend"

organization in ThisBuild := "ru.ispras"

version in ThisBuild := "0.1-SNAPSHOT"

scalaVersion in ThisBuild := "2.11.8"

scalacOptions in ThisBuild ++= Seq("-deprecation", "-unchecked", "-feature")

resolvers in ThisBuild += Resolver.sonatypeRepo("snapshots")

resolvers += "Sonatype OSS Snapshots" at "https://oss.sonatype.org/content/repositories/snapshots"

import Dependencies._


lazy val root = project.in(file("."))
  .enablePlugins(ScalaJSPlugin)
  .aggregate(webui, desktop)
  .settings(name := "lingvodoc-ui"
  )

lazy val webui = (project in file("webui")).dependsOn(shared)
  .enablePlugins(ScalaJSPlugin)
  .settings(
    name := "webui",
    libraryDependencies ++= Seq(
      lib.scalajsDom,
      lib.upickle,
      lib.scalaAngular,
      lib.pamphlet,
      lib.scalaXml,
      lib.scalaJquery,
      lib.jquery,
      lib.angular,
      lib.bootstrap,
      lib.bootstrapUI,
      lib.validator
    ),
    jsDependencies ++= Seq(
      js.jquery / "2.2.1/jquery.js",
      js.angularjs / "angular.js",
      js.angularjs / "angular-route.js" dependsOn "angular.js",
      js.angularjs / "angular-animate.js" dependsOn "angular.js",
      js.bootstrap / "bootstrap.js" dependsOn "2.2.1/jquery.js",
      js.bootstrapUI / "ui-bootstrap.js" dependsOn "bootstrap.js",
      js.bootstrapUITpls / "ui-bootstrap-tpls.js" dependsOn "ui-bootstrap.js",
      js.validator / "0.10.2/dist/validator.js" dependsOn "bootstrap.js",
      ProvidedJS / "wavesurfer.min.js",
      ProvidedJS / "wavesurfer.spectrogram.js" dependsOn "wavesurfer.min.js",
      ProvidedJS / "wavesurfer.timeline.js" dependsOn "wavesurfer.min.js",
      ProvidedJS / "leaflet.js"
    ),
    relativeSourceMaps := true,
    skip in packageJSDependencies := false)

lazy val desktop = (project in file("desktop")).dependsOn(shared)
  .enablePlugins(ScalaJSPlugin)
  .settings(
    name := "desktop",
    libraryDependencies ++= Seq(
      lib.scalajsDom,
      lib.upickle,
      lib.scalaAngular,
      lib.pamphlet,
      lib.scalaXml,
      lib.scalaJquery,
      lib.jquery,
      lib.angular,
      lib.bootstrap,
      lib.bootstrapUI,
      lib.validator
    ),
    jsDependencies ++= Seq(
      js.jquery / "2.2.1/jquery.js",
      js.angularjs / "angular.js",
      js.angularjs / "angular-route.js" dependsOn "angular.js",
      js.angularjs / "angular-animate.js" dependsOn "angular.js",
      js.bootstrap / "bootstrap.js" dependsOn "2.2.1/jquery.js",
      js.bootstrapUI / "ui-bootstrap.js" dependsOn "bootstrap.js",
      js.bootstrapUITpls / "ui-bootstrap-tpls.js" dependsOn "ui-bootstrap.js",
      js.validator / "0.10.2/dist/validator.js" dependsOn "bootstrap.js",
      ProvidedJS / "wavesurfer.min.js",
      ProvidedJS / "wavesurfer.spectrogram.js" dependsOn "wavesurfer.min.js",
      ProvidedJS / "wavesurfer.timeline.js" dependsOn "wavesurfer.min.js",
      ProvidedJS / "leaflet.js"
    ),
    relativeSourceMaps := true,
    skip in packageJSDependencies := false)

lazy val shared = (project in file("shared"))
  .enablePlugins(ScalaJSPlugin)
  .settings(name := "shared",
    libraryDependencies ++= Seq(
      lib.scalajsDom,
      lib.upickle,
      lib.scalaAngular,
      lib.pamphlet,
      lib.scalaXml,
      lib.scalaJquery,
      lib.jquery,
      lib.angular,
      lib.bootstrap,
      lib.bootstrapUI,
      lib.validator
    ),
    jsDependencies ++= Seq(
      js.jquery / "2.2.1/jquery.js",
      js.angularjs / "angular.js",
      js.angularjs / "angular-route.js" dependsOn "angular.js",
      js.angularjs / "angular-animate.js" dependsOn "angular.js",
      js.bootstrap / "bootstrap.js" dependsOn "2.2.1/jquery.js",
      js.bootstrapUI / "ui-bootstrap.js" dependsOn "bootstrap.js",
      js.bootstrapUITpls / "ui-bootstrap-tpls.js" dependsOn "ui-bootstrap.js",
      js.validator / "0.10.2/dist/validator.js" dependsOn "bootstrap.js",
      ProvidedJS / "wavesurfer.min.js",
      ProvidedJS / "wavesurfer.spectrogram.js" dependsOn "wavesurfer.min.js",
      ProvidedJS / "wavesurfer.timeline.js" dependsOn "wavesurfer.min.js",
      ProvidedJS / "leaflet.js"
    )
  )
