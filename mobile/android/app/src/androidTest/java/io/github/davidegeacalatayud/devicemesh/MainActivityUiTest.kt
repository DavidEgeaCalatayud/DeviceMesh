package io.github.davidegeacalatayud.devicemesh

import android.content.Intent
import androidx.compose.ui.test.assertExists
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class MainActivityUiTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun unauthenticatedLaunchShowsSecureLoginSurface() {
        composeRule.onNodeWithText("DeviceMesh").assertExists()
        composeRule.onNodeWithText("Secure operator access").assertExists()
        composeRule.onNodeWithText("HTTPS server").assertExists()
        composeRule.onNodeWithText("Username").assertExists()
        composeRule.onNodeWithText("Password").assertExists()
        composeRule.onNodeWithText("MFA possession factor (if enabled)").assertExists()
        composeRule.onNodeWithText("Sign in").assertExists()
    }
}

@RunWith(AndroidJUnit4::class)
class AuthenticatedMainActivityUiTest {
    @get:Rule
    val composeRule = createEmptyComposeRule()

    @Test
    fun authenticatedLaunchNavigatesOperatorTabs() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val intent = Intent(context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            .putExtra("DeviceMeshUITestAuthenticated", true)

        ActivityScenario.launch<MainActivity>(intent).use {
            composeRule.waitUntil(timeoutMillis = 5_000) {
                composeRule.onAllNodesWithText("ui-test · administrator")
                    .fetchSemanticsNodes().isNotEmpty()
            }
            composeRule.onNodeWithText("Operational summary").assertExists()
            composeRule.onNodeWithText("Devices").performClick()
            composeRule.onNodeWithText("Devices").assertExists()
            composeRule.onNodeWithText("Incidents").performClick()
            composeRule.onNodeWithText("Incidents").assertExists()
            composeRule.onNodeWithText("Alerts").performClick()
            composeRule.onNodeWithText("Alerts").assertExists()
            composeRule.onNodeWithText("Synthetics").performClick()
            composeRule.onNodeWithText("Distributed probes").assertExists()
        }
    }
}
