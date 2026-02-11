"""Target list loading and parsing."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd
from astropy import units as u
from astropy.coordinates import Angle, SkyCoord


@dataclass
class Target:
    """Astronomical target with coordinates and metadata."""

    name: str
    coord: SkyCoord
    priority: int = 1
    magnitude: Optional[float] = None
    target_type: Optional[str] = None
    notes: str = ""
    metadata: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        ra_str = self.coord.ra.to_string(unit=u.hour, sep=":", precision=2)
        dec_str = self.coord.dec.to_string(unit=u.deg, sep=":", precision=1)
        return f"Target({self.name!r}, RA={ra_str}, Dec={dec_str})"


# Column name aliases for auto-detection
COLUMN_ALIASES = {
    "name": ["name", "target", "object", "id", "source", "obj_name", "target_name"],
    "ra": ["ra", "right_ascension", "alpha", "ra_j2000", "raj2000", "ra_deg", "ra_hours"],
    "dec": ["dec", "declination", "delta", "dec_j2000", "decj2000", "dec_deg", "de"],
    "priority": ["priority", "pri", "prio", "rank"],
    "magnitude": ["magnitude", "mag", "vmag", "v_mag", "brightness"],
    "type": ["type", "target_type", "obj_type", "class", "classification"],
    "notes": ["notes", "comment", "comments", "remarks", "description"],
    "equinox": ["equinox", "epoch", "eq"],
}


def detect_columns(df: pd.DataFrame) -> dict:
    """
    Auto-detect column mappings from DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame

    Returns
    -------
    dict
        Mapping of standard names to actual column names
    """
    columns_lower = {col.lower().strip(): col for col in df.columns}
    mapping = {}

    for standard_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in columns_lower:
                mapping[standard_name] = columns_lower[alias]
                break

    return mapping


def parse_coordinate(coord_str: str, is_ra: bool = True) -> Angle:
    """
    Parse a coordinate string in various formats.

    Supported formats:
    - Sexagesimal with colons: "18:30:45.2" or "-45:30:15"
    - Sexagesimal with spaces: "18 30 45.2" or "-45 30 15"
    - Decimal degrees: "274.938" or "-45.504"
    - Decimal hours (RA only): "18.5125h" or "18.5125 h"

    Parameters
    ----------
    coord_str : str
        Coordinate string
    is_ra : bool
        True if this is a right ascension, False for declination

    Returns
    -------
    Angle
        Parsed angle
    """
    coord_str = str(coord_str).strip()

    # Check for explicit hours suffix (RA only)
    if is_ra and coord_str.lower().endswith("h"):
        value = float(coord_str[:-1].strip())
        return Angle(value, unit=u.hour)

    # Check for explicit degrees suffix
    if coord_str.lower().endswith("d"):
        value = float(coord_str[:-1].strip())
        return Angle(value, unit=u.deg)

    # Check if sexagesimal (contains : or multiple spaces indicating HMS/DMS)
    if ":" in coord_str:
        # Colon-separated: "18:30:45.2"
        unit = u.hour if is_ra else u.deg
        return Angle(coord_str, unit=unit)

    # Check for space-separated sexagesimal
    parts = coord_str.split()
    if len(parts) >= 2:
        # Space-separated: "18 30 45.2" or "-45 30 15"
        # Reconstruct with colons
        coord_reformatted = ":".join(parts)
        unit = u.hour if is_ra else u.deg
        return Angle(coord_reformatted, unit=unit)

    # Assume decimal
    value = float(coord_str)
    if is_ra:
        # For RA, assume decimal degrees if value > 24, else assume hours
        if abs(value) > 24:
            return Angle(value, unit=u.deg)
        else:
            # Ambiguous - assume degrees to be safe (most common in catalogs)
            return Angle(value, unit=u.deg)
    else:
        return Angle(value, unit=u.deg)


def load_targets(
    filepath: str | Path,
    ra_col: Optional[str] = None,
    dec_col: Optional[str] = None,
    name_col: Optional[str] = None,
) -> list[Target]:
    """
    Load targets from a CSV file.

    Parameters
    ----------
    filepath : str or Path
        Path to CSV file
    ra_col : str, optional
        Column name for RA (auto-detected if not provided)
    dec_col : str, optional
        Column name for Dec (auto-detected if not provided)
    name_col : str, optional
        Column name for target name (auto-detected if not provided)

    Returns
    -------
    list[Target]
        List of Target objects
    """
    filepath = Path(filepath)

    # Read CSV
    df = pd.read_csv(filepath, comment="#")

    # Auto-detect columns if not specified
    col_mapping = detect_columns(df)

    if ra_col is None:
        ra_col = col_mapping.get("ra")
    if dec_col is None:
        dec_col = col_mapping.get("dec")
    if name_col is None:
        name_col = col_mapping.get("name")

    # Validate required columns
    if ra_col is None or ra_col not in df.columns:
        raise ValueError(
            f"Could not find RA column. Available: {list(df.columns)}. "
            "Specify ra_col parameter or use standard column names."
        )
    if dec_col is None or dec_col not in df.columns:
        raise ValueError(
            f"Could not find Dec column. Available: {list(df.columns)}. "
            "Specify dec_col parameter or use standard column names."
        )

    # Get optional column mappings
    priority_col = col_mapping.get("priority")
    mag_col = col_mapping.get("magnitude")
    type_col = col_mapping.get("type")
    notes_col = col_mapping.get("notes")
    equinox_col = col_mapping.get("equinox")

    targets = []
    for idx, row in df.iterrows():
        # Parse coordinates
        try:
            ra = parse_coordinate(row[ra_col], is_ra=True)
            dec = parse_coordinate(row[dec_col], is_ra=False)
        except Exception as e:
            print(f"Warning: Skipping row {idx} due to coordinate parsing error: {e}")
            continue

        # Get equinox if available
        equinox = "J2000"
        if equinox_col and equinox_col in df.columns:
            eq_val = row[equinox_col]
            if pd.notna(eq_val):
                equinox = f"J{eq_val}" if not str(eq_val).startswith(("J", "B")) else str(eq_val)

        # Create SkyCoord
        coord = SkyCoord(ra=ra, dec=dec, frame="icrs")

        # Get target name
        if name_col and name_col in df.columns:
            name = str(row[name_col])
        else:
            name = f"Target_{idx + 1}"

        # Get optional fields
        priority = 1
        if priority_col and priority_col in df.columns and pd.notna(row[priority_col]):
            try:
                priority = int(row[priority_col])
            except (ValueError, TypeError):
                pass

        magnitude = None
        if mag_col and mag_col in df.columns and pd.notna(row[mag_col]):
            try:
                magnitude = float(row[mag_col])
            except (ValueError, TypeError):
                pass

        target_type = None
        if type_col and type_col in df.columns and pd.notna(row[type_col]):
            target_type = str(row[type_col])

        notes = ""
        if notes_col and notes_col in df.columns and pd.notna(row[notes_col]):
            notes = str(row[notes_col])

        # Collect remaining columns as metadata
        known_cols = {ra_col, dec_col, name_col, priority_col, mag_col, type_col, notes_col, equinox_col}
        known_cols = {c for c in known_cols if c is not None}
        metadata = {
            col: row[col]
            for col in df.columns
            if col not in known_cols and pd.notna(row[col])
        }

        target = Target(
            name=name,
            coord=coord,
            priority=priority,
            magnitude=magnitude,
            target_type=target_type,
            notes=notes,
            metadata=metadata,
        )
        targets.append(target)

    return targets


def targets_to_dataframe(targets: list[Target]) -> pd.DataFrame:
    """
    Convert list of targets to a DataFrame for display.

    Parameters
    ----------
    targets : list[Target]
        List of Target objects

    Returns
    -------
    pd.DataFrame
        DataFrame with target information
    """
    data = []
    for t in targets:
        row = {
            "Name": t.name,
            "RA": t.coord.ra.to_string(unit=u.hour, sep=":", precision=2),
            "Dec": t.coord.dec.to_string(unit=u.deg, sep=":", precision=1, alwayssign=True),
            "Priority": t.priority,
        }
        if t.magnitude is not None:
            row["Mag"] = f"{t.magnitude:.1f}"
        if t.target_type:
            row["Type"] = t.target_type
        data.append(row)

    return pd.DataFrame(data)
