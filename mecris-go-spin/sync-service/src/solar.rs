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
pub fn coords_or_default(lat: Option<&str>, lon: Option<&str>) -> (f64, f64) {
    let parse = |s: Option<&str>, limit: f64| s.and_then(|v| v.trim().parse::<f64>().ok()).filter(|v| v.is_finite() && v.abs() <= limit);
    match (parse(lat, 90.0), parse(lon, 180.0)) {
        (Some(la), Some(lo)) => (la, lo),
        _ => (DEFAULT_LAT, DEFAULT_LON),
    }
}

/// Zenith of sunrise and sunset: 90 degrees plus refraction and the sun's radius.
const ZENITH_DEG: f64 = 90.833;

enum Sun {
    /// Minutes after 00:00 UTC on the date (may fall outside 0..1440).
    RiseSet(f64, f64),
    /// The sun stays below the horizon all day; minutes of solar noon.
    PolarNight(f64),
    /// The sun stays above the horizon all day; minutes of solar noon.
    MidnightSun(f64),
}

fn julian_century(jd: f64) -> f64 { (jd - 2451545.0) / 36525.0 }

/// (equation of time in minutes, declination in degrees) at Julian century `t`.
fn eq_time_and_declination(t: f64) -> (f64, f64) {
    let l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)).rem_euclid(360.0);
    let m = 357.52911 + t * (35999.05029 - 0.0001537 * t);
    let e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t);
    let mr = m.to_radians();
    let c = mr.sin() * (1.914602 - t * (0.004817 + 0.000014 * t)) + (2.0 * mr).sin() * (0.019993 - 0.000101 * t) + (3.0 * mr).sin() * 0.000289;
    let omega = (125.04 - 1934.136 * t).to_radians();
    let lambda = (l0 + c - 0.00569 - 0.00478 * omega.sin()).to_radians();
    let seconds = 21.448 - t * (46.8150 + t * (0.00059 - t * 0.001813));
    let eps0 = 23.0 + (26.0 + seconds / 60.0) / 60.0;
    let eps = (eps0 + 0.00256 * omega.cos()).to_radians();
    let decl = (eps.sin() * lambda.sin()).asin().to_degrees();
    let y = (eps / 2.0).tan().powi(2);
    let l0r = l0.to_radians();
    let eq = y * (2.0 * l0r).sin() - 2.0 * e * mr.sin() + 4.0 * e * y * mr.sin() * (2.0 * l0r).cos()
        - 0.5 * y * y * (4.0 * l0r).sin() - 1.25 * e * e * (2.0 * mr).sin();
    (4.0 * eq.to_degrees(), decl)
}

/// NOAA calcSunriseSetUTC with the sun's position at Julian day `jd`: minutes after
/// 00:00 UTC of the date.
fn rise_or_set_minutes(jd: f64, lat: f64, lon: f64, rise: bool) -> Result<f64, Sun> {
    let (eq, decl) = eq_time_and_declination(julian_century(jd));
    let noon = 720.0 - 4.0 * lon - eq;
    let (latr, declr) = (lat.to_radians(), decl.to_radians());
    let cos_ha = ZENITH_DEG.to_radians().cos() / (latr.cos() * declr.cos()) - latr.tan() * declr.tan();
    if cos_ha > 1.0 { return Err(Sun::PolarNight(noon)); }
    if cos_ha < -1.0 { return Err(Sun::MidnightSun(noon)); }
    let ha = cos_ha.acos().to_degrees();
    Ok(if rise { noon - 4.0 * ha } else { noon + 4.0 * ha })
}

fn sun_minutes(date: NaiveDate, lat: f64, lon: f64) -> Sun {
    let midnight = date.and_hms_opt(0, 0, 0).expect("midnight").and_utc().timestamp() as f64;
    let jd0 = midnight / 86400.0 + 2440587.5;
    // NOAA refines each event by recomputing the sun's position at its first estimate.
    let event = |rise: bool| -> Result<f64, Sun> {
        let first = rise_or_set_minutes(jd0 + 0.5, lat, lon, rise)?;
        rise_or_set_minutes(jd0 + first / 1440.0, lat, lon, rise)
    };
    match (event(true), event(false)) {
        (Ok(r), Ok(s)) => Sun::RiseSet(r, s),
        (Err(e), _) | (_, Err(e)) => e,
    }
}

fn to_epoch(date: NaiveDate, minutes: f64) -> i64 {
    date.and_hms_opt(0, 0, 0).expect("midnight").and_utc().timestamp() + (minutes * 60.0).round() as i64
}

/// Sunrise and sunset (Unix seconds) on `date` at lat/lon (east positive). None when the
/// sun neither rises nor sets that day. The service uses solar_day; this checks the
/// NOAA golden times.
#[cfg(test)]
pub fn sun_times(date: NaiveDate, lat: f64, lon: f64) -> Option<(i64, i64)> {
    match sun_minutes(date, lat, lon) {
        Sun::RiseSet(r, s) => Some((to_epoch(date, r), to_epoch(date, s))),
        _ => None,
    }
}

/// The solar day containing `now` at lat/lon, and whether it is dark now (before
/// sunrise or from sunset on). The day is the local mean solar date, so it needs no
/// time zone.
pub fn solar_day(now: DateTime<Utc>, lat: f64, lon: f64) -> SolarDay {
    let local_mean = now + chrono::Duration::seconds((lon * 240.0).round() as i64);
    let date = local_mean.date_naive();
    let t = now.timestamp();
    match sun_minutes(date, lat, lon) {
        Sun::RiseSet(r, s) => {
            let (sunrise, sunset) = (to_epoch(date, r), to_epoch(date, s));
            SolarDay { sunrise, sunset, is_dark: t < sunrise || t >= sunset }
        }
        // No sunrise: report solar noon for both and call it dark all day.
        Sun::PolarNight(noon) => { let n = to_epoch(date, noon); SolarDay { sunrise: n, sunset: n, is_dark: true } }
        // No sunset: a 24-hour day centred on solar noon.
        Sun::MidnightSun(noon) => { let n = to_epoch(date, noon); SolarDay { sunrise: n - 43_200, sunset: n + 43_200, is_dark: false } }
    }
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
