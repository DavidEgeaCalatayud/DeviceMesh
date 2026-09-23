pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement { repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); repositories { google(); mavenCentral() } }
rootProject.name = "DeviceMeshAndroid"
include(":app", ":core:model", ":core:network", ":core:database", ":core:designsystem", ":domain", ":data", ":feature:dashboard", ":feature:devices", ":feature:alerts", ":feature:diagnostics", ":feature:settings")
