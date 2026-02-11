"""Telescope configuration and pointing constraints."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from astropy import units as u
from astropy.coordinates import EarthLocation
from astroplan import Observer


@dataclass
class TelescopeConfig:
    """Configuration for a telescope including location and pointing limits."""

    name: str
    latitude: float  # degrees
    longitude: float  # degrees (negative for West)
    elevation: float  # meters
    timezone: str

    # Pointing limits
    min_altitude: Optional[float] = None  # degrees
    max_altitude: Optional[float] = 90.0  # degrees
    min_hour_angle: Optional[float] = None  # hours
    max_hour_angle: Optional[float] = None  # hours

    # Optional metadata
    description: str = ""
    slew_rate: Optional[float] = None  # deg/sec

    @property
    def location(self) -> EarthLocation:
        """Get Astropy EarthLocation for this telescope."""
        return EarthLocation(
            lat=self.latitude * u.deg,
            lon=self.longitude * u.deg,
            height=self.elevation * u.m,
        )

    @property
    def observer(self) -> Observer:
        """Get Astroplan Observer for this telescope."""
        return Observer(
            location=self.location,
            timezone=self.timezone,
            name=self.name,
        )

    def __repr__(self) -> str:
        return (
            f"TelescopeConfig({self.name!r}, "
            f"lat={self.latitude:.4f}, lon={self.longitude:.4f})"
        )


def load_telescope_config(filepath: str | Path) -> dict[str, TelescopeConfig]:
    """
    Load telescope configurations from a YAML file.

    Parameters
    ----------
    filepath : str or Path
        Path to YAML configuration file

    Returns
    -------
    dict[str, TelescopeConfig]
        Dictionary mapping telescope IDs to configurations
    """
    filepath = Path(filepath)

    with open(filepath) as f:
        data = yaml.safe_load(f)

    telescopes = {}
    for tel_id, tel_data in data.get("telescopes", {}).items():
        limits = tel_data.get("limits", {})

        config = TelescopeConfig(
            name=tel_data.get("name", tel_id),
            latitude=tel_data["latitude"],
            longitude=tel_data["longitude"],
            elevation=tel_data.get("elevation", 0),
            timezone=tel_data.get("timezone", "UTC"),
            min_altitude=limits.get("min_altitude"),
            max_altitude=limits.get("max_altitude", 90.0),
            min_hour_angle=limits.get("min_hour_angle"),
            max_hour_angle=limits.get("max_hour_angle"),
            description=tel_data.get("description", ""),
            slew_rate=tel_data.get("slew_rate"),
        )
        telescopes[tel_id] = config

    return telescopes


def get_default_config_path() -> Path:
    """Get path to the default telescope configuration file."""
    return Path(__file__).parent.parent / "config" / "telescopes.yaml"


def load_default_telescopes() -> dict[str, TelescopeConfig]:
    """Load the default telescope configurations shipped with the package."""
    config_path = get_default_config_path()
    if config_path.exists():
        return load_telescope_config(config_path)
    return {}


def create_custom_telescope(
    name: str,
    latitude: float,
    longitude: float,
    elevation: float = 0,
    timezone: str = "UTC",
    min_altitude: Optional[float] = None,
    max_altitude: Optional[float] = 90.0,
    min_hour_angle: Optional[float] = None,
    max_hour_angle: Optional[float] = None,
) -> TelescopeConfig:
    """
    Create a custom telescope configuration.

    Parameters
    ----------
    name : str
        Telescope name
    latitude : float
        Latitude in degrees (positive North)
    longitude : float
        Longitude in degrees (negative West)
    elevation : float
        Elevation in meters
    timezone : str
        Timezone name (e.g., "US/Hawaii", "UTC")
    min_altitude : float, optional
        Minimum observable altitude in degrees
    max_altitude : float, optional
        Maximum observable altitude in degrees
    min_hour_angle : float, optional
        Minimum hour angle in hours
    max_hour_angle : float, optional
        Maximum hour angle in hours

    Returns
    -------
    TelescopeConfig
        Custom telescope configuration
    """
    return TelescopeConfig(
        name=name,
        latitude=latitude,
        longitude=longitude,
        elevation=elevation,
        timezone=timezone,
        min_altitude=min_altitude,
        max_altitude=max_altitude,
        min_hour_angle=min_hour_angle,
        max_hour_angle=max_hour_angle,
    )
