# SkyCalc Tutorial

SkyCalc is an interactive airmass plotter for astronomical observation planning. This tutorial will guide you through using the application.

## Installation

```bash
# Install in your conda environment
pip install -e /path/to/skycalc

# Or install dependencies manually
pip install astropy astroplan dash plotly pandas pyyaml pytz
```

## Starting the Application

```bash
# Run with default settings (opens browser)
skycalc

# Run without opening browser
skycalc --no-browser

# Run on a specific port
skycalc --port 8080
```

The application will start a local web server, typically at `http://127.0.0.1:8050`.

## Using the Interface

### 1. Select a Telescope

Use the **Telescope** dropdown to select your observing site. Available telescopes include:
- Keck Observatory
- Gemini North/South
- VLT (Paranal)
- Subaru
- Lick Observatory (Shane 3m)

Each telescope has pre-configured:
- Location (latitude, longitude, elevation)
- Timezone
- Pointing limits (altitude and hour angle constraints)

### 2. Set the Observation Date and Time

- **Observation Date**: Select the date of your observation
- **Start Time**: Set the local time when you want the plot to begin (default: 6:00 PM)

The plot will display a 16-hour window starting 1 hour before your specified start time.

### 3. Upload Your Target List

Click the **Target List (CSV)** upload area to select your CSV file. The CSV should contain at minimum:
- `name`: Target name/identifier
- `ra`: Right Ascension (supports sexagesimal `HH:MM:SS.s` or decimal degrees)
- `dec`: Declination (supports sexagesimal `DD:MM:SS.s` or decimal degrees)

Optional columns:
- `magnitude`: Target brightness
- `type`: Target type (e.g., "FRB", "Galaxy", "Star")
- `priority`: Observation priority (integer)
- `notes`: Any additional notes

Example CSV:
```csv
name,ra,dec,magnitude,type,notes
FRB20230904A,20:31:34.00,+74:32:36.89,19.47,FRB,DM=147.79
M31,00:42:44.30,+41:16:09.0,3.4,Galaxy,Andromeda
Vega,18:36:56.34,+38:47:01.3,0.0,Star,Alpha Lyrae
```

### 4. Select Targets to Plot

After uploading, use the **Select Targets** checklist to choose which targets to display on the plot. All targets are selected by default.

### 5. Configure Display Options

- **Show twilight bands**: Display vertical lines for sunset, sunrise, -12° and -18° twilight
- **Show Moon altitude**: Plot the Moon's position through the night
- **Show pointing limits**: Shade regions where targets violate telescope pointing constraints
- **Show current time**: Display a vertical line at the current time (useful for tonight's observations)

### 6. Adjust Airmass Limit

Use the **Max Airmass Display** slider to set the y-axis range (2-10). Higher airmass values show targets closer to the horizon.

## Reading the Plot

### Axes
- **X-axis (bottom)**: Local time with 30-minute tick marks
- **Y-axis**: Airmass (1 at top = zenith, higher values = closer to horizon)
- **Top axes**: UT (cyan) and LST (orange) in 2-hour intervals

### Target Lines
- **Solid lines**: Target is within telescope pointing limits
- **Dotted lines**: Target is outside pointing limits (hover for details)

### Twilight Lines
- **Solid orange**: Sunset/Sunrise
- **Dashed purple**: -12° (nautical twilight)
- **Dotted blue**: -18° (astronomical twilight)

### Hover Information
Hover over any point on a target's curve to see:
- Time
- Airmass
- Altitude
- Azimuth
- Hour Angle
- Why target is outside limits (if applicable)

## Target Summary Table

Below the plot, a summary table shows:
- Target coordinates
- Priority
- Best (minimum) airmass during the night
- Total observable hours within pointing limits

## Tips

1. **Planning observations**: Look for times when your targets have low airmass (< 2) and are within pointing limits
2. **Moon avoidance**: Enable "Show Moon altitude" to plan around bright moon times
3. **Multiple targets**: Color-coded lines help distinguish between targets; click legend entries to show/hide individual targets
4. **Export**: Use the camera icon in the plot toolbar to save the plot as PNG

## Adding Custom Telescopes

Edit `skycalc/config/telescopes.yaml` to add your own telescope:

```yaml
my_telescope:
  name: "My Observatory"
  latitude: 34.0
  longitude: -118.0
  elevation: 100
  timezone: "US/Pacific"
  limits:
    min_altitude: 20.0
    max_altitude: 85.0
    min_hour_angle: -6.0  # hours
    max_hour_angle: 6.0
```
