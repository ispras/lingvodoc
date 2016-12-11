organization in ThisBuild := "ru.ispras"

version in ThisBuild := "0.1-SNAPSHOT"

scalaVersion in ThisBuild := "2.11.8"

scalacOptions in ThisBuild ++= Seq("-deprecation", "-unchecked", "-feature")

resolvers in ThisBuild += Resolver.sonatypeRepo("snapshots")

resolvers += "Sonatype OSS Snapshots" at "https://oss.sonatype.org/content/repositories/snapshots"


import Dependencies._
import org.scalajs.sbtplugin.ScalaJSPlugin.AutoImport._

lazy val deployAll = TaskKey[Unit]("deployAll", "Copy shared static to artifacts directory")
lazy val deployShared = TaskKey[Unit]("deployShared", "Copy shared static files to artifacts directory")
lazy val deployDesktop = TaskKey[Unit]("deployDesktop", "Copy desktop static files to artifacts directory")
lazy val deployWebUI = TaskKey[Unit]("deployWebUI", "Copy webui static files to artifacts directory")

lazy val root = project.in(file("."))
  .enablePlugins(ScalaJSPlugin)
  .aggregate(webui, desktop)
  .settings(
    name := "lingvodoc-ui",

    deployShared := {
      val finder: PathFinder = (shared.base / "src/templates") ** "*"
      val desktopMappings = finder.get pair rebase(shared.base / "src/templates", "artifacts/desktop/templates")
      val webUIMappings = finder.get pair rebase(shared.base / "src/templates", "artifacts/webui/templates")
      val files = desktopMappings.map(p => (p._1, file(p._2))) ++ webUIMappings.map(p => (p._1, file(p._2)))
      IO.copy(files, overwrite = true)
    },
    deployDesktop := {
      val finder: PathFinder = (desktop.base / "src/templates") ** "*"
      val mappings = finder.get pair rebase(desktop.base / "src/templates", "artifacts/desktop/templates")
      val files = mappings.map(p => (p._1, file(p._2)))
      IO.copy(files, overwrite = true)
    },
    deployWebUI := {
      val finder: PathFinder = (webui.base / "src/templates") ** "*"
      val mappings = finder.get pair rebase(webui.base / "src/templates", "artifacts/webui/templates")
      val files = mappings.map(p => (p._1, file(p._2)))
      IO.copy(files, overwrite = true)
    },

    deployAll := {

    },

    deployDesktop <<= deployDesktop dependsOn(fullOptJS in Compile, deployShared),
    deployWebUI <<= deployWebUI dependsOn(fullOptJS in Compile, deployShared),
    deployAll <<= deployAll dependsOn(deployDesktop, deployWebUI)
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
      js.jquery / "2.2.1/jquery.js" minified "2.2.1/jquery.min.js",
      js.angularjs / "angular.js" minified "angular.min.js",
      js.angularjs / "angular-route.js" minified "angular-route.min.js" dependsOn "angular.js",
      js.angularjs / "angular-animate.js" minified "angular-animate.min.js" dependsOn "angular.js",
      js.angularjs / "angular-sanitize.js" minified "angular-sanitize.min.js" dependsOn "angular.js",
      js.bootstrap / "bootstrap.js" minified "bootstrap.min.js" dependsOn "2.2.1/jquery.js",
      js.bootstrapUI / "ui-bootstrap.js" minified "ui-bootstrap.min.js" dependsOn "bootstrap.js",
      js.bootstrapUITpls / "ui-bootstrap-tpls.js" minified "ui-bootstrap-tpls.min.js" dependsOn "ui-bootstrap.js",
      js.validator / "0.10.2/dist/validator.js" minified "0.10.2/dist/validator.min.js" dependsOn "bootstrap.js",
      ProvidedJS / "wavesurfer.js",
      ProvidedJS / "wavesurfer.spectrogram.js" dependsOn "wavesurfer.js",
      ProvidedJS / "wavesurfer.timeline.js" dependsOn "wavesurfer.js",
      ProvidedJS / "leaflet.js"
    ),
    relativeSourceMaps := true,
    skip in packageJSDependencies := false,
    artifactPath in (Compile, fastOptJS) := file("artifacts/webui/js") / "lingvodoc.js",
    artifactPath in (Compile, fullOptJS) := file("artifacts/webui/js") / "lingvodoc.js",
    artifactPath in (Compile, packageJSDependencies) := file("artifacts/webui/js") / "lingvodoc-deps.js"
  )

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
      js.jquery / "2.2.1/jquery.js" minified "2.2.1/jquery.min.js",
      js.angularjs / "angular.js" minified "angular.min.js",
      js.angularjs / "angular-route.js" minified "angular-route.min.js" dependsOn "angular.js",
      js.angularjs / "angular-animate.js" minified "angular-animate.min.js" dependsOn "angular.js",
      js.angularjs / "angular-sanitize.js" minified "angular-sanitize.min.js" dependsOn "angular.js",
      js.bootstrap / "bootstrap.js" minified "bootstrap.min.js" dependsOn "2.2.1/jquery.js",
      js.bootstrapUI / "ui-bootstrap.js" minified "ui-bootstrap.min.js" dependsOn "bootstrap.js",
      js.bootstrapUITpls / "ui-bootstrap-tpls.js" minified "ui-bootstrap-tpls.min.js" dependsOn "ui-bootstrap.js",
      js.validator / "0.10.2/dist/validator.js" minified "0.10.2/dist/validator.min.js" dependsOn "bootstrap.js",
      ProvidedJS / "wavesurfer.js",
      ProvidedJS / "wavesurfer.spectrogram.js" dependsOn "wavesurfer.js",
      ProvidedJS / "wavesurfer.timeline.js" dependsOn "wavesurfer.js",
      ProvidedJS / "leaflet.js"
    ),
    relativeSourceMaps := true,
    skip in packageJSDependencies := false,
    artifactPath in (Compile, fastOptJS) := file("artifacts/desktop/js") / "lingvodoc.js",
    artifactPath in (Compile, fullOptJS) := file("artifacts/desktop/js") / "lingvodoc.js",
    artifactPath in (Compile, packageJSDependencies) := file("artifacts/desktop/js") / "lingvodoc-deps.js"
  )

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
      js.jquery / "2.2.1/jquery.js" minified "2.2.1/jquery.min.js",
      js.angularjs / "angular.js" minified "angular.min.js",
      js.angularjs / "angular-route.js" minified "angular-route.min.js" dependsOn "angular.js",
      js.angularjs / "angular-animate.js" minified "angular-animate.min.js" dependsOn "angular.js",
      js.bootstrap / "bootstrap.js" minified "bootstrap.min.js" dependsOn "2.2.1/jquery.js",
      js.bootstrapUI / "ui-bootstrap.js" minified "ui-bootstrap.min.js" dependsOn "bootstrap.js",
      js.bootstrapUITpls / "ui-bootstrap-tpls.js" minified "ui-bootstrap-tpls.min.js" dependsOn "ui-bootstrap.js",
      js.validator / "0.10.2/dist/validator.js" minified "0.10.2/dist/validator.min.js" dependsOn "bootstrap.js",
      ProvidedJS / "wavesurfer.js",
      ProvidedJS / "wavesurfer.spectrogram.js" dependsOn "wavesurfer.js",
      ProvidedJS / "wavesurfer.timeline.js" dependsOn "wavesurfer.js",
      ProvidedJS / "leaflet.js"
    )
  )
