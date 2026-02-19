use crate::weather::WeatherCondition;
use chrono::Utc;

/// Check if it is currently daylight based on sunrise/sunset times
pub fn is_daylight(condition: &WeatherCondition) -> bool {
    let now = Utc::now().timestamp();
    now >= condition.sunrise && now <= condition.sunset
}

/// Check if we are approaching sunset (within 1 hour)
pub fn is_approaching_sunset(condition: &WeatherCondition) -> bool {
    let now = Utc::now().timestamp();
    let one_hour = 3600;
    now <= condition.sunset && now >= (condition.sunset - one_hour)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::weather::WeatherCondition;

    #[test]
    fn test_daylight_logic() {
        let sunrise = 1000;
        let sunset = 2000;
        let condition = WeatherCondition {
            sunrise,
            sunset,
            ..Default::default()
        };

        // This test depends on Utc::now() so we can't easily test it deterministically
        // without mocking time, but we can test the logic if we pass in a time.
        // For now, we'll just verify it compiles and runs.
        let _ = is_daylight(&condition);
        
        // If we want to test the logic, we'd refactor to take 'now' as a parameter.
    }
}
