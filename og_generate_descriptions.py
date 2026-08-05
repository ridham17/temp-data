#!/usr/bin/env python3
"""Generate the Lululemon "Final Description" for each style and attribute level from an intermediate
JSON file, and save the results back into it.

Input JSON — a single file keyed by Style ID, with the three levels nested per style:
{
  "<style_id>": {
    "Style Name (Legacy)": "...",
    "Master Style Group": {"mandatory_description": "...", "supplemental_description": "...", ...},
    "Master Style":        {"mandatory_description": "...", "supplemental_description": "...", ...},
    "Style":               {"mandatory_description": "...", "supplemental_description": "...", ...}
  },
  ...
}

For each style and level, ONE call generates the Final Description (no batching). The result is written
back as a "final_description" field on that level, and the file is saved.

    export OPENAI_API_KEY='...'
    OPENAI_MODEL=gpt-5.1 TEMP=0 python3 generate_descriptions.py input.json [output.json]
"""
import json
import os
import sys

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.1")
TEMP = os.environ.get("TEMP", 0)
LEVELS = ["Master Style Group", "Master Style", "Style"]

PROMPT = """Act as a **Lululemon product data analyst and apparel taxonomy expert**.

Provided is the data set as below:
-Style ID (Legacy) - this indicates unique style ID values
-Style Name (Legacy) - this column has legacy names which you need to consider while generating the final description
-{LEVEL} (Mandatory) - this column has all the mandatory attribute values that needs to be compulsorily present in final description
-{LEVEL} (Supplemental) - this column has all supplemental attributes which may or may not become part of final description
-Final Description - this column is what you need to generate.

## Objective
Generate standardized, business-friendly **Final Description** that are:
- crisp
- readable
- consistent across similar products
- faithful to source data
- aligned to the training examples

## Rules to be followed
- All the attribute values which is part of {LEVEL} (Mandatory) column needs to be part of final description
- Additional values available in {LEVEL} (Supplemental) column should become part of final description only if that is available Style Name (Legacy)
- While comparing Style Name (Legacy) vs {LEVEL} (Supplemental) values please consider short forms/abbreviations as well eg: Pockets vs Pkts

## Training data
{TRAINING}

## Prediction data
{PREDICTION}

## Output Required
Return a JSON object mapping the Style ID (Legacy) to its generated Final Description:
{"<Style ID (Legacy)>": "<Final Description>"}

## Output Constraint
Return only the JSON object."""

# Training examples. Each level gives the Mandatory / Supplemental columns and the correct Final
# Description the model should learn to produce.
FEWSHOTS = [
    {
        "rid": "LW6BHCS",
        "name": 'lululemon Align™ High-Rise Crop 17"',
        "levels": {
            "Master Style Group": {"mandatory_description": "lululemon Align Tight", "supplemental_description": "",
                                   "final_description": "lululemon Align Tight"},
            "Master Style": {"mandatory_description": 'lululemon Align HR Tight 17"',
                             "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts",
                             "final_description": 'lululemon Align HR Tight Crop 17"'},
            "Style": {"mandatory_description": 'lululemon Align HR Tight 17"',
                      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts",
                      "final_description": 'lululemon Align HR Tight Crop 17"'},
        },
    },
    {
        "rid": "LW6BKKS",
        "name": 'lululemon Align™ HR Crop 23" Pockets',
        "levels": {
            "Master Style Group": {"mandatory_description": "lululemon Align Tight", "supplemental_description": "",
                                   "final_description": "lululemon Align Tight"},
            "Master Style": {"mandatory_description": 'lululemon Align HR Tight 23"',
                             "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts",
                             "final_description": 'lululemon Align HR Tight Crop 23" Pkts'},
            "Style": {"mandatory_description": 'lululemon Align HR Tight 23"',
                      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts",
                      "final_description": 'lululemon Align HR Tight Crop 23" Pkts'},
        },
    },
    {
        "rid": "LW5CWMA",
        "name": 'lululemon Align™ HR Pant 24"',
        "levels": {
            "Master Style Group": {"mandatory_description": "lululemon Align Tight", "supplemental_description": "",
                                   "final_description": "lululemon Align Tight"},
            "Master Style": {"mandatory_description": 'lululemon Align HR Tight 24" 2 AF',
                             "supplemental_description": "Tight-Fit Yoga Flat Pull On Pkts",
                             "final_description": 'lululemon Align HR Tight 24" 2 AF'},
            "Style": {"mandatory_description": 'lululemon Align HR Tight 24" 2 AF',
                      "supplemental_description": "Tight-Fit Yoga Flat Pull On Pkts",
                      "final_description": 'lululemon Align HR Tight 24" 2 AF'},
        },
    },
    {
        "rid": "LWYOGA1",
        "name": 'lululemon Align™ High-Rise Yoga Crop 17"',
        "levels": {
            "Master Style Group": {"mandatory_description": "lululemon Align Tight", "supplemental_description": "Yoga",
                                   "final_description": "lululemon Align Yoga Tight"},
            "Master Style": {"mandatory_description": 'lululemon Align HR Tight 17"',
                             "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts",
                             "final_description": 'lululemon Align HR Yoga Tight Crop 17"'},
            "Style": {"mandatory_description": 'lululemon Align HR Tight 17"',
                      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts",
                      "final_description": 'lululemon Align HR Yoga Tight Crop 17"'},
        },
    },
    {
        "rid": "LWDROP1",
        "name": 'lululemon Align™ High-Rise Tight-Fit Yoga 25" Crop Pockets',
        "levels": {
            "Master Style Group": {"mandatory_description": "lululemon Align Tight", "supplemental_description": "Yoga",
                                   "final_description": "lululemon Align Yoga Tight"},
            "Master Style": {"mandatory_description": 'lululemon Align HR Tight 25"',
                             "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts Pleated",
                             "final_description": 'lululemon Align Tight-Fit HR Yoga Tight Crop 25" Pkts'},
            "Style": {"mandatory_description": 'lululemon Align HR Tight 25"',
                      "supplemental_description": "Tight-Fit Yoga Flat Pull On Crop Pkts Pleated",
                      "final_description": 'lululemon Align Tight-Fit HR Yoga Tight Crop 25" Pkts'},
        },
    },
]

def block(level_name, style_id, style_name, mandatory, supplemental, final=None):
    lines = [f"Style ID (Legacy): {style_id}",
             f"Style Name (Legacy): {style_name}",
             f"{level_name} (Mandatory): {mandatory}",
             f"{level_name} (Supplemental): {supplemental}"]
    if final is not None:
        lines.append(f"Final Description: {final}")
    return "\n".join(lines)


def training_examples(level_name):
    blocks = []
    for shot in FEWSHOTS:
        level = shot["levels"][level_name]
        blocks.append(block(level_name, shot["rid"], shot["name"],
                            level["mandatory_description"], level["supplemental_description"],
                            level["final_description"]))
    return "\n\n".join(blocks)


def call(client, content):
    kwargs = dict(model=MODEL, messages=[{"role": "user", "content": content}],
                  response_format={"type": "json_object"})
    if TEMP is not None:
        kwargs["temperature"] = float(TEMP)
    return client.chat.completions.create(**kwargs).choices[0].message.content


def predict(client, level_name, style_id, style_name, mandatory, supplemental):
    """One call, one prediction. Returns the Final Description string."""
    prediction = block(level_name, style_id, style_name, mandatory, supplemental)
    content = (PROMPT.replace("{LEVEL}", level_name)
               .replace("{TRAINING}", training_examples(level_name))
               .replace("{PREDICTION}", prediction))

    answer = json.loads(call(client, content))
    return str(answer.get(style_id, "")).strip()


def main():
    input_path = sys.argv[1] if len(sys.argv) > 1 else "intermediate.json"
    default_output = os.path.join(os.path.dirname(input_path), "out_" + os.path.basename(input_path))
    output_path = sys.argv[2] if len(sys.argv) > 2 else default_output   # default: new "out_" file
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("set OPENAI_API_KEY")

    with open(input_path) as f:
        data = json.load(f)

    from openai import OpenAI
    client = OpenAI()

    for style_id, style in data.items():
        style_name = style.get("Style Name (Legacy)", "")
        for level_name in LEVELS:
            level = style.get(level_name)
            if not level:
                continue

            final = predict(client, level_name, style_id, style_name,
                            level.get("mandatory_description", ""),
                            level.get("supplemental_description", ""))
            level["final_description"] = final

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"{input_path} -> {output_path}: {len(data)} styles x {len(LEVELS)} levels")


if __name__ == "__main__":
    main()
