#![no_std]

use core::panic::PanicInfo;

// Known New Moon: 2000-01-06 18:14:00 UTC
const KNOWN_NEW_MOON_UNIX: f64 = 947182440.0;
const SYNODIC_MONTH_DAYS: f64 = 29.53058770576;
const SYNODIC_MONTH_SECONDS: f64 = SYNODIC_MONTH_DAYS * 24.0 * 60.0 * 60.0;

// Shared buffer for returning the phase name
static mut RESULT_BUFFER: [u8; 128] = [0; 128];

#[no_mangle]
pub extern "C" fn calculate_moon_phase(timestamp: f64) -> *const u8 {
    let diff_seconds = timestamp - KNOWN_NEW_MOON_UNIX;
    let cycles = diff_seconds / SYNODIC_MONTH_SECONDS;
    
    // Manual floor for positive cycles
    let cycle_position = cycles - (cycles as u64) as f64;

    let (phase_name, torment_multiplier) = if cycle_position < 0.03 || cycle_position > 0.97 {
        ("New Moon", 1.0)
    } else if cycle_position < 0.22 {
        ("Waxing Crescent", 1.2)
    } else if cycle_position < 0.28 {
        ("First Quarter", 1.5)
    } else if cycle_position < 0.47 {
        ("Waxing Gibbous", 1.8)
    } else if cycle_position < 0.53 {
        ("Full Moon", 3.0)
    } else if cycle_position < 0.72 {
        ("Waning Gibbous", 1.8)
    } else if cycle_position < 0.78 {
        ("Last Quarter", 1.5)
    } else {
        ("Waning Crescent", 1.2)
    };

    // Linear approximation of illumination (0.0 to 1.0)
    let dist_from_center = 2.0 * cycle_position - 1.0;
    let abs_dist = if dist_from_center < 0.0 { -dist_from_center } else { dist_from_center };
    let illumination = 1.0 - abs_dist;

    unsafe {
        // Construct a simple JSON-like string manually to avoid dependencies
        let mut pos = 0;
        write_str(&mut pos, "{\"phase_name\": \"");
        write_str(&mut pos, phase_name);
        write_str(&mut pos, "\", \"torment_multiplier\": ");
        write_float(&mut pos, torment_multiplier);
        write_str(&mut pos, ", \"illumination\": ");
        write_float(&mut pos, illumination);
        write_str(&mut pos, "}");
        RESULT_BUFFER[pos] = 0; // Null terminator
        RESULT_BUFFER.as_ptr()
    }
}

unsafe fn write_str(pos: &mut usize, s: &str) {
    for b in s.as_bytes() {
        if *pos < 127 {
            RESULT_BUFFER[*pos] = *b;
            *pos += 1;
        }
    }
}

unsafe fn write_float(pos: &mut usize, f: f64) {
    let integer = f as u64;
    let fractional = ((f - integer as f64) * 10.0) as u64;
    
    if *pos < 127 {
        RESULT_BUFFER[*pos] = (integer as u8) + b'0';
        *pos += 1;
    }
    if *pos < 127 {
        RESULT_BUFFER[*pos] = b'.';
        *pos += 1;
    }
    if *pos < 127 {
        RESULT_BUFFER[*pos] = (fractional as u8) + b'0';
        *pos += 1;
    }
}

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {}
}
