#!/usr/bin/env python3
"""Generate the Lululemon Final Description for each style and level from an intermediate JSON file
(rank-aware prompt), and save the results back into it. Self-contained.

Input JSON — single file keyed by Style ID, three levels nested per style, each level with rank-tagged
mandatory / supplemental attributes:
{
  "<style_id>": {
    "Style Name (Legacy)": "...",
    "Master Style Group": {"mandatory": {"<attr>": {"rank": <n>, "value": "..."}, ...},
                           "supplemental": {"<attr>": {"rank": <n>, "value": "..."}, ...},
                           "mandatory_description": "...",
                           "supplemental_description": "..."},
    "Master Style": {...}, "Style": {...}
  }, ...
}

One call per style (all three levels together). The generated descriptions are written back as
"final_description" on each level, and the file is saved.

    OPENAI_API_KEY=... python3 generate_descriptions_v3.py input.json [output.json]
"""
import json
import os
import sys

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
TEMP = os.environ.get("TEMP", 0)
LEVELS = ["Master Style Group", "Master Style", "Style"]
OUT_KEY = {"Master Style Group": "master_style_group_description",
           "Master Style": "master_style_description", "Style": "style_description"}


PROSE = """\
You are a Lululemon product data analyst and apparel taxonomy expert. For each product style you produce three cleansed, business-friendly descriptions — one per nested level: Master Style Group ⊆ Master Style ⊆ Style. They must be crisp, consistent across similar products, and faithful to the source attributes — never invent or paraphrase words.

INPUT (JSON). Each style has:
- "Style ID (Legacy)" — echo it back unchanged.
- "Style Name (Legacy)" — the legacy marketing name; used ONLY to decide which supplemental values qualify.
- three level objects keyed "Master Style Group", "Master Style" and "Style". Each level object has:
    - attributes: an array of {attribute, value, category, rank}, ALREADY SORTED BY RANK. rank is the position the value takes in the final description (lower rank = earlier); category is 'mandatory' or 'supplemental'.
    - mandatory_description: the mandatory values only, concatenated in rank order (reference).
    - supplemental_description: all supplemental CANDIDATE values, concatenated in rank order — a candidate list, NOT the answer; keep one only if it is in Style Name (Legacy) (reference).

Treat each value as ONE token even if it spans multiple words — never split a multi-word value into pieces.

BUILD each level's description by walking its attributes array IN THE GIVEN ORDER:
1. KEEP every 'mandatory' value — always, even if it does NOT appear in Style Name (Legacy).
2. For each 'supplemental' value, KEEP it ONLY IF the value — or a listed abbreviation of it — LITERALLY appears in Style Name (Legacy); otherwise DROP it. Do NOT keep a supplemental because it is common, expected, or merely listed. This applies at EVERY level, including Master Style Group. Evaluate EACH supplemental INDEPENDENTLY: keeping several does NOT license keeping the rest, and keeping the ones before it does not license keeping a later one. Every supplemental you keep — including the last item in the list — must ITSELF appear in Style Name (Legacy). Before you finalize a level, re-scan each supplemental you kept and confirm it is actually in the name; drop any that is not.
3. PRESERVE the given order exactly — never reorder. Emit the kept values in the EXACT left-to-right order of the attributes array, even when that order reads unusually. A kept supplemental stays in its position and may sit BETWEEN two mandatory values; never move a value to sound more natural and never group supplementals at the end.
4. Join the kept values with single spaces. Add nothing that is not a value — no connecting words, no extra punctuation.

EVIDENCE MATCH: compare case-insensitively; ignore punctuation and decorators (* ™ " and hyphens); match on word boundaries (not as a substring inside another word). Abbreviations count in BOTH directions: a value is present if the name contains the value OR its counterpart form — e.g. the value 'Long Sleeve' is present when the name says 'LS', AND the value 'LS' is present when the name says 'Long Sleeve'. Known pairs: High-Rise=HR, Mid-Rise=MR, Pockets=Pkts, Long Sleeve=LS, Short Sleeve=SS.

CONSISTENCY ACROSS LEVELS: whether a supplemental value is kept depends ONLY on Style Name (Legacy), never on the level. Make the SAME keep/drop decision for a given value at EVERY level whose attributes include it — if you keep it at one level, keep it at all of them; if you drop it at one, drop it everywhere.

NESTING: broader levels are subsets of narrower ones (Master Style Group ⊆ Master Style ⊆ Style). A value present at a broader level stays at the narrower level when its column exists there. Narrower levels may also carry level-only columns — mandatory OR supplemental — that broader levels omit (e.g. a Pocket Detail supplemental or an Embossed mandatory token present only at Style); include each such column by the SAME rules (mandatory always; supplemental only if evidenced in Style Name (Legacy)). Never invent a value at a level whose attributes array does not list it.

SELF-CHECK, THEN CORRECT (do this INSIDE your answer, in this order): FIRST emit a "verification" object — for each level, list every SUPPLEMENTAL value with "in_name": true/false stating whether that value (or a listed abbreviation) literally appears in the Style Name (Legacy). THEN build each level's description keeping ALL mandatory values and ONLY the supplementals whose in_name is true, in the given rank order. The description MUST agree with your verification — a value marked in_name:false must NOT appear in that level's description.

OUTPUT: return ONLY a JSON object {"results":[{"Style ID (Legacy)", "verification": {"Master Style Group":[{"value","in_name"}], "Master Style":[...], "Style":[...]}, "master_style_group_description","master_style_description","style_description"}]}. One element per input style, the Style ID (Legacy) echoed verbatim, no prose, no code fences.
"""


# FS1 - keep one evidenced supplemental (Crop), drop the rest; interleaved by rank
FS1 = json.loads(r'''
{
  "style_id": "LW6BHCS",
  "style": {
    "Style Name (Legacy)": "lululemon Align™ High-Rise Crop 17\"",
    "Master Style Group": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        }
      },
      "supplemental": {},
      "mandatory_description": "lululemon Align Tight",
      "supplemental_description": ""
    },
    "Master Style": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Rise": {
          "rank": 4,
          "value": "HR"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        },
        "Inseam Measure": {
          "rank": 10,
          "value": "17\""
        }
      },
      "supplemental": {
        "Fit Classification": {
          "rank": 3,
          "value": "Tight-Fit"
        },
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        },
        "Waistband Type": {
          "rank": 6,
          "value": "Flat Pull On"
        },
        "Inseam Length": {
          "rank": 9,
          "value": "Crop"
        },
        "Pocket Detail": {
          "rank": 14,
          "value": "Pkts"
        }
      },
      "mandatory_description": "lululemon Align HR Tight 17\"",
      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts"
    },
    "Style": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Rise": {
          "rank": 4,
          "value": "HR"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        },
        "Inseam Measure": {
          "rank": 10,
          "value": "17\""
        }
      },
      "supplemental": {
        "Fit Classification": {
          "rank": 3,
          "value": "Tight-Fit"
        },
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        },
        "Waistband Type": {
          "rank": 6,
          "value": "Flat Pull On"
        },
        "Inseam Length": {
          "rank": 9,
          "value": "Crop"
        },
        "Pocket Detail": {
          "rank": 14,
          "value": "Pkts"
        }
      },
      "mandatory_description": "lululemon Align HR Tight 17\"",
      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts"
    }
  },
  "answer": {
    "msg": "lululemon Align Tight",
    "ms": "lululemon Align HR Tight Crop 17\"",
    "style": "lululemon Align HR Tight Crop 17\""
  }
}
''')

# FS2 - abbreviation (Pockets -> Pkts) + two supplementals at two positions
FS2 = json.loads(r'''
{
  "style_id": "LW6BKKS",
  "style": {
    "Style Name (Legacy)": "lululemon Align™ HR Crop 23\" Pockets",
    "Master Style Group": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        }
      },
      "supplemental": {},
      "mandatory_description": "lululemon Align Tight",
      "supplemental_description": ""
    },
    "Master Style": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Rise": {
          "rank": 4,
          "value": "HR"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        },
        "Inseam Measure": {
          "rank": 10,
          "value": "23\""
        }
      },
      "supplemental": {
        "Fit Classification": {
          "rank": 3,
          "value": "Tight-Fit"
        },
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        },
        "Waistband Type": {
          "rank": 6,
          "value": "Flat Pull On"
        },
        "Inseam Length": {
          "rank": 9,
          "value": "Crop"
        },
        "Pocket Detail": {
          "rank": 14,
          "value": "Pkts"
        }
      },
      "mandatory_description": "lululemon Align HR Tight 23\"",
      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts"
    },
    "Style": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Rise": {
          "rank": 4,
          "value": "HR"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        },
        "Inseam Measure": {
          "rank": 10,
          "value": "23\""
        }
      },
      "supplemental": {
        "Fit Classification": {
          "rank": 3,
          "value": "Tight-Fit"
        },
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        },
        "Waistband Type": {
          "rank": 6,
          "value": "Flat Pull On"
        },
        "Inseam Length": {
          "rank": 9,
          "value": "Crop"
        },
        "Pocket Detail": {
          "rank": 14,
          "value": "Pkts"
        }
      },
      "mandatory_description": "lululemon Align HR Tight 23\"",
      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts"
    }
  },
  "answer": {
    "msg": "lululemon Align Tight",
    "ms": "lululemon Align HR Tight Crop 23\" Pkts",
    "style": "lululemon Align HR Tight Crop 23\" Pkts"
  }
}
''')

# FS3 - nothing evidenced in the name -> mandatory-only collapse
FS3 = json.loads(r'''
{
  "style_id": "LW5CWMA",
  "style": {
    "Style Name (Legacy)": "lululemon Align™ HR Pant 24\"",
    "Master Style Group": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        }
      },
      "supplemental": {},
      "mandatory_description": "lululemon Align Tight",
      "supplemental_description": ""
    },
    "Master Style": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Rise": {
          "rank": 4,
          "value": "HR"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        },
        "Inseam Measure": {
          "rank": 10,
          "value": "24\""
        },
        "Generation": {
          "rank": 11,
          "value": "2"
        },
        "Fit Type": {
          "rank": 22,
          "value": "AF"
        }
      },
      "supplemental": {
        "Fit Classification": {
          "rank": 3,
          "value": "Tight-Fit"
        },
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        },
        "Waistband Type": {
          "rank": 6,
          "value": "Flat Pull On"
        },
        "Pocket Detail": {
          "rank": 14,
          "value": "Pkts"
        }
      },
      "mandatory_description": "lululemon Align HR Tight 24\" 2 AF",
      "supplemental_description": "Tight-Fit Yoga Flat Pull On Pkts"
    },
    "Style": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Rise": {
          "rank": 4,
          "value": "HR"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        },
        "Inseam Measure": {
          "rank": 10,
          "value": "24\""
        },
        "Generation": {
          "rank": 11,
          "value": "2"
        },
        "Fit Type": {
          "rank": 22,
          "value": "AF"
        }
      },
      "supplemental": {
        "Fit Classification": {
          "rank": 3,
          "value": "Tight-Fit"
        },
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        },
        "Waistband Type": {
          "rank": 6,
          "value": "Flat Pull On"
        },
        "Pocket Detail": {
          "rank": 14,
          "value": "Pkts"
        }
      },
      "mandatory_description": "lululemon Align HR Tight 24\" 2 AF",
      "supplemental_description": "Tight-Fit Yoga Flat Pull On Pkts"
    }
  },
  "answer": {
    "msg": "lululemon Align Tight",
    "ms": "lululemon Align HR Tight 24\" 2 AF",
    "style": "lululemon Align HR Tight 24\" 2 AF"
  }
}
''')

# FS4 - Yoga kept at every level incl. Master Style Group; Pkts is a Style-only supplemental (Master Style != Style)
FS4 = json.loads(r'''
{
  "style_id": "LWYOGA1",
  "style": {
    "Style Name (Legacy)": "lululemon Align™ High-Rise Yoga Crop 17\" Pockets",
    "Master Style Group": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        }
      },
      "supplemental": {
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        }
      },
      "mandatory_description": "lululemon Align Tight",
      "supplemental_description": "Yoga"
    },
    "Master Style": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Rise": {
          "rank": 4,
          "value": "HR"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        },
        "Inseam Measure": {
          "rank": 10,
          "value": "17\""
        }
      },
      "supplemental": {
        "Fit Classification": {
          "rank": 3,
          "value": "Tight-Fit"
        },
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        },
        "Waistband Type": {
          "rank": 6,
          "value": "Flat Pull On"
        },
        "Inseam Length": {
          "rank": 9,
          "value": "Crop"
        }
      },
      "mandatory_description": "lululemon Align HR Tight 17\"",
      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop"
    },
    "Style": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Rise": {
          "rank": 4,
          "value": "HR"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        },
        "Inseam Measure": {
          "rank": 10,
          "value": "17\""
        }
      },
      "supplemental": {
        "Fit Classification": {
          "rank": 3,
          "value": "Tight-Fit"
        },
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        },
        "Waistband Type": {
          "rank": 6,
          "value": "Flat Pull On"
        },
        "Inseam Length": {
          "rank": 9,
          "value": "Crop"
        },
        "Pocket Detail": {
          "rank": 14,
          "value": "Pkts"
        }
      },
      "mandatory_description": "lululemon Align HR Tight 17\"",
      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts"
    }
  },
  "answer": {
    "msg": "lululemon Align Yoga Tight",
    "ms": "lululemon Align HR Yoga Tight Crop 17\"",
    "style": "lululemon Align HR Yoga Tight Crop 17\" Pkts"
  }
}
''')

# FS5 - keep-heavy: drop the supplementals NOT in the name (incl. a trailing one)
FS5 = json.loads(r'''
{
  "style_id": "LWDROP1",
  "style": {
    "Style Name (Legacy)": "lululemon Align™ High-Rise Tight-Fit Yoga 25\" Crop Pockets",
    "Master Style Group": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        }
      },
      "supplemental": {
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        }
      },
      "mandatory_description": "lululemon Align Tight",
      "supplemental_description": "Yoga"
    },
    "Master Style": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Rise": {
          "rank": 4,
          "value": "HR"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        },
        "Inseam Measure": {
          "rank": 10,
          "value": "25\""
        }
      },
      "supplemental": {
        "Fit Classification": {
          "rank": 3,
          "value": "Tight-Fit"
        },
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        },
        "Waistband Type": {
          "rank": 6,
          "value": "Flat Pull On"
        },
        "Inseam Length": {
          "rank": 9,
          "value": "Crop"
        },
        "Pocket Detail": {
          "rank": 14,
          "value": "Pkts"
        },
        "Construction Detail": {
          "rank": 15,
          "value": "Pleated"
        }
      },
      "mandatory_description": "lululemon Align HR Tight 25\"",
      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts Pleated"
    },
    "Style": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "lululemon Align"
        },
        "Rise": {
          "rank": 4,
          "value": "HR"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        },
        "Inseam Measure": {
          "rank": 10,
          "value": "25\""
        }
      },
      "supplemental": {
        "Fit Classification": {
          "rank": 3,
          "value": "Tight-Fit"
        },
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        },
        "Waistband Type": {
          "rank": 6,
          "value": "Flat Pull On"
        },
        "Inseam Length": {
          "rank": 9,
          "value": "Crop"
        },
        "Pocket Detail": {
          "rank": 14,
          "value": "Pkts"
        },
        "Construction Detail": {
          "rank": 15,
          "value": "Pleated"
        }
      },
      "mandatory_description": "lululemon Align HR Tight 25\"",
      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts Pleated"
    }
  },
  "answer": {
    "msg": "lululemon Align Yoga Tight",
    "ms": "lululemon Align Tight-Fit HR Yoga Tight Crop 25\" Pkts",
    "style": "lululemon Align Tight-Fit HR Yoga Tight Crop 25\" Pkts"
  }
}
''')

# FS6 - non-Align keep-heavy: drop Yoga (not in name); Embossed is a Style-only mandatory token (Master Style != Style)
FS6 = json.loads(r'''
{
  "style_id": "WUKEEP1",
  "style": {
    "Style Name (Legacy)": "Wunder Under™ High-Rise Tight-Fit Flat Pull On Crop 26\" Pockets Embossed",
    "Master Style Group": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "Wunder Under"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        }
      },
      "supplemental": {
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        }
      },
      "mandatory_description": "Wunder Under Tight",
      "supplemental_description": "Yoga"
    },
    "Master Style": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "Wunder Under"
        },
        "Rise": {
          "rank": 4,
          "value": "HR"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        },
        "Inseam Measure": {
          "rank": 10,
          "value": "26\""
        }
      },
      "supplemental": {
        "Fit Classification": {
          "rank": 3,
          "value": "Tight-Fit"
        },
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        },
        "Waistband Type": {
          "rank": 6,
          "value": "Flat Pull On"
        },
        "Inseam Length": {
          "rank": 9,
          "value": "Crop"
        },
        "Pocket Detail": {
          "rank": 14,
          "value": "Pkts"
        }
      },
      "mandatory_description": "Wunder Under HR Tight 26\"",
      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts"
    },
    "Style": {
      "mandatory": {
        "Branded Name": {
          "rank": 2,
          "value": "Wunder Under"
        },
        "Rise": {
          "rank": 4,
          "value": "HR"
        },
        "Silhouette": {
          "rank": 8,
          "value": "Tight"
        },
        "Inseam Measure": {
          "rank": 10,
          "value": "26\""
        },
        "Fabric Finish": {
          "rank": 12,
          "value": "Embossed"
        }
      },
      "supplemental": {
        "Fit Classification": {
          "rank": 3,
          "value": "Tight-Fit"
        },
        "Designed for Activity": {
          "rank": 5,
          "value": "Yoga"
        },
        "Waistband Type": {
          "rank": 6,
          "value": "Flat Pull On"
        },
        "Inseam Length": {
          "rank": 9,
          "value": "Crop"
        },
        "Pocket Detail": {
          "rank": 14,
          "value": "Pkts"
        }
      },
      "mandatory_description": "Wunder Under HR Tight 26\" Embossed",
      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts"
    }
  },
  "answer": {
    "msg": "Wunder Under Tight",
    "ms": "Wunder Under Tight-Fit HR Flat Pull On Tight Crop 26\" Pkts",
    "style": "Wunder Under Tight-Fit HR Flat Pull On Tight Crop 26\" Embossed Pkts"
  }
}
''')

FEWSHOTS = [FS1, FS2, FS3, FS4, FS5, FS6]


# ----------------------------------------------------------------------------
# Turning one level's stored attributes into the array the model reads.
# ----------------------------------------------------------------------------
def attributes(level):
    """Flatten a level's mandatory + supplemental attributes into a single list,
    sorted by rank. Each item is {attribute, value, category, rank}; `rank` is the
    position the value takes in the final description (lower rank = earlier), so the
    model just walks this array left-to-right. `category` says whether the value is
    always kept (mandatory) or kept only when evidenced in the name (supplemental).
    """
    items = []
    for attr, info in level.get("mandatory", {}).items():
        items.append({"attribute": attr, "value": info["value"], "category": "mandatory", "rank": int(info["rank"])})
    for attr, info in level.get("supplemental", {}).items():
        items.append({"attribute": attr, "value": info["value"], "category": "supplemental", "rank": int(info["rank"])})
    items.sort(key=lambda d: d["rank"])
    return items


# ----------------------------------------------------------------------------
# Building the exact JSON we send to the model for one style.
# ----------------------------------------------------------------------------
def style_input(style_id, style):
    """Shape one style into the input object the prompt expects: the ID, the legacy
    name (the only evidence for keeping supplementals), and the three nested levels,
    each with its pre-sorted `attributes` array plus two reference strings
    (`mandatory_description` = always-kept values; `supplemental_description` = the
    candidate list, NOT the answer)."""
    obj = {"Style ID (Legacy)": style_id, "Style Name (Legacy)": style.get("Style Name (Legacy)", "")}
    for level_name in LEVELS:
        level = style.get(level_name, {})
        supp = level.get("supplemental_description")
        if supp is None:  # older inputs may omit it; rebuild from the supplemental values in rank order
            supp = " ".join(i["value"] for i in attributes(level) if i["category"] == "supplemental")
        obj[level_name] = {"attributes": attributes(level),
                           "mandatory_description": level.get("mandatory_description", ""),
                           "supplemental_description": supp}
    return obj


# ----------------------------------------------------------------------------
# Few-shot construction. Each worked example shows the model the self-check
# ("verification") it must perform before writing, then the correct output.
# ----------------------------------------------------------------------------
_ANSWER_KEY = {"Master Style Group": "msg", "Master Style": "ms", "Style": "style"}


def verification_of(shot):
    """Build the membership self-check for a few-shot: per level, list each supplemental
    value with in_name=True/False (True iff it survived into that level's answer). This
    demonstrates the required 'verify-then-write' habit that keeps the model from
    including supplementals that aren't actually in the name."""
    verification = {}
    for level_name, answer_key in _ANSWER_KEY.items():
        final = shot["answer"][answer_key]
        supplemental = shot["style"].get(level_name, {}).get("supplemental", {})
        verification[level_name] = [
            {"value": info["value"], "in_name": info["value"] in final}
            for info in sorted(supplemental.values(), key=lambda d: d["rank"])
        ]
    return verification


def few_shot_example(shot):
    """Render one few-shot as an INPUT/OUTPUT pair of JSON, the same format we ask the
    model to produce (verification first, then the three level descriptions)."""
    inp = json.dumps(style_input(shot["style_id"], shot["style"]), ensure_ascii=False)
    out = json.dumps({"Style ID (Legacy)": shot["style_id"],
                      "verification": verification_of(shot),
                      "master_style_group_description": shot["answer"]["msg"],
                      "master_style_description": shot["answer"]["ms"],
                      "style_description": shot["answer"]["style"]}, ensure_ascii=False)
    return "INPUT: " + inp + "\nOUTPUT: " + out


# The full system message = the rules (PROSE) followed by the six worked examples.
SYSTEM = (PROSE.rstrip() + "\n\nWorked examples (input JSON, then the correct output):\n\n"
          + "\n\n".join(few_shot_example(s) for s in FEWSHOTS))


def call(client, user_content):
    """One chat completion, forced to return a JSON object."""
    kwargs = dict(model=MODEL, messages=[{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": user_content}],
                  response_format={"type": "json_object"})
    if TEMP is not None:
        kwargs["temperature"] = float(TEMP)
    return client.chat.completions.create(**kwargs).choices[0].message.content


def descriptions_from(raw_json):
    """Pull the per-level descriptions out of the model's JSON reply, tolerating either
    a bare object or a {"results": [...]} wrapper."""
    parsed = json.loads(raw_json)
    results = parsed.get("results") or [parsed]
    return results[0] if results else {}


def main():
    # Args: input path (default intermediate.json) and optional output path
    # (default out_<input> next to the input).
    input_path = sys.argv[1] if len(sys.argv) > 1 else "intermediate.json"
    default_output = os.path.join(os.path.dirname(input_path), "out_" + os.path.basename(input_path))
    output_path = sys.argv[2] if len(sys.argv) > 2 else default_output
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("Please set OPENAI_API_KEY (or add it to a .env file next to this script).")

    with open(input_path) as f:
        data = json.load(f)

    from openai import OpenAI
    client = OpenAI()

    # One call per style; each call produces all three level descriptions together so
    # they stay mutually consistent. Results are written back onto the input structure.
    total, failed = len(data), []
    for i, (style_id, style) in enumerate(data.items(), 1):
        print("[%d/%d] %s" % (i, total, style_id), flush=True)
        try:
            user = "INPUT: " + json.dumps(style_input(style_id, style), ensure_ascii=False)
            result = descriptions_from(call(client, user))
            for level_name in LEVELS:
                if isinstance(style.get(level_name), dict):
                    style[level_name]["final_description"] = str(result.get(OUT_KEY[level_name], "")).strip()
        except Exception as exc:  # keep going so one bad style can't lose the whole run
            failed.append(style_id)
            print("    ! failed: %s" % exc, file=sys.stderr)

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("\nDone: %d styles -> %s" % (total, output_path))
    if failed:
        print("Failed on %d style(s): %s" % (len(failed), ", ".join(failed)), file=sys.stderr)


if __name__ == "__main__":
    main()
