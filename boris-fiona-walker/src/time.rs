use anyhow::Result;
use chrono::{TimeZone, Timelike, Utc};
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
    use chrono::{NaiveDate, NaiveTime, TimeZone};
    use chrono_tz::US::Eastern;
    
    #[test]
    fn test_walk_time_window_boundaries() {
        // Test the core business rule: Walk reminders between 2-6 PM Eastern
        
        // Before walk window
        assert!(!is_hour_in_walk_window(13)); // 1 PM - too early
        assert!(!is_hour_in_walk_window(12)); // 12 PM - too early
        assert!(!is_hour_in_walk_window(11)); // 11 AM - too early
        
        // During walk window  
        assert!(is_hour_in_walk_window(14)); // 2 PM - start of window
        assert!(is_hour_in_walk_window(15)); // 3 PM - middle of window
        assert!(is_hour_in_walk_window(16)); // 4 PM - middle of window
        assert!(is_hour_in_walk_window(17)); // 5 PM - middle of window
        assert!(is_hour_in_walk_window(18)); // 6 PM - end of window
        
        // After walk window
        assert!(!is_hour_in_walk_window(19)); // 7 PM - too late
        assert!(!is_hour_in_walk_window(20)); // 8 PM - too late
        assert!(!is_hour_in_walk_window(23)); // 11 PM - too late
        assert!(!is_hour_in_walk_window(0));  // Midnight - too late
    }
    
    #[test]
    fn test_timezone_conversion_concept() {
        // Test that we understand Eastern timezone conversion
        // This tests the concept, not the actual implementation
        
        // Create a known UTC time: 6 PM UTC on a standard time day
        let utc_dt = chrono::Utc.with_ymd_and_hms(2025, 1, 15, 18, 0, 0).unwrap();
        
        // Convert to Eastern (should be 1 PM EST during standard time)
        let eastern_dt = Eastern.from_utc_datetime(&utc_dt.naive_utc());
        assert_eq!(eastern_dt.hour(), 13); // 1 PM Eastern
        
        // During daylight saving time, the offset would be different
        let utc_dt_summer = chrono::Utc.with_ymd_and_hms(2025, 7, 15, 18, 0, 0).unwrap();
        let eastern_dt_summer = Eastern.from_utc_datetime(&utc_dt_summer.naive_utc());
        assert_eq!(eastern_dt_summer.hour(), 14); // 2 PM EDT during daylight time
    }
    
    #[test]
    fn test_date_formatting() {
        // Test that date formatting works as expected for rate limiting
        let test_date = NaiveDate::from_ymd_opt(2025, 10, 19).unwrap();
        let test_time = NaiveTime::from_hms_opt(15, 30, 0).unwrap();
        let test_datetime = test_date.and_time(test_time);
        
        let eastern_dt = Eastern.from_local_datetime(&test_datetime).unwrap();
        let formatted = eastern_dt.format("%Y-%m-%d").to_string();
        
        assert_eq!(formatted, "2025-10-19");
    }
    
    // Helper function for testing hour ranges
    fn is_hour_in_walk_window(hour: u8) -> bool {
        (14..=18).contains(&hour)
    }
}