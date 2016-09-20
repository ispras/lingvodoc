enablePlugins(ScalaJSPlugin)

name := "lingvodoc2 frontend"

scalaVersion := "2.11.8"
scalacOptions += "-deprecation"

resolvers += "Sonatype OSS Snapshots" at "https://oss.sonatype.org/content/repositories/snapshots"

libraryDependencies += "org.scala-js" %%% "scalajs-dom" % "0.9.1"
libraryDependencies += "com.lihaoyi" %%% "upickle" % "0.3.9"
libraryDependencies += "com.greencatsoft" %%% "scalajs-angular" % "0.8-SNAPSHOT"
libraryDependencies += "io.surfkit" %%% "scalajs-google-maps" % "0.1-SNAPSHOT"
libraryDependencies += "org.scala-lang.modules" % "scala-xml_2.11" % "1.0.5"
libraryDependencies += "be.doeraene" %%% "scalajs-jquery" % "0.9.0" // jquery facade, used for xml parsing
libraryDependencies += "org.singlespaced" %%% "scalajs-d3" % "0.3.3" // d3 facade, used for eaf editing


libraryDependencies += "org.webjars" % "jquery" % "2.2.1"
libraryDependencies += "org.webjars" % "angularjs" % "1.5.8"
libraryDependencies += "org.webjars" % "bootstrap" % "3.3.6"

libraryDependencies += "org.webjars" % "angular-ui-bootstrap" % "1.3.3"
libraryDependencies += "org.webjars.bower" % "bootstrap-validator" % "0.10.2"

jsDependencies += "org.webjars" % "jquery" % "2.2.1" / "2.2.1/jquery.js"
jsDependencies += "org.webjars" % "angularjs" % "1.5.8" / "angular.js" dependsOn "2.2.1/jquery.js"
jsDependencies += "org.webjars" % "angularjs" % "1.5.8" / "angular-route.js" dependsOn "angular.js"
jsDependencies += "org.webjars" % "angularjs" % "1.5.8" / "angular-animate.js" dependsOn "angular.js"

jsDependencies += "org.webjars" % "bootstrap" % "3.3.6" / "bootstrap.js" dependsOn "angular.js"



jsDependencies += "org.webjars" % "angular-ui-bootstrap" % "1.3.3" / "ui-bootstrap.js" dependsOn "bootstrap.js"
jsDependencies += "org.webjars" % "angular-ui-bootstrap" % "1.3.3" / "ui-bootstrap-tpls.js" dependsOn "ui-bootstrap.js"

jsDependencies += "org.webjars.bower" % "bootstrap-validator" % "0.10.2"  / "0.10.2/dist/validator.js" dependsOn "bootstrap.js"


// Wavesurfer is not in webjars yet; perhaps we should create it ourselves
jsDependencies += ProvidedJS / "wavesurfer.min.js"

jsDependencies += ProvidedJS / "wavesurfer.spectrogram.js" dependsOn "wavesurfer.min.js"

// library for context menus, https://github.com/Templarian/ui.bootstrap.contextMenu. WARN: we have modified it.
jsDependencies += ProvidedJS / "contextMenu.js"
