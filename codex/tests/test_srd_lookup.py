"""Tests for srd_lookup.py with canned answers; nothing here touches the network."""

import io
import json
import os
import time

import pytest

import srd_lookup as srd


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(srd, "CACHE_DIR", tmp_path / "cache")
    return tmp_path / "cache"


def _wizard():
    return {
        "key": "srd_wizard",
        "name": "Wizard",
        "hit_dice": "D6",
        "saving_throws": [{"name": "Intelligence"}, {"name": "Wisdom"}],
        "subclass_of": None,
        "features": [
            {
                "name": "Arcane Recovery",
                "desc": "You **regain** slots. Once per day. More text.",
                "gained_at": [{"level": 1, "detail": None}],
            },
            {"name": "Proficiencies", "desc": "skip me", "gained_at": []},
            {"name": "Spell Mastery", "desc": None, "gained_at": [{"level": 18}]},
        ],
    }


def _classes_raw():
    evoker = {
        "key": "srd_evocation",
        "name": "School of Evocation",
        "hit_dice": None,
        "saving_throws": [],
        "subclass_of": {"key": "srd_wizard", "name": "Wizard"},
        "features": [],
    }
    fighter = {**_wizard(), "key": "srd_fighter", "name": "Fighter", "hit_dice": "D10"}
    return [evoker, _wizard(), fighter]


def _species_raw():
    trait = {"name": "Darkvision", "desc": "See in the dark. Out to 60 feet."}
    skipped = {"name": "Age", "desc": "Mature at 100."}
    return [
        {
            "key": "srd_elf",
            "name": "Elf",
            "is_subspecies": False,
            "traits": [trait, skipped],
        },
        {
            "key": "srd_high-elf",
            "name": "High Elf",
            "is_subspecies": True,
            "subspecies_of": "srd_elf",
            "traits": [{"name": "Cantrip", "desc": "One wizard cantrip."}],
        },
        {"key": "srd_human", "name": "Human", "is_subspecies": False, "traits": []},
    ]


# --- parsing ----------------------------------------------------------------


def test_first_sentence_strips_markdown_and_cuts_at_the_first_sentence():
    assert (
        srd._first_sentence("You **regain** slots. Once per day.")
        == "You regain slots."
    )
    assert (
        srd._first_sentence("Line one\n\n| table | row |\nmore")
        == "Line one table row more"
    )
    assert srd._first_sentence(None) == "" and srd._first_sentence("") == ""
    long = srd._first_sentence("word " * 100)
    assert len(long) == 240 and long.endswith("...")


def test_die_size_reads_the_number_or_returns_none():
    assert srd._die_size("D6") == 6 and srd._die_size("d12") == 12
    assert srd._die_size(None) is None and srd._die_size("none") is None


def test_class_features_skip_rules_entries_and_record_the_levels():
    features = srd._class_features(_wizard()["features"])
    assert features == [
        {"name": "Arcane Recovery", "text": "You regain slots.", "levels": [1]},
        {"name": "Spell Mastery", "text": "", "levels": [18]},
    ]
    assert srd._class_features(None) == []


def test_class_entries_keep_base_classes_and_attach_subclass_names():
    entries = srd._class_entries(_classes_raw())
    assert [e["name"] for e in entries] == ["Fighter", "Wizard"]
    wizard = entries[1]
    assert wizard["die"] == 6 and wizard["saves"] == ["Intelligence", "Wisdom"]
    assert wizard["subclasses"] == ["School of Evocation"]
    assert entries[0]["subclasses"] == []


def test_species_entries_attach_subspecies_and_skip_flavor_traits():
    entries = srd._species_entries(_species_raw())
    assert [e["name"] for e in entries] == ["Elf", "Human"]
    elf = entries[0]
    assert elf["traits"] == [{"name": "Darkvision", "text": "See in the dark."}]
    assert elf["subspecies"] == [
        {
            "name": "High Elf",
            "traits": [{"name": "Cantrip", "text": "One wizard cantrip."}],
        }
    ]
    assert entries[1] == {"name": "Human", "traits": [], "subspecies": []}


def test_spell_entries_sort_by_level_then_name():
    raw = [
        {"name": "Shield", "level": 1, "classes": [{"name": "Wizard"}]},
        {"name": "Light", "level": 0, "classes": None},
        {"name": "Fire Bolt", "level": 0, "classes": [{"name": "Wizard"}]},
    ]
    assert [(s["name"], s["level"]) for s in srd._spell_entries(raw)] == [
        ("Fire Bolt", 0),
        ("Light", 0),
        ("Shield", 1),
    ]
    assert srd._spell_entries(raw)[1]["classes"] == []


def test_only_the_two_srd_documents_are_requested_and_credit_is_given():
    assert srd.DOCUMENTS == {"2014": "srd-2014", "2024": "srd-2024"}
    assert "Creative Commons Attribution 4.0" in srd.ATTRIBUTION
    assert "dnd.wizards.com/resources/systems-reference-document" in srd.ATTRIBUTION


# --- fetching and caching ---------------------------------------------------


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_json_sends_a_user_agent_and_turns_failures_into_srd_unavailable(
    monkeypatch,
):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["agent"] = request.get_header("User-agent")
        seen["timeout"] = timeout
        return _Response(b'{"ok": true}')

    monkeypatch.setattr(srd.urllib.request, "urlopen", fake_urlopen)
    assert srd._fetch_json(srd.API + "x/") == {"ok": True}
    assert seen == {"agent": srd.USER_AGENT, "timeout": srd.TIMEOUT_SECONDS}

    def offline(request, timeout):
        raise OSError("no route")

    monkeypatch.setattr(srd.urllib.request, "urlopen", offline)
    with pytest.raises(srd.SrdUnavailable, match="could not reach the SRD"):
        srd._fetch_json(srd.API)

    monkeypatch.setattr(
        srd.urllib.request, "urlopen", lambda request, timeout: _Response(b"<html>")
    )
    with pytest.raises(srd.SrdUnavailable, match="unreadable"):
        srd._fetch_json(srd.API)


def test_next_page_rejects_odd_shapes_and_foreign_next_links():
    assert srd._next_page({"results": [1], "next": None}) == ([1], None)
    ok = srd.API + "classes/?page=2"
    assert srd._next_page({"results": [], "next": ok}) == ([], ok)
    for bad in (
        [],
        {},
        {"results": "x"},
        {"results": [], "next": "https://evil.example/x"},
    ):
        with pytest.raises(srd.SrdUnavailable):
            srd._next_page(bad)


def test_all_results_follows_pages_and_asks_only_for_the_srd_document(monkeypatch):
    urls = []
    pages = {
        0: {"results": ["a"], "next": srd.API + "spells/?page=2"},
        1: {"results": ["b"], "next": None},
    }

    def fake_fetch(url):
        urls.append(url)
        return pages[len(urls) - 1]

    monkeypatch.setattr(srd, "_fetch_json", fake_fetch)
    assert srd._all_results("spells", "2024", "name,level") == ["a", "b"]
    assert (
        urls[0]
        == srd.API + "spells/?document__key=srd-2024&limit=500&fields=name,level"
    )


def test_cached_results_fetch_once_then_reuse_refetch_when_stale_or_broken(
    cache, monkeypatch
):
    calls = []

    def fake_all(resource, edition, fields, document=None):
        calls.append((resource, edition))
        return [{"n": len(calls)}]

    monkeypatch.setattr(srd, "_all_results", fake_all)
    assert srd._cached_results("spells", "2014", "f") == [{"n": 1}]
    assert srd._cached_results("spells", "2014", "f") == [{"n": 1}]
    assert calls == [("spells", "2014")]
    path = next(cache.glob("spells-2014-*.json"))
    old = time.time() - srd.CACHE_SECONDS - 10
    os.utime(path, (old, old))
    assert srd._cached_results("spells", "2014", "f") == [{"n": 2}]
    path.write_text("{not json")
    assert srd._cached_results("spells", "2014", "f") == [{"n": 3}]
    assert srd._cached_results("spells", "2024", "f") == [{"n": 4}]


def test_an_unwritable_cache_does_not_stop_a_lookup(tmp_path, monkeypatch):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("x")
    monkeypatch.setattr(srd, "CACHE_DIR", blocker / "srd")
    monkeypatch.setattr(srd, "_all_results", lambda *args: [{"ok": 1}])
    assert srd._cached_results("classes", "2014", "f") == [{"ok": 1}]


# --- public loaders ---------------------------------------------------------


def test_loaders_return_normalized_entries_end_to_end(cache, monkeypatch):
    answers = {
        "classes": _classes_raw(),
        "species": _species_raw(),
        "spells": [{"name": "Light", "level": 0, "classes": [{"name": "Wizard"}]}],
    }

    def fake_fetch(url):
        resource = url.removeprefix(srd.API).split("/")[0]
        return {"results": answers[resource], "next": None}

    monkeypatch.setattr(srd, "_fetch_json", fake_fetch)
    assert [c["name"] for c in srd.load_classes("2014")] == ["Fighter", "Wizard"]
    assert [s["name"] for s in srd.load_species("2024")] == ["Elf", "Human"]
    assert srd.load_spells("2014") == [
        {"name": "Light", "level": 0, "classes": ["Wizard"]}
    ]
    assert (
        json.loads(next(cache.glob("spells-2014-*.json")).read_text())[0]["name"]
        == "Light"
    )


# --- spell details, conditions, slugs ---------------------------------------


def test_slugify_makes_stable_url_safe_ids():
    cases = [
        ("Hunter's Mark", "hunters-mark"),
        ("Tasha\u2019s Hideous Laughter", "tashas-hideous-laughter"),
        ("Antipathy/Sympathy", "antipathy-sympathy"),
        ("  Acid   Arrow ", "acid-arrow"),
        ("Poisoned", "poisoned"),
    ]
    for name, slug in cases:
        assert srd.slugify(name) == slug, name


def test_casting_time_reads_naturally():
    cases = [
        ("action", "Action"),
        ("bonus-action", "Bonus action"),
        ("1minute", "1 minute"),
        ("10minutes", "10 minutes"),
        ("8hours", "8 hours"),
        (None, ""),
    ]
    for raw, expected in cases:
        assert srd._casting_time(raw) == expected, raw


def test_capitalized_only_touches_the_first_letter():
    assert srd._capitalized("instantaneous") == "Instantaneous"
    assert srd._capitalized("Up to 1 minute") == "Up to 1 minute"
    assert srd._capitalized(None) == ""


def test_components_list_v_s_and_m_with_the_material():
    full = {"verbal": True, "somatic": True, "material": True}
    assert (
        srd._components({**full, "material_specified": "A pearl. "})
        == "V, S, M (A pearl)"
    )
    assert srd._components(full) == "V, S, M"
    assert srd._components({"verbal": True}) == "V"
    assert srd._components({}) == ""


def _raw_spell(**overrides):
    spell = {
        "name": "Hunter's Mark",
        "level": 1,
        "school": {"name": "Divination"},
        "casting_time": "bonus-action",
        "range_text": "90 feet",
        "duration": "1 hour",
        "verbal": True,
        "concentration": True,
        "desc": "You mark a creature.",
        "higher_level": None,
        "classes": [{"name": "Ranger"}],
    }
    return {**spell, **overrides}


def test_spell_detail_collects_everything_the_rules_page_shows():
    assert srd._spell_detail(_raw_spell()) == {
        "slug": "hunters-mark",
        "name": "Hunter's Mark",
        "level": 1,
        "school": "Divination",
        "casting_time": "Bonus action",
        "range": "90 feet",
        "components": "V",
        "duration": "1 hour",
        "concentration": True,
        "ritual": False,
        "classes": ["Ranger"],
        "text": "You mark a creature.",
        "higher": "",
    }
    bare = srd._spell_detail({"name": "Odd", "level": 0})
    assert bare["school"] == "" and bare["classes"] == [] and bare["text"] == ""


def test_condition_entries_use_the_wording_of_the_chosen_edition_only():
    raw = [
        {
            "name": "Poisoned",
            "descriptions": [
                {"document": "a5e-ag", "desc": "a5e text"},
                {"document": "srd-2014", "desc": "old text"},
                {"document": "srd-2024", "desc": "new text"},
            ],
        },
        {"name": "Bloodied", "descriptions": [{"document": "a5e-ag", "desc": "x"}]},
        {"name": "Blinded", "descriptions": None},
    ]
    assert srd._condition_entries(raw, "2024") == [
        {"slug": "poisoned", "name": "Poisoned", "text": "new text"}
    ]
    assert srd._condition_entries(raw, "2014")[0]["text"] == "old text"


def test_detail_loaders_use_the_right_documents_and_honor_refresh(cache, monkeypatch):
    urls = []

    def fake_fetch(url):
        urls.append(url)
        if "/conditions/" in url:
            raw = [
                {
                    "name": "Poisoned",
                    "descriptions": [{"document": "srd-2014", "desc": "t"}],
                }
            ]
        else:
            raw = [_raw_spell(), _raw_spell(name="Bless", level=1)]
        return {"results": raw, "next": None}

    monkeypatch.setattr(srd, "_fetch_json", fake_fetch)
    assert [s["name"] for s in srd.load_spell_details("2014")] == [
        "Bless",
        "Hunter's Mark",
    ]
    assert srd.load_conditions("2014")[0]["slug"] == "poisoned"
    assert "document__key=srd-2014" in urls[0] and "document__key=core" in urls[1]
    srd.load_spell_details("2014")
    assert len(urls) == 2  # served from the cache
    srd.load_spell_details("2014", refresh=True)
    assert len(urls) == 3
