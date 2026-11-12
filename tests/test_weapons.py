from trackcod.weapons import WeaponRegistry


def test_registry_from_site(meta):
    r = WeaponRegistry.from_meta(meta, [])
    assert r.match("ISO NI HTSHADE") == "ISO NIGHTSHADE" and r.category("ISO NIGHTSHADE") == "Mitraillette"
    assert len(r.weapons()) == 35 and r.match("CARTES DE VISITE") is None


def test_observe_learns_after_two_concordant_reads():
    r = WeaponRegistry([], [])
    assert r.observe("NOUVELLE ARME X") is None
    assert r.observe("Nouvelle Arme X") == "NOUVELLE ARME X" and "NOUVELLE ARME X" in r.learned
    assert r.match("nouvelle arme x") == "NOUVELLE ARME X"


def test_observe_known_weapon_immediately(meta):
    assert WeaponRegistry.from_meta(meta, []).observe("iso nightshade") == "ISO NIGHTSHADE"


def test_observe_rejects_noise():
    r = WeaponRegistry([], [])
    assert r.observe("a-") is None and r.observe("a-") is None and r.learned == []


def test_offline_registry_without_meta():
    r = WeaponRegistry.from_meta(None, ["KG-7 VULCAN"])
    assert r.match("KG-7 VULCAN") == "KG-7 VULCAN" and r.category("KG-7 VULCAN") == ""


def test_update_site_keeps_learned(meta):
    r = WeaponRegistry([], ["NOUVELLE ARME"])
    r.update_site(meta)
    assert r.match("ISO NIGHTSHADE") == "ISO NIGHTSHADE" and r.match("NOUVELLE ARME") == "NOUVELLE ARME"


def test_garbled_site_name_is_not_learned(meta):
    r = WeaponRegistry.from_meta(meta, [])
    assert r.observe("ISQ NIGHTSHAQE ZZ") is None and r.observe("ISQ NIGHTSHAQE ZZ") is None and r.learned == []


def test_learned_keeps_most_readable_form():
    r = WeaponRegistry([], [])
    r.observe("NOUVELLE ARME X")
    assert r.observe("NOUVELLE ARME X.") in ("NOUVELLE ARME X", "NOUVELLE ARME X.")
    r2 = WeaponRegistry([], [])
    r2.observe("N0UVELLE ARME")
    assert r2.observe("NOUVELLE ARME") == "NOUVELLE ARME"


def test_update_site_prunes_learned_site_weapons(meta):
    r = WeaponRegistry([], ["ISO NIGHTSHADE", "NOUVELLE ARME"])
    r.update_site(meta)
    assert r.learned == ["NOUVELLE ARME"]


def test_add_typed_name():
    r = WeaponRegistry([], [])
    assert r.add(" Nouvelle Arme ") == "NOUVELLE ARME" and r.match("nouvelle arme") == "NOUVELLE ARME"
    assert r.add("  ") is None
