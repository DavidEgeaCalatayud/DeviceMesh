package io.github.davidegeacalatayud.devicemesh

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class LoginUiTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun freshInstallShowsSecureLoginSurface() {
        composeRule.onNodeWithText("DeviceMesh").assertIsDisplayed()
        composeRule.onNodeWithText("Secure operator access").assertIsDisplayed()
        composeRule.onNodeWithText("HTTPS server").assertIsDisplayed()
        composeRule.onNodeWithText("Username").assertIsDisplayed()
        composeRule.onNodeWithText("Password").assertIsDisplayed()
        composeRule.onNodeWithText("Sign in").assertIsDisplayed()
    }
}
