use serde::Deserialize;
use anyhow::{anyhow, Result};
use spin_sdk::variables;

/// Weather condition summary
#[derive(Debug, Deserialize, Default, PartialEq, Clone)]
pub struct WeatherCondition {
    pub temperature: f64,
    pub description: String,
    pub is_raining: bool,
    pub is_snowing: bool,
    pub wind_speed: f64,
    pub sunrise: i64,
    pub sunset: i64,
}

/// OpenWeather API response structures
#[derive(Deserialize)]
struct OpenWeatherResponse {
    main: Main,
    weather: Vec<Weather>,
    wind: Wind,
    sys: Sys,
}

#[derive(Deserialize)]
struct Main {
    temp: f64,
}

#[derive(Deserialize)]
struct Weather {
    main: String,
    description: String,
}

#[derive(Deserialize)]
struct Wind {
    speed: f64,
}

#[derive(Deserialize)]
struct Sys {
    sunrise: i64,
    sunset: i64,
}

/// Get current weather for South Bend, IN (41.6764°N, 86.2520°W)
pub async fn get_current_weather() -> Result<WeatherCondition> {
    let api_key = variables::get("openweather_api_key")
        .map_err(|_| anyhow!("Missing openweather_api_key variable"))?;
    
    let lat = "41.6764";
    let lon = "-86.2520";
    let url = format!(
        "https://api.openweathermap.org/data/2.5/weather?lat={}&lon={}&appid={}&units=imperial",
        lat, lon, api_key
    );

    let request = spin_sdk::http::Request::builder()
        .method(spin_sdk::http::Method::Get)
        .uri(&url)
        .build();

    let response: spin_sdk::http::Response = spin_sdk::http::send(request).await?;

    if *response.status() >= 200 && *response.status() < 300 {
        let body = response.body();
        let ow_response: OpenWeatherResponse = serde_json::from_slice(body)?;
        
        let is_raining = ow_response.weather.iter().any(|w| w.main == "Rain" || w.main == "Drizzle");
        let is_snowing = ow_response.weather.iter().any(|w| w.main == "Snow");
        
        Ok(WeatherCondition {
            temperature: ow_response.main.temp,
            description: ow_response.weather.first().map(|w| w.description.clone()).unwrap_or_default(),
            is_raining,
            is_snowing,
            wind_speed: ow_response.wind.speed,
            sunrise: ow_response.sys.sunrise,
            sunset: ow_response.sys.sunset,
        })
    } else {
        let error_body = String::from_utf8_lossy(response.body());
        Err(anyhow!("OpenWeather API error {}: {}", response.status(), error_body))
    }
}

/// Check if the weather is safe for a walk
pub fn is_weather_safe(condition: &WeatherCondition) -> (bool, String) {
    if condition.is_raining {
        return (false, "It's raining. Maybe wait a bit? 🌧️".to_string());
    }
    
    if condition.temperature < 20.0 {
        return (false, format!("It's too cold ({}°F). ❄️", condition.temperature));
    }
    
    if condition.temperature > 95.0 {
        return (false, format!("It's too hot ({}°F). ☀️", condition.temperature));
    }
    
    if condition.wind_speed > 30.0 {
        return (false, "It's too windy! 💨".to_string());
    }
    
    (true, "Weather looks good!".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_weather_safe_logic() {
        let safe_condition = WeatherCondition {
            temperature: 70.0,
            description: "clear sky".to_string(),
            is_raining: false,
            is_snowing: false,
            wind_speed: 10.0,
            sunrise: 1000,
            sunset: 2000,
        };
        let (safe, _) = is_weather_safe(&safe_condition);
        assert!(safe);

        let rainy_condition = WeatherCondition {
            is_raining: true,
            ..safe_condition.clone()
        };
        let (safe, msg) = is_weather_safe(&rainy_condition);
        assert!(!safe);
        assert!(msg.contains("raining"));

        let freezing_condition = WeatherCondition {
            temperature: 10.0,
            ..safe_condition.clone()
        };
        let (safe, msg) = is_weather_safe(&freezing_condition);
        assert!(!safe);
        assert!(msg.contains("cold"));

        let windy_condition = WeatherCondition {
            wind_speed: 35.0,
            ..safe_condition.clone()
        };
        let (safe, msg) = is_weather_safe(&windy_condition);
        assert!(!safe);
        assert!(msg.contains("windy"));
    }
}
