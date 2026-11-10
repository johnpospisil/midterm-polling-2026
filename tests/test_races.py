from mp.build.races import choose_principals, flags_for, replacement_notes


def test_choose_principals_prefers_d_then_i_and_most_polled():
    # Alaska governor (top-4): one D, three Rs; the R most often in poll headers is the principal
    nominees = {"Jonathan Kreiss-Tomkins": "D", "Bernadette Wilson": "R", "Dave Bronson": "R",
                "Treg Taylor": "R"}
    counts = {"Bernadette Wilson": 12, "Dave Bronson": 3, "Jonathan Kreiss-Tomkins": 15}
    assert choose_principals(nominees, counts) == ("Jonathan Kreiss-Tomkins", "D", "Bernadette Wilson")
    # Nebraska Senate: no Democrat, independent is the D side
    assert choose_principals({"Pete Ricketts": "R", "Dan Osborn": "I"}, {}) == ("Dan Osborn", "I", "Pete Ricketts")
    # Democrat present: an independent never becomes the D side
    assert choose_principals({"Hannah Pingree": "D", "Bobby Charles": "R", "Rick Bennett": "I"}, {}) == (
        "Hannah Pingree", "D", "Bobby Charles")
    assert choose_principals({"A": "D", "B": "D"}, {}) == (None, None, None)  # same-party contest


def test_flags():
    assert flags_for("SEN", "AK") == {"rcv": True, "top_two": False, "top_four": True}
    assert flags_for("SEN", "ME") == {"rcv": True, "top_two": False, "top_four": False}
    assert flags_for("GOV", "ME") == {"rcv": False, "top_two": False, "top_four": False}
    assert flags_for("GOV", "CA") == {"rcv": False, "top_two": True, "top_four": False}


def test_replacement_notes():
    html = ('<table class="infobox"><tr><th>Nominee</th><td>Susan Collins</td>'
            "<td>Troy Jackson (replacing Graham Platner )</td></tr></table>")
    assert replacement_notes(html) == ["Troy Jackson replacing Graham Platner"]
