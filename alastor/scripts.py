#!/usr/bin/env python3
import csv
import io
import json
import logging
import pathlib
import urllib.request
import zipfile

import krcg.utils

logger = logging.getLogger()


def geonames() -> None:
    """Fetch countries and first order cities from geonames.org, save as JSON"""
    print("generating geographical data...")
    path = pathlib.Path.cwd()
    local_filename, _headers = urllib.request.urlretrieve(
        "https://download.geonames.org/export/dump/countryInfo.txt"
    )
    buffer = io.StringIO()
    with open(local_filename) as f:
        for line in f.readlines():
            if line[:1] == "#":
                continue
            buffer.write(line)
    buffer.seek(0)
    countries = list(
        csv.DictReader(
            buffer,
            delimiter="\t",
            fieldnames=[
                "iso",
                "iso3",
                "iso_numeric",
                "fips",
                "country",
                "capital",
                "area",
                "population",
                "continent",
                "tld",
                "currency_code",
                "currency_name",
                "phone",
                "postal_code_format",
                "postal_code_regex",
                "languages",
                "geoname_id",
                "neighbours",
                "equivalent_fips_code",
            ],
        )
    )
    for country in countries:
        try:
            country["languages"] = country["languages"].split(",")
            country.pop("neighbours", None)
            country["geoname_id"] = int(country.get("geoname_id") or 0) or None
            country["area"] = float(country.get("area") or 0) or None
            country.pop("population", None)
            country.pop("area", None)
            logger.info(country)
        except (KeyError, ValueError):
            logger.exception(f"Failed to parse country: {country}")
    with open(path / "geodata" / "countries.json", "w", encoding="utf-8") as fp:
        json.dump(krcg.utils.json_pack(countries), fp, ensure_ascii=False)
    local_filename, _headers = urllib.request.urlretrieve(
        "https://download.geonames.org/export/dump/cities15000.zip"
    )
    z = zipfile.ZipFile(local_filename)
    cities = list(
        csv.DictReader(
            io.TextIOWrapper(z.open("cities15000.txt")),
            delimiter="\t",
            fieldnames=[
                "geoname_id",  # integer id of record in geonames database
                "name",  # name of geographical point (utf8) varchar(200)
                "ascii_name",  # name of geographical point in plain ascii characters
                "alternate_names",  # alternate ascii names automatically transliterated
                "latitude",  # latitude in decimal degrees (wgs84)
                "longitude",  # longitude in decimal degrees (wgs84)
                "feature_class",  # see http://www.geonames.org/export/codes.html
                "feature_code",  # see http://www.geonames.org/export/codes.html
                "country_code",  # ISO-3166 2-letter country code, 2 characters
                "cc2",  # alternate country codes, ISO-3166 2-letter country code
                "admin1_code",  # fipscode (subject to change to iso code)
                "admin2_code",  # code for the second administrative division
                "admin3_code",  # code for third level administrative division
                "admin4_code",  # code for fourth level administrative division
                "population",  # integer
                "elevation",  # in meters, integer
                "dem",  # digital elevation model, srtm3 or gtopo30, integer
                "timezone",  # iana timezone id
                "modification_date",  # date of last modification in ISO format
            ],
        )
    )
    for city in cities:
        city["geoname_id"] = int(city["geoname_id"])
        city["latitude"] = float(city["latitude"])
        city["longitude"] = float(city["longitude"])
        city["cc2"] = city["cc2"].split(",")
        city.pop("population", None)
        city.pop("elevation", None)
        city.pop("dem", None)
        city.pop("alternate_names", None)
    with open(path / "geodata" / "cities.json", "w", encoding="utf-8") as fp:
        json.dump(krcg.utils.json_pack(cities), fp, ensure_ascii=False)


if __name__ == "__main__":
    geonames()
