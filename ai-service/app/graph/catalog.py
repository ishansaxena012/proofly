"""Research dimension catalog.

The planner combines a universal baseline (applies to every physical product) with
a category-specific set. Categories are matched from the resolved product; unknown
categories fall back to a generic set rather than to the headphone set.

Each dimension carries the keyword vocabulary used to route a passage to a topic
during evidence extraction, and a query template set used to build channel
queries. All of this is data, not branching logic, so adding a category is a data
change.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Dimension:
    name: str
    rationale: str
    keywords: tuple[str, ...]
    query_terms: tuple[str, ...] = field(default=())
    universal: bool = False


UNIVERSAL_DIMENSIONS: tuple[Dimension, ...] = (
    Dimension(
        name="Build Quality",
        rationale="Materials, assembly and physical robustness apply to any product.",
        keywords=(
            "build quality", "build", "materials", "plastic", "metal", "hinge", "creak",
            "flex", "solid", "sturdy", "flimsy", "scratch", "finish",
        ),
        query_terms=("build quality", "durability problems"),
        universal=True,
    ),
    Dimension(
        name="Reliability & Longevity",
        rationale="How the product holds up over months of ownership, and failure modes.",
        keywords=(
            "after six months", "after a year", "long term", "long-term", "broke", "broken",
            "failure", "died", "warranty", "repair", "defect", "reliability", "months of use",
            "three months", "still works",
        ),
        query_terms=("long term review", "problems after months"),
        universal=True,
    ),
    Dimension(
        name="Value for Money",
        rationale="Price relative to alternatives and to the previous generation.",
        keywords=(
            "price", "priced", "expensive", "cheap", "value", "worth", "cost", "discount",
            "msrp", "overpriced", "justify",
        ),
        query_terms=("worth the price", "price vs alternatives"),
        universal=True,
    ),
    Dimension(
        name="Ease of Use",
        rationale="Setup, controls, software and day-to-day friction.",
        keywords=(
            "setup", "app", "controls", "control", "touch", "gesture", "button", "menu",
            "interface", "intuitive", "confusing", "firmware", "update",
        ),
        query_terms=("app and controls", "setup problems"),
        universal=True,
    ),
)


GENERIC_DIMENSIONS: tuple[Dimension, ...] = (
    Dimension(
        name="Core Performance",
        rationale="How well the product does the main job it is bought for.",
        keywords=(
            "performance", "works", "effective", "results", "quality", "accurate", "fast",
            "slow", "powerful", "capable",
        ),
        query_terms=("review", "real world performance"),
    ),
    Dimension(
        name="Everyday Practicality",
        rationale="Fit into daily routines: size, noise, maintenance, consumables.",
        keywords=(
            "daily", "everyday", "clean", "maintenance", "size", "weight", "portable",
            "storage", "noisy", "quiet",
        ),
        query_terms=("daily use", "maintenance"),
    ),
)


CATEGORY_DIMENSIONS: dict[str, tuple[Dimension, ...]] = {
    "headphones": (
        Dimension(
            name="Sound Quality",
            rationale="Tonal balance, detail and tuning are the primary purchase driver.",
            keywords=(
                "sound", "sound quality", "audio", "bass", "treble", "midrange", "mids",
                "soundstage", "tuning", "frequency response", "sibilance", "detail",
                "equaliser", "equalizer", "ldac", "codec",
            ),
            query_terms=("sound quality review", "sound signature"),
        ),
        Dimension(
            name="Noise Cancellation",
            rationale="ANC performance is the headline feature of this category.",
            keywords=(
                "noise cancel", "noise cancelling", "noise canceling", "anc", "attenuation",
                "isolation", "rumble", "engine noise", "transparency", "ambient mode",
            ),
            query_terms=("noise cancellation performance", "ANC on a plane"),
        ),
        Dimension(
            name="Comfort & Fit",
            rationale="Comfort determines whether long listening sessions are tolerable.",
            keywords=(
                "comfort", "comfortable", "clamp", "clamping", "earpad", "ear pads", "pads",
                "pressure", "hot spot", "glasses", "fit", "heavy", "lightweight", "grams",
            ),
            query_terms=("comfort long sessions", "clamping force"),
        ),
        Dimension(
            name="Battery Life",
            rationale="Real measured endurance versus the manufacturer claim.",
            keywords=(
                "battery", "battery life", "hours", "charge", "charging", "quick charge",
                "playback", "endurance", "drain",
            ),
            query_terms=("battery life test", "real battery hours"),
        ),
        Dimension(
            name="Microphone & Call Quality",
            rationale="Call performance varies sharply by environment and is often contested.",
            keywords=(
                "microphone", "mic", "call", "calls", "voice", "wind", "windy", "meetings",
                "voice pickup", "intelligible", "muffled", "callers",
            ),
            query_terms=("microphone call quality", "mic in wind"),
        ),
        Dimension(
            name="Connectivity",
            rationale="Pairing stability, multipoint and codec support.",
            keywords=(
                "bluetooth", "pairing", "paired", "multipoint", "connection", "dropout",
                "latency", "range", "aac", "sbc", "lc3",
            ),
            query_terms=("bluetooth multipoint", "connection dropouts"),
        ),
    ),
    "laptop": (
        Dimension(
            name="Performance",
            rationale="CPU/GPU throughput and sustained performance under load.",
            keywords=(
                "cpu", "gpu", "benchmark", "performance", "render", "compile", "throttle",
                "sustained", "single core", "multi core", "ram", "memory",
            ),
            query_terms=("benchmark performance", "sustained load"),
        ),
        Dimension(
            name="Display",
            rationale="Panel quality dominates day-to-day satisfaction on a laptop.",
            keywords=(
                "display", "screen", "panel", "oled", "brightness", "nits", "colour", "color",
                "refresh rate", "glare", "reflective", "resolution",
            ),
            query_terms=("display quality", "screen brightness"),
        ),
        Dimension(
            name="Battery Life",
            rationale="Unplugged endurance versus the manufacturer claim.",
            keywords=("battery", "battery life", "hours", "charge", "unplugged", "drain", "watt"),
            query_terms=("real battery life", "battery test"),
        ),
        Dimension(
            name="Thermals & Noise",
            rationale="Fan noise and surface temperature are common regret drivers.",
            keywords=("fan", "fans", "thermal", "thermals", "hot", "heat", "noise", "loud", "throttling"),
            query_terms=("fan noise", "thermal throttling"),
        ),
        Dimension(
            name="Keyboard & Trackpad",
            rationale="Primary input quality on a device used for hours daily.",
            keywords=("keyboard", "keys", "key travel", "trackpad", "touchpad", "typing", "backlight"),
            query_terms=("keyboard feel", "trackpad quality"),
        ),
        Dimension(
            name="Ports & Connectivity",
            rationale="Port selection and dock/peripheral behaviour.",
            keywords=("port", "ports", "usb", "thunderbolt", "hdmi", "sd card", "dock", "wifi", "wi-fi"),
            query_terms=("port selection", "docking problems"),
        ),
    ),
    "smartphone": (
        Dimension(
            name="Camera Quality",
            rationale="Cameras are the dominant differentiator in this category.",
            keywords=(
                "camera", "photo", "photos", "video", "low light", "night mode", "zoom",
                "telephoto", "ultrawide", "processing", "hdr", "shutter",
            ),
            query_terms=("camera comparison", "low light camera"),
        ),
        Dimension(
            name="Battery Life",
            rationale="Screen-on time versus the manufacturer claim.",
            keywords=("battery", "screen on time", "sot", "charge", "charging", "hours", "drain"),
            query_terms=("battery screen on time", "battery test"),
        ),
        Dimension(
            name="Display",
            rationale="Panel brightness, refresh behaviour and outdoor legibility.",
            keywords=("display", "screen", "oled", "brightness", "nits", "refresh", "ppi", "outdoor"),
            query_terms=("display brightness", "screen quality"),
        ),
        Dimension(
            name="Performance",
            rationale="Chipset throughput, sustained performance and app responsiveness.",
            keywords=("chipset", "soc", "performance", "lag", "stutter", "benchmark", "throttle", "gaming"),
            query_terms=("performance and throttling", "gaming performance"),
        ),
        Dimension(
            name="Software & Updates",
            rationale="Update commitment and bloat materially affect ownership.",
            keywords=("software", "update", "updates", "android", "ios", "bloatware", "ui", "security patch"),
            query_terms=("software update policy", "software experience"),
        ),
        Dimension(
            name="Durability",
            rationale="Drop, scratch and water resistance in real ownership.",
            keywords=("durability", "drop", "cracked", "scratch", "ip68", "water", "gorilla glass", "shattered"),
            query_terms=("durability drop test", "screen scratches"),
        ),
    ),
    "kitchen_appliance": (
        Dimension(
            name="Output Quality",
            rationale="Quality of what the appliance actually produces.",
            keywords=("taste", "flavour", "flavor", "extraction", "crema", "texture", "evenly", "result", "consistency"),
            query_terms=("results quality", "taste test"),
        ),
        Dimension(
            name="Cleaning & Maintenance",
            rationale="Cleaning burden is the most common long-term complaint in this category.",
            keywords=("clean", "cleaning", "descale", "descaling", "dishwasher", "maintenance", "filter", "residue"),
            query_terms=("cleaning and descaling", "maintenance burden"),
        ),
        Dimension(
            name="Speed & Capacity",
            rationale="Throughput and batch size for household use.",
            keywords=("fast", "slow", "minutes", "capacity", "litre", "liter", "cups", "batch", "preheat"),
            query_terms=("how long does it take", "capacity"),
        ),
        Dimension(
            name="Noise",
            rationale="Operating noise in a shared living space.",
            keywords=("noise", "loud", "quiet", "decibel", "grinder", "buzzing", "rattle"),
            query_terms=("how loud is it", "noise level"),
        ),
    ),
}


CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "headphones": (
        "headphone", "headphones", "headset", "earbuds", "earphone", "earphones", "iem",
        "over-ear", "on-ear", "anc headphones", "wireless headphones",
    ),
    "laptop": ("laptop", "notebook", "ultrabook", "macbook", "chromebook", "gaming laptop"),
    "smartphone": ("smartphone", "phone", "iphone", "android phone", "mobile phone", "handset"),
    "kitchen_appliance": (
        "coffee machine", "espresso machine", "coffee maker", "blender", "air fryer",
        "toaster", "kettle", "food processor", "kitchen appliance", "grinder",
    ),
}


def resolve_category_key(*hints: str | None) -> tuple[str, bool]:
    """Map free-text category hints onto a catalog key.

    Returns ``(key, matched)``. ``matched`` is False when we fall back to the
    generic dimension set, which the planner records in the plan and the report
    discloses.
    """

    haystack = " ".join(hint.lower() for hint in hints if hint)
    best_key: str | None = None
    best_len = 0
    for key, aliases in CATEGORY_ALIASES.items():
        for alias in aliases:
            if alias in haystack and len(alias) > best_len:
                best_key, best_len = key, len(alias)
    if best_key:
        return best_key, True
    return "generic", False


def dimensions_for(category_key: str) -> tuple[Dimension, ...]:
    specific = CATEGORY_DIMENSIONS.get(category_key, GENERIC_DIMENSIONS)
    return specific + UNIVERSAL_DIMENSIONS
