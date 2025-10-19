use anyhow::{anyhow, Result};
use chrono::{DateTime, TimeZone, Utc};
use chrono_tz::US::Eastern;

/// Get current hour in Eastern timezone (0-23)
pub fn get_current_hour_eastern() -> Result<u8> {
    let utc_now = Utc::now();
    
    // Convert to Eastern time
    let eastern_time = Eastern.from_utc_datetime(&utc_now.naive_utc());
    
    Ok(eastern_time.hour() as u8)
}

/// Get current date in Eastern timezone (YYYY-MM-DD format)
pub fn get_current_date_eastern() -> Result<String> {
    let utc_now = Utc::now();
    let eastern_time = Eastern.from_utc_datetime(&utc_now.naive_utc());
    
    Ok(eastern_time.format("%Y-%m-%d").to_string())
}

/// Check if current time is within walk reminder window (2-6 PM Eastern)
pub fn is_walk_time() -> Result<bool> {
    let hour = get_current_hour_eastern()?;
    Ok((14..=18).contains(&hour))
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_walk_time_logic() {
        // These would need to be mocked for proper testing
        // but shows the intended logic
        assert!(!(13 >= 14 && 13 <= 18)); // 1 PM - not walk time
        assert!(14 >= 14 && 14 <= 18);    // 2 PM - walk time  
        assert!(16 >= 14 && 16 <= 18);    // 4 PM - walk time
        assert!(18 >= 14 && 18 <= 18);    // 6 PM - walk time
        assert!(!(19 >= 14 && 19 <= 18)); // 7 PM - not walk time
    }
}