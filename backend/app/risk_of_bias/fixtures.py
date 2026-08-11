DEMONSTRATION_RCT_INSTRUMENT = {
    "name": "Demonstration randomized-study bias instrument",
    "version_label": "DEMO-RCT-1",
    "guidance": "Framework demonstration only; this is not a complete implementation of RoB 2.",
    "applicable_study_designs": ["RANDOMIZED_CONTROLLED_TRIAL"],
    "answer_choices": [
        {"value": "YES", "label": "Yes"},
        {"value": "PROBABLY_YES", "label": "Probably yes"},
        {"value": "PROBABLY_NO", "label": "Probably no"},
        {"value": "NO", "label": "No"},
        {"value": "NO_INFORMATION", "label": "No information", "missingness": True},
        {"value": "NOT_APPLICABLE", "label": "Not applicable", "missingness": True},
    ],
    "domain_judgment_choices": [
        {"value": "LOW", "label": "Low"},
        {"value": "SOME_CONCERNS", "label": "Some concerns"},
        {"value": "HIGH", "label": "High"},
    ],
    "overall_judgment_choices": [
        {"value": "LOW", "label": "Low"},
        {"value": "SOME_CONCERNS", "label": "Some concerns"},
        {"value": "HIGH", "label": "High"},
    ],
    "domains": [
        {
            "key": "RANDOMIZATION",
            "label": "Randomization process",
            "questions": [
                {"key": "RANDOM_SEQUENCE", "text": "Was the allocation sequence random?"},
                {"key": "ALLOCATION_CONCEALED", "text": "Was allocation concealed?"},
            ],
            "rule": {
                "type": "ANSWER_SEVERITY",
                "answer_mapping": {
                    "YES": "LOW",
                    "PROBABLY_YES": "LOW",
                    "PROBABLY_NO": "SOME_CONCERNS",
                    "NO": "HIGH",
                    "NO_INFORMATION": "SOME_CONCERNS",
                    "NOT_APPLICABLE": "LOW",
                },
                "severity_order": ["LOW", "SOME_CONCERNS", "HIGH"],
            },
        },
        {
            "key": "MISSING_OUTCOME_DATA",
            "label": "Missing outcome data",
            "questions": [
                {"key": "OUTCOME_DATA_COMPLETE", "text": "Were outcome data sufficiently complete?"}
            ],
            "rule": {
                "type": "ANSWER_SEVERITY",
                "answer_mapping": {
                    "YES": "LOW",
                    "PROBABLY_YES": "LOW",
                    "PROBABLY_NO": "SOME_CONCERNS",
                    "NO": "HIGH",
                    "NO_INFORMATION": "SOME_CONCERNS",
                    "NOT_APPLICABLE": "LOW",
                },
                "severity_order": ["LOW", "SOME_CONCERNS", "HIGH"],
            },
        },
    ],
    "overall_rule": {
        "type": "MAX_DOMAIN_SEVERITY",
        "domain_mapping": {"LOW": "LOW", "SOME_CONCERNS": "SOME_CONCERNS", "HIGH": "HIGH"},
        "severity_order": ["LOW", "SOME_CONCERNS", "HIGH"],
    },
}
