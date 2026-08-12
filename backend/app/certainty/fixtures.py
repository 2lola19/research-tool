GRADE_COMPATIBLE_FOUNDATION: dict[str, object] = {
    "name": "GRADE-compatible certainty foundation",
    "version_label": "Foundation 1",
    "guidance": "Structured human judgment foundation; not complete official GRADE guidance.",
    "starting_rules": {
        "RANDOMIZED": "HIGH",
        "OBSERVATIONAL": "LOW",
        "MIXED": "LOW",
        "OTHER": "LOW",
    },
    "domains": [
        {
            "key": key,
            "label": label,
            "direction": "DOWNGRADE",
            "choices": [
                {"value": "NO_DOWNGRADE", "label": "No downgrade", "magnitude": 0},
                {"value": "DOWNGRADE_ONE", "label": "Downgrade one level", "magnitude": 1},
                {"value": "DOWNGRADE_TWO", "label": "Downgrade two levels", "magnitude": 2},
            ],
        }
        for key, label in (
            ("RISK_OF_BIAS", "Risk of bias"),
            ("INCONSISTENCY", "Inconsistency"),
            ("INDIRECTNESS", "Indirectness"),
            ("IMPRECISION", "Imprecision"),
            ("PUBLICATION_BIAS", "Publication bias"),
        )
    ]
    + [
        {
            "key": key,
            "label": label,
            "direction": "UPGRADE",
            "choices": [
                {"value": "NO_UPGRADE", "label": "No upgrade", "magnitude": 0},
                {"value": "UPGRADE_ONE", "label": "Upgrade one level", "magnitude": 1},
                {"value": "UPGRADE_TWO", "label": "Upgrade two levels", "magnitude": 2},
            ],
        }
        for key, label in (
            ("LARGE_EFFECT", "Large effect"),
            ("DOSE_RESPONSE", "Dose-response gradient"),
            ("RESIDUAL_CONFOUNDING", "Residual confounding"),
        )
    ],
}
