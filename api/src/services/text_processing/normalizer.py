"""
Text normalization module for TTS processing.
Handles various text formats including URLs, emails, numbers, money, and special characters.
Converts them into a format suitable for text-to-speech processing.
"""

import math
import re
from functools import lru_cache
from typing import List, Optional, Union

import inflect
from numpy import number

# from text_to_num import text2num
from torch import mul

from ...structures.schemas import NormalizationOptions

# Constants
VALID_TLDS = [
    "com",
    "org",
    "net",
    "edu",
    "gov",
    "mil",
    "int",
    "biz",
    "info",
    "name",
    "pro",
    "coop",
    "museum",
    "travel",
    "jobs",
    "mobi",
    "tel",
    "asia",
    "cat",
    "xxx",
    "aero",
    "arpa",
    "bg",
    "br",
    "ca",
    "cn",
    "de",
    "es",
    "eu",
    "fr",
    "in",
    "it",
    "jp",
    "mx",
    "nl",
    "ru",
    "uk",
    "us",
    "io",
    "co",
]

VALID_UNITS = {
    "m": "meter",
    "cm": "centimeter",
    "mm": "millimeter",
    "km": "kilometer",
    "in": "inch",
    "ft": "foot",
    "yd": "yard",
    "mi": "mile",  # Length
    "g": "gram",
    "kg": "kilogram",
    "mg": "milligram",  # Mass
    "s": "second",
    "ms": "millisecond",
    "min": "minutes",
    "h": "hour",  # Time
    "l": "liter",
    "ml": "mililiter",
    "cl": "centiliter",
    "dl": "deciliter",  # Volume
    "kph": "kilometer per hour",
    "mph": "mile per hour",
    "mi/h": "mile per hour",
    "m/s": "meter per second",
    "km/h": "kilometer per hour",
    "mm/s": "milimeter per second",
    "cm/s": "centimeter per second",
    "ft/s": "feet per second",
    "cm/h": "centimeter per day",  # Speed
    "°c": "degree celsius",
    "c": "degree celsius",
    "°f": "degree fahrenheit",
    "f": "degree fahrenheit",
    "k": "kelvin",  # Temperature
    "pa": "pascal",
    "kpa": "kilopascal",
    "mpa": "megapascal",
    "atm": "atmosphere",  # Pressure
    "hz": "hertz",
    "khz": "kilohertz",
    "mhz": "megahertz",
    "ghz": "gigahertz",  # Frequency
    "v": "volt",
    "kv": "kilovolt",
    "mv": "mergavolt",  # Voltage
    "a": "amp",
    "ma": "megaamp",
    "ka": "kiloamp",  # Current
    "w": "watt",
    "kw": "kilowatt",
    "mw": "megawatt",  # Power
    "j": "joule",
    "kj": "kilojoule",
    "mj": "megajoule",  # Energy
    "Ω": "ohm",
    "kΩ": "kiloohm",
    "mΩ": "megaohm",  # Resistance (Ohm)
    "f": "farad",
    "µf": "microfarad",
    "nf": "nanofarad",
    "pf": "picofarad",  # Capacitance
    "b": "bit",
    "kb": "kilobit",
    "mb": "megabit",
    "gb": "gigabit",
    "tb": "terabit",
    "pb": "petabit",  # Data size
    "kbps": "kilobit per second",
    "mbps": "megabit per second",
    "gbps": "gigabit per second",
    "tbps": "terabit per second",
    "px": "pixel",  # CSS units
}

SYMBOL_REPLACEMENTS = {
    "~": " ",
    "@": " at ",
    "#": " number ",
    "$": " dollar ",
    "%": " percent ",
    "^": " ",
    "&": " and ",
    "*": " ",
    "_": " ",
    "|": " ",
    "\\": " ",
    "/": " slash ",
    "=": " equals ",
    "+": " plus ",
}

MONEY_UNITS = {"$": ("dollar", "cent"), "£": ("pound", "pence"), "€": ("euro", "cent")}

# Pre-compiled regex patterns for performance
EMAIL_PATTERN = re.compile(
    r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}\b", re.IGNORECASE
)
URL_PATTERN = re.compile(
    r"(https?://|www\.|)+(localhost|[a-zA-Z0-9.-]+(\.(?:"
    + "|".join(VALID_TLDS)
    + r"))+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})(:[0-9]+)?([/?][^\s]*)?",
    re.IGNORECASE,
)

UNIT_PATTERN = re.compile(
    r"((?<!\w)([+-]?)(\d{1,3}(,\d{3})*|\d+)(\.\d+)?)\s*("
    + "|".join(sorted(list(VALID_UNITS.keys()), reverse=True))
    + r"""){1}(?=[^\w\d]{1}|\b)""",
    re.IGNORECASE,
)

TIME_PATTERN = re.compile(
    r"([0-9]{1,2} ?: ?[0-9]{2}( ?: ?[0-9]{2})?)( ?(pm|am)\b)?", re.IGNORECASE
)

MONEY_PATTERN = re.compile(
    r"(-?)(["
    + "".join(MONEY_UNITS.keys())
    + r"])(\d+(?:\.\d+)?)((?: hundred| thousand| (?:[bm]|tr|quadr)illion|k|m|b|t)*)\b",
    re.IGNORECASE,
)

NUMBER_PATTERN = re.compile(
    r"(-?)(\d+(?:\.\d+)?)((?: hundred| thousand| (?:[bm]|tr|quadr)illion|k|m|b)*)\b",
    re.IGNORECASE,
)

DEFAULT_PRONUNCIATION_DICTIONARY = {
    "Abington": "/'æb ɪŋ tən/",
    "Acton": "/'æktən/",
    "Acushnet": "/ək'ʊʃnɪt/",
    "Adams": "/'ædəmz/",
    "Agawam": "/'æɡəw,æm/",
    "Alford": "/əlf'ɔɹd/",
    "Amesbury": "/'eɪmz bɛr i/",
    "Amherst": "/'æmhəɹst/",
    "Andover": "/'ændoʊvəɹ/",
    "Arlington": "/'ɑɹlɪŋtən/",
    "Ashburnham": "/'æʃbəɹn,æm/",
    "Ashby": "/'æʃbi/",
    "Ashfield": "/'æʃfild/",
    "Ashland": "/'æʃlənd/",
    "Athol": "/'æθ ɔl/",
    "Attleboro": "/'ætəlbəɹə/",
    "Auburn": "/'ɔbəɹn/",
    "Avon": "/'eɪ vən/",
    "Ayer": "/'eɪ ər/",
    "Barnstable": "/'bɑrn stə bəl/",
    "Barre": "/'bær i/",
    "Becket": "/b'ɛkət/",
    "Bedford": "/b'ɛdfəɹd/",
    "Belchertown": "/b'ɛlʧəɹt,aʊn/",
    "Bellingham": "/b'ɛlɪŋh,æm/",
    "Belmont": "/b'ɛlmɑnt/",
    "Berkley": "/b'ɜɹkli/",
    "Berlin": "/bəɹl'ɪn/",
    "Bernardston": "/b'ɜɹnəɹdstən/",
    "Beverly": "/'bɛv ər li/",
    "Billerica": "/bɪl'ɹɪkə/",
    "Blackstone": "/bl'ækstoʊn/",
    "Blandford": "/bl'ændfəɹd/",
    "Bolton": "/'boʊl tən/",
    "Boston": "/'bɑs tən/",
    "Bourne": "/bɔrn/",
    "Boxborough": "/b'ɑksbəɹ,oʊ/",
    "Boxford": "/b'ɑksfəɹd/",
    "Boylston": "/b'ɔɪlstən/",
    "Braintree": "/bɹ'eɪntɹi/",
    "Brewster": "/bɹ'ustəɹ/",
    "Bridgewater": "/bɹ'ɪʤwɔtəɹ/",
    "Brimfield": "/bɹ'ɪmfild/",
    "Brockton": "/'bɹɑk tən/",
    "Brookfield": "/bɹ'ʊkfild/",
    "Brookline": "/'brʊk laɪn/",
    "Buckland": "/b'ʌklənd/",
    "Burlington": "/b'ɜɹlɪŋtən/",
    "Cambridge": "/'keɪm bɹɪd͡ʒ/",
    "Canton": "/k,ænt'ɑn/",
    "Carlisle": "/k'ɑɹl,aɪl/",
    "Carver": "/k'ɑɹvəɹ/",
    "Charlemont": "/ʧ'ɑɹlɪm,ɔnt/",
    "Charlton": "/ʧ'ɑɹltən/",
    "Chatham": "/'tʃæ θəm/",
    "Chelmsford": "/ʧ'ɛlmsfəɹd/",
    "Chelsea": "/ʧ'ɛlsi/",
    "Cheshire": "/ʧ'ɛʃəɹ/",
    "Chester": "/ʧ'ɛstəɹ/",
    "Chesterfield": "/ʧ'ɛstəɹf,ild/",
    "Chicopee": "/'tʃɪk ə pi/",
    "Chilmark": "/ʧ'ɪlmɑɹk/",
    "Clarksburg": "/kl'ɑɹksbɜɹɡ/",
    "Clinton": "/kl'ɪntən/",
    "Cohasset": "/koʊ'hæs ɪt/",
    "Colrain": "/k'ɑlɹeɪn/",
    "Concord": "/'kɑŋ kərd/",
    "Conway": "/k'ɑnweɪ/",
    "Cummington": "/k'ʌmɪŋtən/",
    "Dalton": "/d'ɔltən/",
    "Danvers": "/d'ænvəɹz/",
    "Dartmouth": "/d'ɑɹtməθ/",
    "Dedham": "/'dɛd əm/",
    "Deerfield": "/d'ɪɹfild/",
    "Dennis": "/d'ɛnɪs/",
    "Dighton": "/d'aɪtən/",
    "Douglas": "/d'ʌɡləz/",
    "Dover": "/'doʊ vər/",
    "Dracut": "/'dreɪ kət/",
    "Dudley": "/d'ʌdli/",
    "Dunstable": "/d'ʌnstəbəl/",
    "Duxbury": "/'dʌks bɛr i/",
    "East Bridgewater": "/'ist bɹ'ɪʤwɔtəɹ/",
    "East Brookfield": "/'ist bɹ'ʊkfild/",
    "East Longmeadow": "/'ist l'ɔŋmɪd,oʊ/",
    "Eastham": "/'iːst hæm/",
    "Easthampton": "/,iːst'hæmp tən/",
    "Easton": "/'istən/",
    "Edgartown": "/'ɛdɡəɹt,aʊn/",
    "Egremont": "/'ɛɡɹɪm,ɔnt/",
    "Erving": "/'ɜɹvɪŋ/",
    "Essex": "/'ɛsəks/",
    "Everett": "/'ɛv ər ɪt/",
    "Fairhaven": "/f'ɛɹheɪvən/",
    "Fall River": "/f'ɔl ɹ'ɪvəɹ/",
    "Falmouth": "/f'ælməθ/",
    "Fitchburg": "/f'ɪʧb,ɜɹɡ/",
    "Florida": "/fl'ɔɹədə/",
    "Foxborough": "/'fɑks bə roʊ/",
    "Framingham": "/'freɪm ɪŋ hæm/",
    "Franklin": "/fɹ'æŋklən/",
    "Freetown": "/fɹ'it,aʊn/",
    "Gardner": "/ɡ'ɑɹdnəɹ/",
    "Aquinnah": "/'ækwɪnə/",
    "Georgetown": "/ʤ'ɔɹʤt,aʊn/",
    "Gill": "/ɡ'ɪl/",
    "Gloucester": "/'ɡlɑs tər/",
    "Goshen": "/ɡ'ɑʃən/",
    "Gosnold": "/ɡ'ɑsnoʊld/",
    "Grafton": "/ɡɹ'æftən/",
    "Granby": "/ɡɹ'ænbi/",
    "Granville": "/ɡɹ'ænvɪl/",
    "Great Barrington": "/ɡɹ'eɪt b'æɹɪŋtən/",
    "Greenfield": "/ɡɹ'inf,ild/",
    "Groton": "/ɡɹ'ɑtən/",
    "Groveland": "/ɡɹ'ɑvɛlənd/",
    "Hadley": "/h'ædli/",
    "Halifax": "/h'æləf,æks/",
    "Hamilton": "/h'æməltən/",
    "Hampden": "/h'æmpdən/",
    "Hancock": "/h'æŋkɑk/",
    "Hanover": "/h'æn,oʊvəɹ/",
    "Hanson": "/h'ænsən/",
    "Hardwick": "/h'ɑɹdwɪk/",
    "Harvard": "/h'ɑɹvəɹd/",
    "Harwich": "/h'æɹɪʤ/",
    "Hatfield": "/h'ætfild/",
    "Haverhill": "/'heɪ vɹɪl/",
    "Hawley": "/h'ɔli/",
    "Heath": "/h'iθ/",
    "Hingham": "/'hɪŋ əm/",
    "Hinsdale": "/h'ɪnsdeɪl/",
    "Holbrook": "/'hoʊl brʊk/",
    "Holden": "/h'oʊldən/",
    "Holland": "/h'ɑlənd/",
    "Holliston": "/h'ɑlɪstən/",
    "Holyoke": "/h'oʊlioʊk/",
    "Hopedale": "/h'oʊpdeɪl/",
    "Hopkinton": "/h'ɑpkɪntən/",
    "Hubbardston": "/h'ʌbɑɹdstən/",
    "Hudson": "/h'ʌdsən/",
    "Hull": "/hʌl/",
    "Huntington": "/h'ʌntɪŋtən/",
    "Ipswich": "/'ɪpswəʧ/",
    "Kingston": "/k'ɪŋstən/",
    "Lakeville": "/l'eɪkvɪl/",
    "Lancaster": "/l'æŋk,æstəɹ/",
    "Lanesborough": "/l'eɪnsbəɹ,oʊ/",
    "Lawrence": "/'lɔr əns/",
    "Lee": "/l'i/",
    "Leicester": "/'lɛs tər/",
    "Lenox": "/l'ɛnəks/",
    "Leominster": "/'lɛm ən stər/",
    "Leverett": "/l'ɛvəɹɹɪt/",
    "Lexington": "/l'ɛksɪŋtən/",
    "Leyden": "/l'eɪdən/",
    "Lincoln": "/l'ɪŋkən/",
    "Littleton": "/l'ɪtəltən/",
    "Longmeadow": "/l'ɔŋmɪd,oʊ/",
    "Lowell": "/l'oʊəl/",
    "Ludlow": "/l'ʌdloʊ/",
    "Lunenburg": "/l'ʌnənb,ɜɹɡ/",
    "Lynn": "/l'ɪn/",
    "Lynnfield": "/l'ɪnfild/",
    "Malden": "/m'ɔldən/",
    "Manchester": "/m'ænʧəstəɹ/",
    "Mansfield": "/m'ænsf,ild/",
    "Marblehead": "/m'ɑɹbəlhɛd/",
    "Marion": "/m'ɛɹiən/",
    "Marlborough": "/'mɑrl bə roʊ/",
    "Marshfield": "/m'ɑɹʃfild/",
    "Mashpee": "/m'æʃpi/",
    "Mattapoisett": "/mætə'pɔɪsɛt/",
    "Maynard": "/'meɪ nərd/",
    "Medfield": "/m'ɛdfild/",
    "Medford": "/'mɛd fərd/",
    "Medway": "/'mɛd weɪ/",
    "Melrose": "/m'ɛlɹoʊz/",
    "Mendon": "/m'ɛndən/",
    "Merrimac": "/'mɛr ə mæk/",
    "Methuen": "/mə'θuː ən/",
    "Middleborough": "/'mɪd əl bə roʊ/",
    "Middlefield": "/m'ɪdəlf,ild/",
    "Middleton": "/m'ɪdəltən/",
    "Milford": "/m'ɪlfəɹd/",
    "Millbury": "/m'ɪlbɛɹi/",
    "Millis": "/'mɪl ɪs/",
    "Millville": "/m'ɪlvɪl/",
    "Milton": "/m'ɪltən/",
    "Monroe": "/mən'roʊ/",
    "Monson": "/m'ɔnsən/",
    "Montague": "/m'ɑntəɡj,u/",
    "Monterey": "/m,ɑntəɹ'eɪ/",
    "Montgomery": "/məntɡ'ʌməɹi/",
    "Mount Washington": "/m'aʊnt w'ɔʃɪŋtən/",
    "Nahant": "/nə'hɑnt/",
    "Nantucket": "/næn'tʌk ɪt/",
    "Natick": "/'neɪ tɪk/",
    "Needham": "/'niː dəm/",
    "New Ashford": "/njuː 'æʃ fərd/",
    "New Bedford": "/njuː 'bɛd fərd/",
    "New Braintree": "/njuː 'breɪn tri/",
    "New Marlborough": "/njuː 'mɑrl bə roʊ/",
    "New Salem": "/njuː 'seɪ ləm/",
    "Newbury": "/'nuː bər i/",
    "Newburyport": "/'nuː bər i pɔrt/",
    "Newton": "/'nuː tən/",
    "Norfolk": "/n'ɔɹfək/",
    "North Adams": "/n'ɔɹθ 'ædəmz/",
    "North Andover": "/,nɔrθ 'æn doʊ vər/",
    "North Attleborough": "/,nɔrθ 'æt əl bər oʊ/",
    "North Brookfield": "/n'ɔɹθ bɹ'ʊkfild/",
    "North Reading": "/,nɔrθ 'rɛd ɪŋ/",
    "Northampton": "/nɔɹθ'æmptən/",
    "Northborough": "/'nɔrθ bə roʊ/",
    "Northbridge": "/n'ɔɹθbɹɪʤ/",
    "Northfield": "/n'ɔɹθfild/",
    "Norton": "/n'ɔɹtən/",
    "Norwell": "/'nɔr wɛl/",
    "Norwood": "/n'ɔɹwʊd/",
    "Oak Bluffs": "/'oʊk bl'ʌfs/",
    "Oakham": "/'oʊkæm/",
    "Orange": "/'ɔɹənʤ/",
    "Orleans": "/ɔɹl'inz/",
    "Otis": "/'oʊtɪs/",
    "Oxford": "/'ɑksfəɹd/",
    "Palmer": "/p'ɑlməɹ/",
    "Paxton": "/p'ækstən/",
    "Peabody": "/'piː bə di/",
    "Pelham": "/p'ɛləm/",
    "Pembroke": "/p'ɛmbɹoʊk/",
    "Pepperell": "/p'ɛpəɹɹəl/",
    "Peru": "/pəɹ'u/",
    "Petersham": "/p'itəɹʃ,æm/",
    "Phillipston": "/f'ɪlɪpstən/",
    "Pittsfield": "/p'ɪtsfild/",
    "Plainfield": "/pl'eɪnfild/",
    "Plainville": "/pl'eɪnvɪl/",
    "Plymouth": "/pl'ɪməθ/",
    "Plympton": "/pl'ɪmptən/",
    "Princeton": "/pɹ'ɪnstən/",
    "Provincetown": "/'prɑv əns taʊn/",
    "Quincy": "/'kwɪn zi/",
    "Randolph": "/ɹ,ænd'ɔlf/",
    "Raynham": "/ɹ'eɪnæm/",
    "Reading": "/'rɛdɪŋ/",
    "Rehoboth": "/rɪ'hoʊ bəθ/",
    "Revere": "/ɹəv'ɪɹ/",
    "Richmond": "/ɹ'ɪʧmənd/",
    "Rochester": "/ɹ'ɑtʃ,ʌstəɹ/",
    "Rockland": "/ɹ'ɑklənd/",
    "Rockport": "/ɹ'ɑkpɔɹt/",
    "Rowe": "/ɹ'oʊ/",
    "Rowley": "/ɹ'oʊli/",
    "Royalston": "/ɹ'ɔɪælstən/",
    "Russell": "/ɹ'ʌsəl/",
    "Rutland": "/ɹ'ʌtlənd/",
    "Salem": "/s'eɪləm/",
    "Salisbury": "/s'ɔlzb,ɛɹi/",
    "Sandisfield": "/s'ændɪsf,ild/",
    "Sandwich": "/s'ændw,ɪʧ/",
    "Saugus": "/s'ɔɡəs/",
    "Savoy": "/səv'ɔɪ/",
    "Scituate": "/'sɪtʃ u ət/",
    "Seekonk": "/'siː kɑŋk/",
    "Sharon": "/ʃ'ɛɹən/",
    "Sheffield": "/ʃ'ɛfild/",
    "Shelburne": "/ʃ'ɛlbɜɹn/",
    "Sherborn": "/ʃ'ɜɹbɔɹn/",
    "Shirley": "/ʃ'ɜɹli/",
    "Shrewsbury": "/'ʃruz bɛr i/",
    "Shutesbury": "/ʃj'utsbɛɹi/",
    "Somerset": "/s'ʌməs,ɛt/",
    "Somerville": "/'sʌm ər vɪl/",
    "South Hadley": "/s'aʊθ h'ædli/",
    "Southampton": "/s,aʊθh'æmptən/",
    "Southborough": "/s'aʊθbəɹ,oʊ/",
    "Southbridge": "/s'aʊθbɹɪʤ/",
    "Southwick": "/s'aʊθwɪk/",
    "Spencer": "/sp'ɛnsəɹ/",
    "Springfield": "/spɹ'ɪŋf,ild/",
    "Sterling": "/st'ɜɹlɪŋ/",
    "Stockbridge": "/st'ɑkbɹɪʤ/",
    "Stoneham": "/st'oʊnhæm/",
    "Stoughton": "/st'ɔtən/",
    "Stow": "/st'oʊ/",
    "Sturbridge": "/st'ɜɹbɹɪʤ/",
    "Sudbury": "/s'ʌdbɛɹi/",
    "Sunderland": "/s'ʌndəɹlənd/",
    "Sutton": "/s'ʌtn/",
    "Swampscott": "/sw'ɑmpskɑt/",
    "Swansea": "/sw'ɑnzi/",
    "Taunton": "/'tɔn tən/",
    "Templeton": "/t'ɛmpəltən/",
    "Tewksbury": "/'tʊks bɛr i/",
    "Tisbury": "/'tɪz bɛr i/",
    "Tolland": "/t'oʊlənd/",
    "Topsfield": "/t'ɑpsfild/",
    "Townsend": "/t'aʊnsɛnd/",
    "Truro": "/tɹ'ʊɹ,oʊ/",
    "Tyngsborough": "/'tɪŋz bə roʊ/",
    "Tyringham": "/t'aɪɹɪŋ,æm/",
    "Upton": "/'ʌptən/",
    "Uxbridge": "/'ʌksbɹɪʤ/",
    "Wakefield": "/'weɪk fiːld/",
    "Wales": "/w'eɪlz/",
    "Walpole": "/w'ɔlpoʊl/",
    "Waltham": "/'wɔl θæm/",
    "Ware": "/w'ɛɹ/",
    "Wareham": "/'wɛr əm/",
    "Warren": "/w'ɔɹən/",
    "Warwick": "/w'ɔɹwɪk/",
    "Washington": "/w'ɔʃɪŋtən/",
    "Watertown": "/'wɔ tər taʊn/",
    "Wayland": "/'weɪ lənd/",
    "Webster": "/w'ɛbstəɹ/",
    "Wellesley": "/w'ɛlzli/",
    "Wellfleet": "/w'ɛlflit/",
    "Wendell": "/w'ɛndɛl/",
    "Wenham": "/w'ɛnæm/",
    "West Boylston": "/w'ɛst b'ɔɪlstən/",
    "West Bridgewater": "/w'ɛst bɹ'ɪʤwɔtəɹ/",
    "West Brookfield": "/w'ɛst bɹ'ʊkfild/",
    "West Newbury": "/w'ɛst n'ubɛɹi/",
    "West Springfield": "/w'ɛst spɹ'ɪŋf,ild/",
    "West Stockbridge": "/w'ɛst st'ɑkbɹɪʤ/",
    "West Tisbury": "/w'ɛst t'ɪsbɛɹi/",
    "Westborough": "/w'ɛstbəɹ,oʊ/",
    "Westfield": "/'wɛst fiːld/",
    "Westford": "/w'ɛstfəɹd/",
    "Westhampton": "/wɛsθ'æmptən/",
    "Westminster": "/w'ɛstm,ɪnstəɹ/",
    "Weston": "/w'ɛstən/",
    "Westport": "/w'ɛstpɔɹt/",
    "Westwood": "/'wɛst wʊd/",
    "Weymouth": "/'weɪ məθ/",
    "Whately": "/w'ʌtli/",
    "Whitman": "/w'ɪtmən/",
    "Wilbraham": "/w'ɪlbɹəh,æm/",
    "Williamsburg": "/w'ɪljəmzb,ɜɹɡ/",
    "Williamstown": "/w'ɪljəmst,aʊn/",
    "Wilmington": "/w'ɪlmɪŋtən/",
    "Winchendon": "/w'ɪnʧɛndən/",
    "Winchester": "/w'ɪnʧ,ɛstəɹ/",
    "Windsor": "/w'ɪnzəɹ/",
    "Winthrop": "/w'ɪnθɹɑp/",
    "Woburn": "/'wuː bərn/",
    "Worcester": "/'wɪstɚ/",
    "Worthington": "/w'ɜɹðɪŋtən/",
    "Wrentham": "/'rɛn θəm/",
    "Yarmouth": "/'jɑr məθ/",
    "Dorchester": "/dɔɹ'ʧɛstəɹ/",
    "Hyde Park": "/h'aɪd pɑɹk/",
    "Mattapan": "/m'ætəpæn/",
    "Roslindale": "/ɹ'ɑzlɪn deɪl/",
    "Roxbury": "/ɹ'ɑks bɛɹi/",
    "Allston": "/'ɔlstən/",
    "Brighton": "/b'ɹaɪtn/",
    "Celtics": "/s'ɛltɪks/",
    "Fenway": "/f'ɛnweɪ/"
}

INFLECT_ENGINE = inflect.engine()

# Pronunciation normalization --------------------------------------------------------------

def handle_pronunciations(text: str, pronunciation_dict: dict = None) -> str:
    """
    Normalizes non-traditional names in the given text by converting them to their phonetic IPA representations.
    
    Args:
        text (str): The input text containing non-traditional names.
        pronunciation_dict (dict, optional): A dictionary of words and their International Phonetic Alphabet spellings.

    Returns:
        str: The text with non-traditional names normalized.
    """
    def preprocess_pronunciation(proper_noun: str, pn_to_ipa: dict):
        """
        Preprocesses the town name by converting it to the phonetic IPA representation.
        
        Args:
            town_name (str): The name of the town to preprocess.
        
        Returns:
            str: The preprocessed town name.
        """
        ipa = pn_to_ipa[proper_noun]
        if not ipa:
            return proper_noun  # Return the original proper noun if IPA is not available
        return f"[{proper_noun}]({ipa})\n"
    
    pn_to_ipa = DEFAULT_PRONUNCIATION_DICTIONARY.copy()
    if pronunciation_dict:
        pn_to_ipa.update(pronunciation_dict)

    # Match the exact known proper nouns, including multi-word and hyphenated names.
    pn_pattern = re.compile(
        r'\b(?:' + '|'.join(
            sorted((re.escape(town.strip()) for town in pn_to_ipa.keys()), key=len, reverse=True)
        ) + r')\b'
    )

    return pn_pattern.sub(
        lambda match: preprocess_pronunciation(match.group(0), pn_to_ipa),
        text,
    )

# Remove HTML tags and their content --------------------------------------------------------------

def handle_html_tags_and_content(text):
    # Remove HTML tags and their content
    clean_text = re.sub(r'<.*?>', '', text)
    return clean_text

# Punctuation normalization --------------------------------------------------------------
def handle_comma_pacing(text):
    # Normalize punctuation in the text
    def replace_commas_with_semicolon_hyphens(text):
        # Replace commas with semicolons
        return text.replace(',', ';-')
    text = replace_commas_with_semicolon_hyphens(text)
    return text

def handle_slashes(text):
    # Add spaces around slashes in the text for better readability
    # Example: Convert "and/or" to "and / or"
    text = text.replace("/", " / ")
    return text

# Date normalization --------------------------------------------------------------
def handle_month_abbreviations(text):
    # Normalize dates in the text
    # Example: Convert "Jan. 23, 2025" to "January 23, 2025"
    month_abbreviations = {
        "Jan.": "January",
        "Feb.": "February",
        "Mar.": "March",
        "Apr.": "April",
        "May.": "May",
        "Jun.": "June",
        "Jul.": "July",
        "Aug.": "August",
        "Sep.": "September",
        "Oct.": "October",
        "Nov.": "November",
        "Dec.": "December"
    }
    for abbr, full in month_abbreviations.items():
        text = text.replace(abbr, full)
    return text

def handle_scores(text):
    # Normalize scores in the text
    # Example: Convert "3-2" to "three - two"
    score_pattern = re.compile(r'(\d+)-(\d+)')
    return score_pattern.sub(lambda m: f"{INFLECT_ENGINE.number_to_words(int(m.group(1)))} - {INFLECT_ENGINE.number_to_words(int(m.group(2)))}", text)

def handle_number_abbreviations(text):
    # Normalize number abbreviations in the text
    # Example: Convert "No. 1" to "Number one"
    number_abbr_pattern = re.compile(r'No\. (\d+)')
    return number_abbr_pattern.sub(lambda m: f"Number {INFLECT_ENGINE.number_to_words(int(m.group(1)))}", text)

def handle_units(u: re.Match[str]) -> str:
    """Converts units to their full form"""
    unit_string = u.group(6).strip()
    unit = unit_string

    if unit_string.lower() in VALID_UNITS:
        unit = VALID_UNITS[unit_string.lower()].split(" ")

        # Handles the B vs b case
        if unit[0].endswith("bit"):
            b_case = unit_string[min(1, len(unit_string) - 1)]
            if b_case == "B":
                unit[0] = unit[0][:-3] + "byte"

        number = u.group(1).strip()
        unit[0] = INFLECT_ENGINE.no(unit[0], number)
    return " ".join(unit)


def conditional_int(number: float, threshold: float = 0.00001):
    if abs(round(number) - number) < threshold:
        return int(round(number))
    return number


def translate_multiplier(multiplier: str) -> str:
    """Translate multiplier abrevations to words"""

    multiplier_translation = {
        "k": "thousand",
        "m": "million",
        "b": "billion",
        "t": "trillion",
    }
    if multiplier.lower() in multiplier_translation:
        return multiplier_translation[multiplier.lower()]
    return multiplier.strip()


def split_four_digit(number: float):
    part1 = str(conditional_int(number))[:2]
    part2 = str(conditional_int(number))[2:]
    return f"{INFLECT_ENGINE.number_to_words(part1)} {INFLECT_ENGINE.number_to_words(part2)}"


def handle_numbers(n: re.Match[str]) -> str:
    number = n.group(2)

    try:
        number = float(number)
    except:
        return n.group()

    if n.group(1) == "-":
        number *= -1

    multiplier = translate_multiplier(n.group(3))

    number = conditional_int(number)
    if multiplier != "":
        multiplier = f" {multiplier}"
    else:
        if (
            number % 1 == 0
            and len(str(number)) == 4
            and number > 1500
            and number % 1000 > 9
        ):
            return split_four_digit(number)

    return f"{INFLECT_ENGINE.number_to_words(number)}{multiplier}"


def handle_money(m: re.Match[str]) -> str:
    """Convert money expressions to spoken form"""

    bill, coin = MONEY_UNITS[m.group(2)]

    number = m.group(3)

    try:
        number = float(number)
    except:
        return m.group()

    if m.group(1) == "-":
        number *= -1

    multiplier = translate_multiplier(m.group(4))

    if multiplier != "":
        multiplier = f" {multiplier}"

    if number % 1 == 0 or multiplier != "":
        text_number = f"{INFLECT_ENGINE.number_to_words(conditional_int(number))}{multiplier} {INFLECT_ENGINE.plural(bill, count=number)}"
    else:
        sub_number = int(str(number).split(".")[-1].ljust(2, "0"))

        text_number = f"{INFLECT_ENGINE.number_to_words(int(math.floor(number)))} {INFLECT_ENGINE.plural(bill, count=number)} and {INFLECT_ENGINE.number_to_words(sub_number)} {INFLECT_ENGINE.plural(coin, count=sub_number)}"

    return text_number


def handle_decimal(num: re.Match[str]) -> str:
    """Convert decimal numbers to spoken form"""
    a, b = num.group().split(".")
    return " point ".join([a, " ".join(b)])


def handle_email(m: re.Match[str]) -> str:
    """Convert email addresses into speakable format"""
    email = m.group(0)
    parts = email.split("@")
    if len(parts) == 2:
        user, domain = parts
        user = user.replace(".", " dot ").replace("_", " underscore ").replace("-", " dash ").strip()
        domain = domain.replace(".", " dot ")
        return f"{user} at {domain}"
    return email


def handle_url(u: re.Match[str]) -> str:
    """Make URLs speakable by converting special characters to spoken words"""
    if not u:
        return ""

    url = u.group(0).strip()

    # Handle protocol first
    url = re.sub(
        r"^https?://",
        lambda a: "https " if "https" in a.group() else "http ",
        url,
        flags=re.IGNORECASE,
    )
    url = re.sub(r"^www\.", "www ", url, flags=re.IGNORECASE)

    # Handle port numbers before other replacements
    url = re.sub(r":(\d+)(?=/|$)", lambda m: f" colon {m.group(1)}", url)

    # Split into domain and path
    parts = url.split("/", 1)
    domain = parts[0]
    path = parts[1] if len(parts) > 1 else ""

    # Handle dots in domain
    domain = domain.replace(".", " dot ")

    # Reconstruct URL
    if path:
        url = f"{domain} slash {path}"
    else:
        url = domain

    # Replace remaining symbols with words
    url = url.replace("-", " dash ")
    url = url.replace("_", " underscore ")
    url = url.replace("?", " question-mark ")
    url = url.replace("=", " equals ")
    url = url.replace("&", " ampersand ")
    url = url.replace("%", " percent ")
    url = url.replace(":", " colon ")  # Handle any remaining colons
    url = url.replace("/", " slash ")  # Handle any remaining slashes

    # Clean up extra spaces
    return re.sub(r"\s+", " ", url).strip()


def handle_phone_number(p: re.Match[str]) -> str:
    p = list(p.groups())

    country_code = ""
    if p[0] is not None:
        p[0] = p[0].replace("+", "")
        country_code += INFLECT_ENGINE.number_to_words(p[0])

    area_code = INFLECT_ENGINE.number_to_words(
        p[2].replace("(", "").replace(")", ""), group=1, comma=""
    )

    telephone_prefix = INFLECT_ENGINE.number_to_words(p[3], group=1, comma="")

    line_number = INFLECT_ENGINE.number_to_words(p[4], group=1, comma="")

    return ",".join([country_code, area_code, telephone_prefix, line_number])


def handle_time(t: re.Match[str]) -> str:
    t = t.groups()

    time_parts = t[0].split(":")

    numbers = []
    numbers.append(INFLECT_ENGINE.number_to_words(time_parts[0].strip()))

    minute_number = INFLECT_ENGINE.number_to_words(time_parts[1].strip())
    if int(time_parts[1]) < 10:
        if int(time_parts[1]) != 0:
            numbers.append(f"oh {minute_number}")
    else:
        numbers.append(minute_number)

    half = ""
    if len(time_parts) > 2:
        seconds_number = INFLECT_ENGINE.number_to_words(time_parts[2].strip())
        second_word = INFLECT_ENGINE.plural("second", int(time_parts[2].strip()))
        numbers.append(f"and {seconds_number} {second_word}")
    else:
        if t[2] is not None:
            half = " " + t[2].strip()
        else:
            if int(time_parts[1]) == 0:
                numbers.append("o'clock")

    return " ".join(numbers) + half


def normalize_text(text: str, normalization_options: NormalizationOptions) -> str:
    """Normalize text for TTS processing"""

    # Handle email addresses first if enabled
    if normalization_options.email_normalization:
        text = EMAIL_PATTERN.sub(handle_email, text)

    # Handle URLs if enabled
    if normalization_options.url_normalization:
        text = URL_PATTERN.sub(handle_url, text)

    # Pre-process numbers with units if enabled
    if normalization_options.unit_normalization:
        text = UNIT_PATTERN.sub(handle_units, text)

    # Replace optional pluralization
    if normalization_options.optional_pluralization_normalization:
        text = re.sub(r"\(s\)", "s", text)

    if normalization_options.html_normalization:
        text = handle_html_tags_and_content(text)

    if normalization_options.month_abbreviation_normalization:
        text = handle_month_abbreviations(text)

    if normalization_options.score_normalization:
        text = handle_scores(text)

    if normalization_options.number_abbreviation_normalization:
        text = handle_number_abbreviations(text)

    # Replace phone numbers:
    if normalization_options.phone_normalization:
        text = re.sub(
            r"(\+?\d{1,2})?([ .-]?)(\(?\d{3}\)?)[\s.-](\d{3})[\s.-](\d{4})",
            handle_phone_number,
            text,
        )

    # Replace quotes and brackets (additional cleanup)
    text = text.replace(chr(8216), "'").replace(chr(8217), "'")
    text = text.replace("«", chr(8220)).replace("»", chr(8221))
    text = text.replace(chr(8220), '"').replace(chr(8221), '"')

    # Handle CJK punctuation and some non standard chars
    for a, b in zip("、。！，：；？–", ",.!,:;?-"):
        text = text.replace(a, b + " ")

    # Handle simple time in the format of HH:MM:SS (am/pm)
    text = TIME_PATTERN.sub(
        handle_time,
        text,
    )

    # Clean up whitespace
    text = re.sub(r"[^\S \n]", " ", text)
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"(?<=\n) +(?=\n)", "", text)

    # Handle special characters that might cause audio artifacts first
    # Replace newlines with spaces (or pauses if needed)
    text = text.replace("\n", " ")
    text = text.replace("\r", " ")

    # Handle titles and abbreviations
    text = re.sub(r"\bD[Rr]\.(?= [A-Z])", "Doctor", text)
    text = re.sub(r"\b(?:Mr\.|MR\.(?= [A-Z]))", "Mister", text)
    text = re.sub(r"\b(?:Ms\.|MS\.(?= [A-Z]))", "Miss", text)
    text = re.sub(r"\b(?:Mrs\.|MRS\.(?= [A-Z]))", "Mrs", text)
    text = re.sub(r"\betc\.(?! [A-Z])", "etc", text)

    # Handle common words
    text = re.sub(r"(?i)\b(y)eah?\b", r"\1e'a", text)

    # Handle numbers and money BEFORE replacing special characters
    text = re.sub(r"(?<=\d),(?=\d)", "", text)

    text = MONEY_PATTERN.sub(
        handle_money,
        text,
    )

    text = NUMBER_PATTERN.sub(handle_numbers, text)

    text = re.sub(r"\d*\.\d+", handle_decimal, text)

    if normalization_options.punctuation_pacing_normalization:
        text = handle_slashes(text)
        text = handle_comma_pacing(text)

    # Handle other problematic symbols AFTER money/number processing
    if normalization_options.replace_remaining_symbols:
        for symbol, replacement in SYMBOL_REPLACEMENTS.items():
            text = text.replace(symbol, replacement)

    # Handle various formatting
    text = re.sub(r"(?<=\d)-(?=\d)", " to ", text)
    text = re.sub(r"(?<=\d)S", " S", text)
    text = re.sub(r"(?<=[BCDFGHJ-NP-TV-Z])'?s\b", "'S", text)
    text = re.sub(r"(?<=X')S\b", "s", text)
    text = re.sub(
        r"(?:[A-Za-z]\.){2,} [a-z]", lambda m: m.group().replace(".", "-"), text
    )
    text = re.sub(r"(?i)(?<=[A-Z])\.(?=[A-Z])", "-", text)

    text = re.sub(r"\s{2,}", " ", text)

    return text
