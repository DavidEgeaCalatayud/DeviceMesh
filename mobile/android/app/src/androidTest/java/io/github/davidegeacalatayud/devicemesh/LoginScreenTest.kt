package io.github.davidegeacalatayud.devicemesh

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test

class LoginScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<MainActivity>()

    @Test
    fun loginSurfaceIsUsableBeforeAuthentication() {
        rule.onNodeWithText("DeviceMesh").assertIsDisplayed()
        rule.onNodeWithText("Secure operator access").assertIsDisplayed()
        rule.onNodeWithText("Username").assertIsDisplayed()
        rule.onNodeWithText("Password").assertIsDisplayed()
        rule.onNodeWithText("Sign in").assertIsDisplayed().assertIsNotEnabled()
    }
}
