package com.mecris.go

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.mecris.go.sync.LanguageStatDto
import com.mecris.go.ui.theme.MecrisTheme
import org.junit.Rule
import org.junit.Test

class ReviewPumpUiTest {

    @get:Rule
    val composeTestRule = createComposeRule()

    @Test
    fun reviewPump_changingLever_updatesTargetFlowRate() {
        // GIVEN: A Review Pump for Arabic with 700 debt and 50 tomorrow liability
        val initialStat = LanguageStatDto(
            name = "ARABIC",
            current = 700,
            tomorrow = 50,
            next_7_days = 200,
            daily_rate = 10.0,
            safebuf = 2,
            derail_risk = "CAUTION",
            pump_multiplier = 1.0 // Maintenance
        )

        composeTestRule.setContent {
            MecrisTheme {
                // We test the widget logic
                ReviewPumpWidget(
                    stat = initialStat,
                    onMultiplierChange = { _, _ -> }
                )
            }
        }

        // 1x target should be just tomorrow's liability (50)
        composeTestRule.onNodeWithText("50").assertIsDisplayed()

        // WHEN: We click the "4x" lever (Aggressive / 7 days)
        // Note: The UI currently renders "4x" text inside the boxes
        composeTestRule.onNodeWithText("4x").performClick()

        // THEN: The Target Flow should update to 150 (50 + 700/7)
        // And it should be visually distinct (this is what we're going to fix)
        composeTestRule.onNodeWithText("150").assertIsDisplayed()
    }
}
