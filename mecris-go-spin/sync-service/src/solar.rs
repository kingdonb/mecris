//! Sunrise, sunset and darkness from latitude and longitude (#188), with the NOAA
//! solar calculator equations (Meeus, as in NOAA's General Solar Position spreadsheet).
//! Pure: no API key and no outbound call. Accurate to about a minute at mid latitudes.

use chrono::{DateTime, NaiveDate, Utc};

/// The phone's default location (DelayedNagWorker.fetchWeatherOracle): New York.
pub const DEFAULT_LAT: f64 = 40.7128;
pub const DEFAULT_LON: f64 = -74.0060;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SolarDay {
    /// Unix seconds.
    pub sunrise: i64,
    /// Unix seconds.
    pub sunset: i64,
    pub is_dark: bool,
}

/// The request's lat/lon when both parse as finite, in-range degrees; otherwise the
/// phone's default (both, never one of each).
pub fn coords_or_default(_lat: Option<&str>, _lon: Option<&str>) -> (f64, f64) {
    (0.0, 0.0)
}

/// Sunrise and sunset (Unix seconds) on `date` at lat/lon (east positive). None when the
/// sun neither rises nor sets that day.
pub fn sun_times(_date: NaiveDate, _lat: f64, _lon: f64) -> Option<(i64, i64)> {
    None
}

/// The solar day containing `now` at lat/lon, and whether it is dark now (before
/// sunrise or from sunset on). The day is the local mean solar date, so it needs no
/// time zone.
pub fn solar_day(_now: DateTime<Utc>, _lat: f64, _lon: f64) -> SolarDay {
    SolarDay { sunrise: 0, sunset: 0, is_dark: false }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn at(s: &str) -> DateTime<Utc> { DateTime::parse_from_rfc3339(s).unwrap().with_timezone(&Utc) }
    fn day(y: i32, m: u32, d: u32) -> NaiveDate { NaiveDate::from_ymd_opt(y, m, d).unwrap() }

    /// NOAA solar calculator, New York (40.7128 N, 74.0060 W), times in UTC.
    const NOAA_NEW_YORK: [((i32, u32, u32), &str, &str); 3] = [
        ((2026, 6, 21), "2026-06-21T09:25:00Z", "2026-06-22T00:31:00Z"),   // 05:25 / 20:31 EDT
        ((2026, 11, 14), "2026-11-14T11:42:00Z", "2026-11-14T21:38:00Z"),  // 06:42 / 16:38 EST
        ((2026, 12, 21), "2026-12-21T12:17:00Z", "2026-12-21T21:32:00Z"),  // 07:17 / 16:32 EST
    ];

    #[test]
    fn new_york_sun_times_match_noaa_within_three_minutes() {
        for ((y, m, d), rise, set) in NOAA_NEW_YORK {
            let (r, s) = sun_times(day(y, m, d), DEFAULT_LAT, DEFAULT_LON).expect("the sun rises in New York");
            let (want_r, want_s) = (at(rise).timestamp(), at(set).timestamp());
            assert!((r - want_r).abs() <= 180, "{y}-{m}-{d} sunrise off by {} s", r - want_r);
            assert!((s - want_s).abs() <= 180, "{y}-{m}-{d} sunset off by {} s", s - want_s);
        }
    }

    #[test]
    fn dark_at_17_30_est_light_at_noon_on_2026_11_14() {
        let evening = solar_day(at("2026-11-14T22:30:00Z"), DEFAULT_LAT, DEFAULT_LON);
        assert!(evening.is_dark, "17:30 EST is after the 16:38 sunset");
        let noon = solar_day(at("2026-11-14T17:00:00Z"), DEFAULT_LAT, DEFAULT_LON);
        assert!(!noon.is_dark, "12:00 EST is daylight");
        // Both readings describe the same day's sun.
        assert_eq!((evening.sunrise, evening.sunset), (noon.sunrise, noon.sunset));
        assert!(noon.sunrise < at("2026-11-14T17:00:00Z").timestamp() && at("2026-11-14T17:00:00Z").timestamp() < noon.sunset);
    }

    #[test]
    fn small_hours_are_dark_and_belong_to_the_coming_day() {
        // 01:00 EST on 2026-11-15: before that day's sunrise.
        let s = solar_day(at("2026-11-15T06:00:00Z"), DEFAULT_LAT, DEFAULT_LON);
        assert!(s.is_dark);
        assert!(s.sunrise > at("2026-11-15T06:00:00Z").timestamp());
    }

    #[test]
    fn sunset_itself_is_dark() {
        let (_, set) = sun_times(day(2026, 11, 14), DEFAULT_LAT, DEFAULT_LON).unwrap();
        let t = DateTime::from_timestamp(set, 0).unwrap();
        assert!(solar_day(t, DEFAULT_LAT, DEFAULT_LON).is_dark);
        let before = DateTime::from_timestamp(set - 60, 0).unwrap();
        assert!(!solar_day(before, DEFAULT_LAT, DEFAULT_LON).is_dark);
    }

    #[test]
    fn other_places_use_their_own_sun() {
        // 2026-11-14 22:30 UTC: dark in New York, daylight in Honolulu (12:30 HST).
        let honolulu = solar_day(at("2026-11-14T22:30:00Z"), 21.3069, -157.8583);
        assert!(!honolulu.is_dark);
        // Sydney at the same instant is 09:30 the next morning: light.
        let sydney = solar_day(at("2026-11-14T22:30:00Z"), -33.8688, 151.2093);
        assert!(!sydney.is_dark);
        // London at the same instant is 22:30: dark.
        let london = solar_day(at("2026-11-14T22:30:00Z"), 51.5074, -0.1278);
        assert!(london.is_dark);
    }

    #[test]
    fn polar_night_is_dark_and_midnight_sun_is_not() {
        // Tromso in December never sees the sun rise; in June it never sets.
        assert_eq!(sun_times(day(2026, 12, 21), 69.6492, 18.9553), None);
        assert!(solar_day(at("2026-12-21T11:00:00Z"), 69.6492, 18.9553).is_dark);
        assert_eq!(sun_times(day(2026, 6, 21), 69.6492, 18.9553), None);
        assert!(!solar_day(at("2026-06-21T23:00:00Z"), 69.6492, 18.9553).is_dark);
    }

    #[test]
    fn missing_or_invalid_coordinates_fall_back_to_new_york() {
        let ny = (DEFAULT_LAT, DEFAULT_LON);
        assert_eq!(coords_or_default(None, None), ny);
        assert_eq!(coords_or_default(Some("51.5"), None), ny, "one coordinate is not a place");
        assert_eq!(coords_or_default(None, Some("-0.1")), ny);
        assert_eq!(coords_or_default(Some("abc"), Some("-0.1")), ny);
        assert_eq!(coords_or_default(Some("NaN"), Some("-0.1")), ny);
        assert_eq!(coords_or_default(Some("inf"), Some("-0.1")), ny);
        assert_eq!(coords_or_default(Some("91"), Some("0")), ny);
        assert_eq!(coords_or_default(Some("0"), Some("180.5")), ny);
        assert_eq!(coords_or_default(Some(""), Some("")), ny);
        assert_eq!(coords_or_default(Some("51.5074"), Some("-0.1278")), (51.5074, -0.1278));
        assert_eq!(coords_or_default(Some(" -33.8688 "), Some("151.2093")), (-33.8688, 151.2093));
    }
}
