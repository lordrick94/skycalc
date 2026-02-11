# SkyCalc Architecture

This document describes the structure and purpose of each file in the SkyCalc project.

## Project Structure

```
skycalc/
├── docs/
│   ├── tutorial.md          # User guide and tutorial
│   └── architecture.md      # This file
├── examples/
│   ├── sample_targets.csv   # Example target list
│   └── test_frb_targets.csv # FRB targets for testing
├── skycalc/
│   ├── __init__.py          # Package initialization
│   ├── run.py               # CLI entry point
│   ├── config/
│   │   └── telescopes.yaml  # Telescope configurations
│   ├── core/
│   │   ├── __init__.py
│   │   ├── calculations.py  # Astronomical calculations
│   │   ├── targets.py       # Target parsing
│   │   └── telescope.py     # Telescope configuration
│   └── gui/
│       ├── __init__.py
│       ├── app.py           # Dash application layout
│       ├── callbacks.py     # Interactive callbacks
│       └── components.py    # Reusable UI components
├── pyproject.toml           # Project configuration
└── .gitignore
```

## File Descriptions

### Root Files

#### `pyproject.toml`
Project metadata and dependencies for pip installation. Defines:
- Package name, version, description
- Python version requirement (>=3.10)
- Dependencies: astropy, astroplan, dash, plotly, pandas, pyyaml, pytz
- CLI entry point: `skycalc` command

#### `.gitignore`
Standard Python gitignore excluding `__pycache__`, virtual environments, IDE files, etc.

---

### `skycalc/` - Main Package

#### `__init__.py`
Package initialization. Exports the version number.

#### `run.py`
Command-line interface entry point. Handles:
- Argument parsing (`--port`, `--no-browser`, `--debug`)
- Starting the Dash server
- Opening the browser (unless `--no-browser`)

---

### `skycalc/config/` - Configuration

#### `telescopes.yaml`
YAML configuration file defining telescope sites. Each telescope entry includes:
- `name`: Display name
- `latitude`, `longitude`: Location in degrees
- `elevation`: Altitude in meters
- `timezone`: pytz timezone string
- `description`: Optional description
- `limits`: Pointing constraints
  - `min_altitude`, `max_altitude`: Altitude limits in degrees
  - `min_hour_angle`, `max_hour_angle`: Hour angle limits in hours

**Included telescopes**: Keck, Gemini North, Gemini South, VLT, Subaru, Lick

---

### `skycalc/core/` - Core Calculations

#### `calculations.py`
Astronomical calculations using Astropy/Astroplan:

- **`compute_airmass_curve()`**: Calculate airmass, altitude, azimuth, and hour angle for a target over a time range. Uses Pickering (2002) formula for accurate airmass near the horizon.

- **`compute_airmass()`**: Convert altitude to airmass using Pickering (2002) formula: `X = 1 / sin(h + 244/(165 + 47*h^1.1))`

- **`compute_twilight_times()`**: Calculate sunset, sunrise, and twilight times (civil -6°, nautical -12°, astronomical -18°). Returns times in **local timezone**.

- **`compute_moon_info()`**: Calculate Moon altitude, azimuth, and illumination fraction over a time range.

- **`get_night_time_range()`**: Get start/end times for a night based on twilight type.

- **`check_pointing_limits()`**: Determine which times a target is within telescope pointing constraints.

#### `targets.py`
Target list parsing with flexible CSV handling:

- **`Target`** dataclass: Stores target name, coordinates (SkyCoord), priority, magnitude, type, notes, and extra metadata.

- **`load_targets()`**: Parse CSV file with automatic column detection. Supports:
  - Column aliases (ra/right_ascension/alpha, dec/declination/delta, etc.)
  - Sexagesimal coordinates (`HH:MM:SS.s`, `DD:MM:SS.s`)
  - Decimal degrees
  - Comment lines starting with `#`

- **`parse_coordinate()`**: Parse coordinate strings in various formats.

- **`targets_to_dataframe()`**: Convert target list to pandas DataFrame for display.

#### `telescope.py`
Telescope configuration handling:

- **`TelescopeConfig`** dataclass: Stores telescope properties including location (EarthLocation), timezone, pointing limits, and creates an Astroplan Observer.

- **`load_telescope_config()`**: Load telescope from YAML file.

- **`load_default_telescopes()`**: Load all telescopes from the default config file.

---

### `skycalc/gui/` - Web Interface

#### `app.py`
Dash application layout definition:

- Initializes Dash app with Bootstrap DARKLY theme
- Defines the sidebar layout:
  - Telescope dropdown
  - Date picker (HTML5 date input)
  - Start time input (HTML5 time input)
  - CSV file upload
  - Target checklist
  - Display options
  - Airmass limit slider
- Defines main content area with plot and target table
- Creates `dcc.Store` for target data persistence

#### `callbacks.py`
Interactive callbacks that respond to user input:

- **`parse_uploaded_file()`**: Process uploaded CSV, parse targets, update checklist options.

- **`update_telescope_info()`**: Display telescope location and pointing limits.

- **`update_airmass_plot()`**: Main plotting callback. Generates the airmass figure with:
  - Target airmass curves (solid when observable, dotted when outside limits)
  - Twilight lines with annotations
  - Pointing limit indicators
  - Moon curve (optional)
  - Current time line (optional)
  - UT/LST axes at top

- **`update_target_table()`**: Generate summary table with observability metrics.

- **Helper functions**:
  - `_add_twilight_bands()`: Add twilight vertical lines and annotations
  - `_add_limit_shading()`: Add pointing limit indicators
  - `_add_ut_lst_axes()`: Add UT and LST time axes at plot top

#### `components.py`
Reusable UI components (currently minimal, available for future expansion).

---

### `examples/` - Example Data

#### `sample_targets.csv`
Basic example with common astronomical targets (M31, M13, Vega, etc.).

#### `test_frb_targets.csv`
FRB (Fast Radio Burst) targets for testing, includes magnitude, type, and notes columns.

---

## Data Flow

1. **Startup**: `run.py` initializes the Dash app, loads telescope configs from YAML
2. **User uploads CSV**: `parse_uploaded_file()` callback parses targets, stores in `dcc.Store`
3. **User changes settings**: `update_airmass_plot()` callback regenerates the figure
4. **Calculations**: Core functions compute airmass curves, check pointing limits
5. **Display**: Plotly figure rendered in browser with interactive hover

## Key Dependencies

- **Astropy**: Coordinate transformations, time handling, units
- **Astroplan**: Observer class, twilight calculations, target visibility
- **Dash**: Web application framework
- **Plotly**: Interactive plotting
- **Pandas**: Data manipulation
- **PyYAML**: Configuration file parsing
- **pytz**: Timezone handling
