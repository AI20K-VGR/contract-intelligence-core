# P3 — bộ phân loại cặp dev

Trạng thái: `OBSERVED`.

Ground truth: reviewed gold (approved=true), dev.
Evaluation gate: `PASS`; gold provenance: approved=4, unapproved=0.
P3 classifier gate: `PASS`.
Prompt: `pairs-v7`; vòng chỉnh: 0.
Model phục vụ: gpt-5.5.
Rejection reason: pair-rejections-v1.


Số đo (k/n, Wilson95, cụm, token, latency):

```json
{
  "by_label": {
    "GENERAL_SPECIFIC": {
      "denominator": 4,
      "covered": 0,
      "passed": 0,
      "precision_conservative": {
        "passed": 0,
        "denominator": 4,
        "rate": 0.0,
        "wilson95": [
          0.0,
          0.4899
        ]
      },
      "precision_observed": {
        "passed": 0,
        "denominator": 0,
        "rate": null,
        "wilson95": [
          0.0,
          1.0
        ]
      },
      "recall_observed": {
        "passed": 0,
        "denominator": 2,
        "rate": 0.0,
        "wilson95": [
          0.0,
          0.6576
        ]
      },
      "direction_accuracy": {
        "passed": 0,
        "denominator": 0,
        "rate": null,
        "wilson95": [
          0.0,
          1.0
        ]
      },
      "precision_weighted": null,
      "recall_weighted": null
    },
    "CONFLICT": {
      "denominator": 2,
      "covered": 1,
      "passed": 1,
      "precision_conservative": {
        "passed": 1,
        "denominator": 2,
        "rate": 0.5,
        "wilson95": [
          0.0945,
          0.9055
        ]
      },
      "precision_observed": {
        "passed": 1,
        "denominator": 1,
        "rate": 1.0,
        "wilson95": [
          0.2065,
          1.0
        ]
      },
      "recall_observed": {
        "passed": 1,
        "denominator": 1,
        "rate": 1.0,
        "wilson95": [
          0.2065,
          1.0
        ]
      },
      "direction_accuracy": null,
      "precision_weighted": null,
      "recall_weighted": null
    },
    "DUPLICATE": {
      "denominator": 2,
      "covered": 1,
      "passed": 1,
      "precision_conservative": {
        "passed": 1,
        "denominator": 2,
        "rate": 0.5,
        "wilson95": [
          0.0945,
          0.9055
        ]
      },
      "precision_observed": {
        "passed": 1,
        "denominator": 1,
        "rate": 1.0,
        "wilson95": [
          0.2065,
          1.0
        ]
      },
      "recall_observed": {
        "passed": 1,
        "denominator": 1,
        "rate": 1.0,
        "wilson95": [
          0.2065,
          1.0
        ]
      },
      "direction_accuracy": null,
      "precision_weighted": null,
      "recall_weighted": null
    },
    "REFERENCE": {
      "denominator": 2,
      "covered": 0,
      "passed": 0,
      "precision_conservative": {
        "passed": 0,
        "denominator": 2,
        "rate": 0.0,
        "wilson95": [
          0.0,
          0.6576
        ]
      },
      "precision_observed": {
        "passed": 0,
        "denominator": 0,
        "rate": null,
        "wilson95": [
          0.0,
          1.0
        ]
      },
      "recall_observed": {
        "passed": 0,
        "denominator": 0,
        "rate": null,
        "wilson95": [
          0.0,
          1.0
        ]
      },
      "direction_accuracy": {
        "passed": 0,
        "denominator": 0,
        "rate": null,
        "wilson95": [
          0.0,
          1.0
        ]
      },
      "precision_weighted": null,
      "recall_weighted": null
    }
  },
  "by_cluster": {
    "cl-0fa3021b56": {
      "GENERAL_SPECIFIC": {
        "denominator": 1,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 1,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      },
      "CONFLICT": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "DUPLICATE": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "REFERENCE": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      }
    },
    "cl-1027a3caf6": {
      "GENERAL_SPECIFIC": {
        "denominator": 3,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 3,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.5615
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      },
      "CONFLICT": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "DUPLICATE": {
        "denominator": 2,
        "covered": 1,
        "passed": 1,
        "precision_conservative": {
          "passed": 1,
          "denominator": 2,
          "rate": 0.5,
          "wilson95": [
            0.0945,
            0.9055
          ]
        },
        "precision_observed": {
          "passed": 1,
          "denominator": 1,
          "rate": 1.0,
          "wilson95": [
            0.2065,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 1,
          "denominator": 1,
          "rate": 1.0,
          "wilson95": [
            0.2065,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "REFERENCE": {
        "denominator": 1,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 1,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      }
    },
    "cl-4637ce270e": {
      "GENERAL_SPECIFIC": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 1,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      },
      "CONFLICT": {
        "denominator": 1,
        "covered": 1,
        "passed": 1,
        "precision_conservative": {
          "passed": 1,
          "denominator": 1,
          "rate": 1.0,
          "wilson95": [
            0.2065,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 1,
          "denominator": 1,
          "rate": 1.0,
          "wilson95": [
            0.2065,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 1,
          "denominator": 1,
          "rate": 1.0,
          "wilson95": [
            0.2065,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "DUPLICATE": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "REFERENCE": {
        "denominator": 1,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 1,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      }
    },
    "cl-61cf8fa90c": {
      "GENERAL_SPECIFIC": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      },
      "CONFLICT": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "DUPLICATE": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "REFERENCE": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      }
    },
    "cl-6ef7261d72": {
      "GENERAL_SPECIFIC": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      },
      "CONFLICT": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "DUPLICATE": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "REFERENCE": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      }
    },
    "cl-b8007cde81": {
      "GENERAL_SPECIFIC": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 1,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      },
      "CONFLICT": {
        "denominator": 1,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 1,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "DUPLICATE": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "REFERENCE": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      }
    },
    "cl-d10ad02902": {
      "GENERAL_SPECIFIC": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      },
      "CONFLICT": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "DUPLICATE": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": null,
        "precision_weighted": null,
        "recall_weighted": null
      },
      "REFERENCE": {
        "denominator": 0,
        "covered": 0,
        "passed": 0,
        "precision_conservative": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "direction_accuracy": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_weighted": null
      }
    }
  },
  "cluster_intervals": {
    "CONFLICT": {
      "precision_conservative": {
        "method": "harness.scripts.wilson.cluster_adjusted",
        "conf": 0.95,
        "route": "cluster-floor",
        "icc": null,
        "deff": null,
        "n_eff": 2.0,
        "lower": 0.09453120573423074,
        "upper": 0.9054687942657693,
        "K": 2,
        "N": 2,
        "clusters_passed": 1,
        "pass_threshold": 1.0
      },
      "precision_observed": {
        "method": "harness.scripts.wilson.cluster_adjusted",
        "conf": 0.95,
        "route": "cluster-floor",
        "icc": null,
        "deff": null,
        "n_eff": 1.0,
        "lower": 0.20654931437723745,
        "upper": 1.0,
        "K": 1,
        "N": 1,
        "clusters_passed": 1,
        "pass_threshold": 1.0
      },
      "recall_observed": {
        "method": "harness.scripts.wilson.cluster_adjusted",
        "conf": 0.95,
        "route": "cluster-floor",
        "icc": null,
        "deff": null,
        "n_eff": 1.0,
        "lower": 0.20654931437723745,
        "upper": 1.0,
        "K": 1,
        "N": 1,
        "clusters_passed": 1,
        "pass_threshold": 1.0
      },
      "direction_accuracy": null
    },
    "DUPLICATE": {
      "precision_conservative": {
        "method": "harness.scripts.wilson.cluster_adjusted",
        "conf": 0.95,
        "route": "cluster-floor",
        "icc": null,
        "deff": null,
        "n_eff": 1.0,
        "lower": 0.0,
        "upper": 0.7934506856227626,
        "K": 1,
        "N": 2,
        "clusters_passed": 0,
        "pass_threshold": 1.0
      },
      "precision_observed": {
        "method": "harness.scripts.wilson.cluster_adjusted",
        "conf": 0.95,
        "route": "cluster-floor",
        "icc": null,
        "deff": null,
        "n_eff": 1.0,
        "lower": 0.20654931437723745,
        "upper": 1.0,
        "K": 1,
        "N": 1,
        "clusters_passed": 1,
        "pass_threshold": 1.0
      },
      "recall_observed": {
        "method": "harness.scripts.wilson.cluster_adjusted",
        "conf": 0.95,
        "route": "cluster-floor",
        "icc": null,
        "deff": null,
        "n_eff": 1.0,
        "lower": 0.20654931437723745,
        "upper": 1.0,
        "K": 1,
        "N": 1,
        "clusters_passed": 1,
        "pass_threshold": 1.0
      },
      "direction_accuracy": null
    },
    "GENERAL_SPECIFIC": {
      "precision_conservative": {
        "method": "harness.scripts.wilson.cluster_adjusted",
        "conf": 0.95,
        "route": "cluster-floor",
        "icc": null,
        "deff": null,
        "n_eff": 2.0,
        "lower": 0.0,
        "upper": 0.6576197724933468,
        "K": 2,
        "N": 4,
        "clusters_passed": 0,
        "pass_threshold": 1.0
      },
      "precision_observed": null,
      "recall_observed": {
        "method": "harness.scripts.wilson.cluster_adjusted",
        "conf": 0.95,
        "route": "cluster-floor",
        "icc": null,
        "deff": null,
        "n_eff": 2.0,
        "lower": 0.0,
        "upper": 0.6576197724933468,
        "K": 2,
        "N": 2,
        "clusters_passed": 0,
        "pass_threshold": 1.0
      },
      "direction_accuracy": null
    },
    "REFERENCE": {
      "precision_conservative": {
        "method": "harness.scripts.wilson.cluster_adjusted",
        "conf": 0.95,
        "route": "cluster-floor",
        "icc": null,
        "deff": null,
        "n_eff": 2.0,
        "lower": 0.0,
        "upper": 0.6576197724933468,
        "K": 2,
        "N": 2,
        "clusters_passed": 0,
        "pass_threshold": 1.0
      },
      "precision_observed": null,
      "recall_observed": null,
      "direction_accuracy": null
    }
  },
  "false_duplicate": {
    "observed": 0,
    "unreviewed": 1
  },
  "direction_accuracy": {
    "GENERAL_SPECIFIC": {
      "passed": 0,
      "denominator": 0,
      "rate": null,
      "wilson95": [
        0.0,
        1.0
      ]
    },
    "REFERENCE": {
      "passed": 0,
      "denominator": 0,
      "rate": null,
      "wilson95": [
        0.0,
        1.0
      ]
    }
  },
  "rejected": {
    "bad_span": 0,
    "citation_invalid": 0,
    "conflict_same_span": 0,
    "duplicate_id": 0,
    "duplicate_value_mismatch": 5,
    "invalid_label": 0,
    "malformed": 0,
    "missing_direction": 0,
    "no_answer": 0,
    "reference_explicit": 0,
    "ungrounded_span": 0,
    "unknown_pair": 0,
    "unrelated": 23
  },
  "injection_signals": 0,
  "tokens_per_doc": {
    "pd-ae9bb69ee7": {
      "prompt": 3242,
      "completion": 789
    },
    "pd-b300e5ad70": {
      "prompt": 2203,
      "completion": 446
    },
    "pd-b6d8628d32": {
      "prompt": 2362,
      "completion": 683
    },
    "pd-bf1d9346b4": {
      "prompt": 6853,
      "completion": 2831
    },
    "pd-e0d65645f2": {
      "prompt": 1579,
      "completion": 39
    },
    "pd-eec95ad3b2": {
      "prompt": 3208,
      "completion": 818
    },
    "pd-fa299625d8": {
      "prompt": 1795,
      "completion": 271
    }
  },
  "calls_per_doc": {
    "pd-ae9bb69ee7": 1,
    "pd-b300e5ad70": 1,
    "pd-b6d8628d32": 1,
    "pd-bf1d9346b4": 3,
    "pd-e0d65645f2": 1,
    "pd-eec95ad3b2": 1,
    "pd-fa299625d8": 1
  },
  "latency_ms": {
    "p50": 11179.6,
    "p95": 46470.88
  }
}
```
