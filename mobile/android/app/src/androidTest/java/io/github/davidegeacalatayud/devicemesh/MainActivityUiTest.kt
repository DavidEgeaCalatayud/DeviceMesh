package io.github.davidegeacalatayud.devicemesh

import androidx.compose.ui.test.assertExists
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
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
