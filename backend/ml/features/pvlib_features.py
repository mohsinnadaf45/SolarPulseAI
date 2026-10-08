"""
Solar position, irradiance decomposition, and physics-based feature extraction using pvlib.
"""

from typing import Optional
import numpy as np
import pandas as pd

from backend.ml.config import PlantConfig

try:
    import pvlib
    from pvlib import solarposition, atmosphere, clearsky, irradiance, temperature
    from pvlib.location import Location
    HAS_PVLIB = True
except ImportError:
    HAS_PVLIB = False


def _solar_position_fallback(times: pd.DatetimeIndex, latitude: float, longitude: float) -> pd.DataFrame:
    """
    Fallback solar position calculation using simplified astronomical formulas
    when pvlib is not installed in the environment.
    """
    day_of_year = times.dayofyear.values
    # Fractional year in radians
    gamma = 2.0 * np.pi / 365.0 * (day_of_year - 1)
    
    # Equation of time (minutes)
    eqtime = 229.18 * (0.000075 + 0.001868 * np.cos(gamma) - 0.032077 * np.sin(gamma)
                       - 0.014615 * np.cos(2 * gamma) - 0.040849 * np.sin(2 * gamma))
    
    # Solar declination angle (radians)
    decl = (0.006918 - 0.399912 * np.cos(gamma) + 0.070257 * np.sin(gamma)
            - 0.006758 * np.cos(2 * gamma) + 0.000907 * np.sin(2 * gamma))
    
    # Time offset in minutes
    # Assume times are UTC or local with utc offset
    if times.tz is not None:
        utc_hours = times.tz_convert("UTC").hour + times.tz_convert("UTC").minute / 60.0
    else:
        utc_hours = times.hour + times.minute / 60.0
    
    time_offset = eqtime + 4.0 * longitude
    tst = utc_hours * 60.0 + time_offset
    solar_time_hours = (tst / 4.0) % 360.0
    hour_angle = np.radians(solar_time_hours - 180.0)
    
    lat_rad = np.radians(latitude)
    zenith_rad = np.arccos(
        np.clip(
            np.sin(lat_rad) * np.sin(decl) + np.cos(lat_rad) * np.cos(decl) * np.cos(hour_angle),
            -1.0, 1.0
        )
    )
    zenith_deg = np.degrees(zenith_rad)
    elevation_deg = 90.0 - zenith_deg
    
    # Approximate azimuth
    cos_azimuth = np.clip(
        (np.sin(decl) - np.sin(lat_rad) * np.cos(zenith_rad)) /
        (np.cos(lat_rad) * np.sin(zenith_rad) + 1e-6),
        -1.0, 1.0
    )
    azimuth_deg = np.degrees(np.arccos(cos_azimuth))
    azimuth_deg = np.where(hour_angle > 0, 360.0 - azimuth_deg, azimuth_deg)
    
    return pd.DataFrame({
        "solar_zenith": zenith_deg,
        "solar_azimuth": azimuth_deg,
        "solar_elevation": elevation_deg
    }, index=times)


def compute_pvlib_features(df: pd.DataFrame, plant: PlantConfig) -> pd.DataFrame:
    """
    Computes physics-derived features using pvlib:
      - Solar zenith, azimuth, elevation
      - Relative airmass
      - Ineichen clear-sky irradiance (GHI, DNI, DHI)
      - Total Plane-of-Array (POA) irradiance (Global, Direct, Diffuse)
      - Cell temperature (Faiman model)
      - Clear-sky index

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame indexed by timezone-aware DatetimeIndex, containing weather/telemetry:
        Expected columns (or reasonable defaults):
          - 'ghi_nwp' or 'ghi'
          - 'dni_nwp' or 'dni' (optional, will be estimated if missing)
          - 'dhi_nwp' or 'dhi' (optional, will be estimated if missing)
          - 'temp_ambient_nwp' or 'temp_air' (optional, defaults to 25.0 °C)
          - 'wind_speed_nwp' or 'wind_speed' (optional, defaults to 1.5 m/s)
    plant : PlantConfig
        Plant configuration dataclass containing latitude, longitude, tilt, azimuth, etc.

    Returns
    -------
    pd.DataFrame
        DataFrame with computed physical feature columns.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a pandas DatetimeIndex.")
    
    times = df.index
    # Ensure timezone awareness (default to UTC if naive)
    if times.tz is None:
        times = times.tz_localize("UTC")
        df = df.copy()
        df.index = times

    # Extract input weather columns with fallback column names
    ghi = df["ghi_nwp"] if "ghi_nwp" in df.columns else df.get("ghi", pd.Series(0.0, index=times))
    ghi = ghi.fillna(0.0).clip(lower=0.0)

    temp_air = (
        df["temp_ambient_nwp"]
        if "temp_ambient_nwp" in df.columns
        else df.get("temp_air", pd.Series(25.0, index=times))
    ).fillna(25.0)

    wind_speed = (
        df["wind_speed_nwp"]
        if "wind_speed_nwp" in df.columns
        else df.get("wind_speed", pd.Series(1.5, index=times))
    ).fillna(1.5).clip(lower=0.0)

    if HAS_PVLIB:
        location = Location(
            latitude=plant.latitude,
            longitude=plant.longitude,
            altitude=plant.altitude,
            name=plant.name
        )

        # 1. Solar Position
        solpos = location.get_solarposition(times)
        solar_zenith = solpos["zenith"]
        solar_azimuth = solpos["azimuth"]
        solar_elevation = solpos["elevation"]

        # 2. Relative Air Mass
        airmass_relative = atmosphere.get_relative_airmass(solar_zenith)
        airmass_relative = airmass_relative.fillna(20.0).clip(lower=1.0, upper=25.0)

        # 3. Clear-sky Irradiance (Ineichen)
        cs = location.get_clearsky(times, model="ineichen")
        clearsky_ghi = cs["ghi"].clip(lower=0.0)
        clearsky_dni = cs["dni"].clip(lower=0.0)
        clearsky_dhi = cs["dhi"].clip(lower=0.0)

        # DNI / DHI handling (use provided or derive using Erbs model if missing)
        if "dni_nwp" in df.columns:
            dni = df["dni_nwp"].fillna(0.0).clip(lower=0.0)
        elif "dni" in df.columns:
            dni = df["dni"].fillna(0.0).clip(lower=0.0)
        else:
            # Estimate DNI and DHI from GHI via Erbs decomposition
            erbs_decomp = irradiance.erbs(ghi, solar_zenith, times)
            dni = erbs_decomp["dni"].fillna(0.0).clip(lower=0.0)

        if "dhi_nwp" in df.columns:
            dhi = df["dhi_nwp"].fillna(0.0).clip(lower=0.0)
        elif "dhi" in df.columns:
            dhi = df["dhi"].fillna(0.0).clip(lower=0.0)
        else:
            erbs_decomp = irradiance.erbs(ghi, solar_zenith, times)
            dhi = erbs_decomp["dhi"].fillna(0.0).clip(lower=0.0)

        # 4. Plane-of-Array (POA) Irradiance
        dni_extra = irradiance.get_extra_radiation(times)
        poa = irradiance.get_total_irradiance(
            surface_tilt=plant.tilt_deg,
            surface_azimuth=plant.azimuth_deg,
            solar_zenith=solar_zenith,
            solar_azimuth=solar_azimuth,
            dni=dni,
            ghi=ghi,
            dhi=dhi,
            dni_extra=dni_extra,
            airmass=airmass_relative,
            model="haydavies"
        )
        poa_global = poa["poa_global"].fillna(0.0).clip(lower=0.0)
        poa_direct = poa["poa_direct"].fillna(0.0).clip(lower=0.0)
        poa_diffuse = poa["poa_diffuse"].fillna(0.0).clip(lower=0.0)

        # 5. Cell Temperature (Faiman model)
        # Faiman u0 and u1 standard defaults: u0=25.0 W/(m^2*C), u1=6.84 W/(m^2*C*(m/s))
        cell_temp = temperature.faiman(
            poa_global=poa_global,
            temp_air=temp_air,
            wind_speed=wind_speed
        )

    else:
        # Fallback when pvlib is not installed
        solpos = _solar_position_fallback(times, plant.latitude, plant.longitude)
        solar_zenith = solpos["solar_zenith"]
        solar_azimuth = solpos["solar_azimuth"]
        solar_elevation = solpos["solar_elevation"]

        # Approximate airmass
        zenith_rad = np.radians(np.clip(solar_zenith, 0, 89.9))
        airmass_relative = pd.Series(1.0 / np.cos(zenith_rad), index=times).clip(1.0, 25.0)

        # Approximate clear-sky (simple Haurwitz model)
        daylight = solar_elevation > 0
        clearsky_ghi = pd.Series(0.0, index=times)
        clearsky_ghi[daylight] = 1098.0 * np.cos(zenith_rad[daylight]) * np.exp(-0.057 / np.cos(zenith_rad[daylight]))
        clearsky_ghi = clearsky_ghi.clip(lower=0.0)
        clearsky_dni = (clearsky_ghi * 0.8).clip(lower=0.0)
        clearsky_dhi = (clearsky_ghi * 0.2).clip(lower=0.0)

        # Approximate POA
        tilt_rad = np.radians(plant.tilt_deg)
        az_diff_rad = np.radians(solar_azimuth - plant.azimuth_deg)
        cos_inc = np.cos(zenith_rad) * np.cos(tilt_rad) + np.sin(zenith_rad) * np.sin(tilt_rad) * np.cos(az_diff_rad)
        cos_inc = np.clip(cos_inc, 0.0, 1.0)
        poa_direct = clearsky_dni * cos_inc
        poa_diffuse = clearsky_dhi * (1.0 + np.cos(tilt_rad)) / 2.0
        poa_global = (poa_direct + poa_diffuse).clip(lower=0.0)

        # Approximate cell temp
        cell_temp = temp_air + poa_global * 0.03

    # 6. Clear-sky Index (Kt = GHI / Clear-Sky GHI)
    clearsky_safe = np.where(clearsky_ghi > 10.0, clearsky_ghi, np.nan)
    clearsky_index = pd.Series(
        np.where(clearsky_ghi > 10.0, ghi / clearsky_safe, 0.0),
        index=times
    ).fillna(0.0).clip(lower=0.0, upper=2.0)

    # Nighttime zero clamping for POA and solar elevations below horizon
    night_mask = solar_elevation <= 0
    poa_global[night_mask] = 0.0
    poa_direct[night_mask] = 0.0
    poa_diffuse[night_mask] = 0.0
    clearsky_index[night_mask] = 0.0

    result_df = pd.DataFrame({
        "solar_zenith": solar_zenith,
        "solar_azimuth": solar_azimuth,
        "solar_elevation": solar_elevation,
        "airmass_relative": airmass_relative,
        "clearsky_ghi": clearsky_ghi,
        "clearsky_dni": clearsky_dni,
        "clearsky_dhi": clearsky_dhi,
        "poa_global": poa_global,
        "poa_direct": poa_direct,
        "poa_diffuse": poa_diffuse,
        "cell_temp": cell_temp,
        "clearsky_index": clearsky_index,
    }, index=times)

    return result_df
