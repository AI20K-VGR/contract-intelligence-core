# P3 — bộ phân loại cặp dev

Trạng thái: `OBSERVED`.

Ground truth: gpt-labels (approved=false), dev.
Prompt: `pairs-v1`; vòng chỉnh: 0.
Model phục vụ: claude-sonnet-4-6.


Số đo (k/n, Wilson95, cụm, token, latency):

```json
{
  "by_label": {
    "CONFLICT": {
      "covered": 0,
      "denominator": 0,
      "direction_accuracy": null,
      "passed": 0,
      "precision_conservative": {
        "denominator": 0,
        "passed": 0,
        "rate": null,
        "wilson95": [
          0.0,
          1.0
        ]
      },
      "precision_observed": {
        "denominator": 0,
        "passed": 0,
        "rate": null,
        "wilson95": [
          0.0,
          1.0
        ]
      },
      "precision_weighted": null,
      "recall_observed": {
        "denominator": 5,
        "passed": 0,
        "rate": 0.0,
        "wilson95": [
          0.0,
          0.4345
        ]
      },
      "recall_weighted": null
    },
    "DUPLICATE": {
      "covered": 1,
      "denominator": 1,
      "direction_accuracy": null,
      "passed": 0,
      "precision_conservative": {
        "denominator": 1,
        "passed": 0,
        "rate": 0.0,
        "wilson95": [
          0.0,
          0.7935
        ]
      },
      "precision_observed": {
        "denominator": 1,
        "passed": 0,
        "rate": 0.0,
        "wilson95": [
          0.0,
          0.7935
        ]
      },
      "precision_weighted": null,
      "recall_observed": {
        "denominator": 2,
        "passed": 0,
        "rate": 0.0,
        "wilson95": [
          0.0,
          0.6576
        ]
      },
      "recall_weighted": null
    },
    "GENERAL_SPECIFIC": {
      "covered": 9,
      "denominator": 10,
      "direction_accuracy": {
        "denominator": 4,
        "passed": 4,
        "rate": 1.0,
        "wilson95": [
          0.5101,
          1.0
        ]
      },
      "passed": 4,
      "precision_conservative": {
        "denominator": 10,
        "passed": 4,
        "rate": 0.4,
        "wilson95": [
          0.1682,
          0.6873
        ]
      },
      "precision_observed": {
        "denominator": 9,
        "passed": 4,
        "rate": 0.4444,
        "wilson95": [
          0.1888,
          0.7334
        ]
      },
      "precision_weighted": null,
      "recall_observed": {
        "denominator": 13,
        "passed": 4,
        "rate": 0.3077,
        "wilson95": [
          0.1268,
          0.5763
        ]
      },
      "recall_weighted": null
    },
    "REFERENCE": {
      "covered": 0,
      "denominator": 0,
      "direction_accuracy": {
        "denominator": 0,
        "passed": 0,
        "rate": null,
        "wilson95": [
          0.0,
          1.0
        ]
      },
      "passed": 0,
      "precision_conservative": {
        "denominator": 0,
        "passed": 0,
        "rate": null,
        "wilson95": [
          0.0,
          1.0
        ]
      },
      "precision_observed": {
        "denominator": 0,
        "passed": 0,
        "rate": null,
        "wilson95": [
          0.0,
          1.0
        ]
      },
      "precision_weighted": null,
      "recall_observed": {
        "denominator": 4,
        "passed": 0,
        "rate": 0.0,
        "wilson95": [
          0.0,
          0.4899
        ]
      },
      "recall_weighted": null
    }
  },
  "by_cluster": {
    "cl-0fa3021b56": {
      "CONFLICT": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      },
      "DUPLICATE": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      },
      "GENERAL_SPECIFIC": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 1,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "recall_weighted": null
      },
      "REFERENCE": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 1,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "recall_weighted": null
      }
    },
    "cl-1027a3caf6": {
      "CONFLICT": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      },
      "DUPLICATE": {
        "covered": 1,
        "denominator": 1,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 1,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "precision_observed": {
          "denominator": 1,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 1,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "recall_weighted": null
      },
      "GENERAL_SPECIFIC": {
        "covered": 6,
        "denominator": 7,
        "direction_accuracy": {
          "denominator": 2,
          "passed": 2,
          "rate": 1.0,
          "wilson95": [
            0.3424,
            1.0
          ]
        },
        "passed": 2,
        "precision_conservative": {
          "denominator": 7,
          "passed": 2,
          "rate": 0.2857,
          "wilson95": [
            0.0822,
            0.6411
          ]
        },
        "precision_observed": {
          "denominator": 6,
          "passed": 2,
          "rate": 0.3333,
          "wilson95": [
            0.0968,
            0.7
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 6,
          "passed": 2,
          "rate": 0.3333,
          "wilson95": [
            0.0968,
            0.7
          ]
        },
        "recall_weighted": null
      },
      "REFERENCE": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 2,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.6576
          ]
        },
        "recall_weighted": null
      }
    },
    "cl-4637ce270e": {
      "CONFLICT": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 3,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.5615
          ]
        },
        "recall_weighted": null
      },
      "DUPLICATE": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 1,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "recall_weighted": null
      },
      "GENERAL_SPECIFIC": {
        "covered": 2,
        "denominator": 2,
        "direction_accuracy": {
          "denominator": 2,
          "passed": 2,
          "rate": 1.0,
          "wilson95": [
            0.3424,
            1.0
          ]
        },
        "passed": 2,
        "precision_conservative": {
          "denominator": 2,
          "passed": 2,
          "rate": 1.0,
          "wilson95": [
            0.3424,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 2,
          "passed": 2,
          "rate": 1.0,
          "wilson95": [
            0.3424,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 2,
          "passed": 2,
          "rate": 1.0,
          "wilson95": [
            0.3424,
            1.0
          ]
        },
        "recall_weighted": null
      },
      "REFERENCE": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      }
    },
    "cl-61cf8fa90c": {
      "CONFLICT": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      },
      "DUPLICATE": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      },
      "GENERAL_SPECIFIC": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      },
      "REFERENCE": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      }
    },
    "cl-6ef7261d72": {
      "CONFLICT": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      },
      "DUPLICATE": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      },
      "GENERAL_SPECIFIC": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 1,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "recall_weighted": null
      },
      "REFERENCE": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 1,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "recall_weighted": null
      }
    },
    "cl-b8007cde81": {
      "CONFLICT": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 2,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.6576
          ]
        },
        "recall_weighted": null
      },
      "DUPLICATE": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      },
      "GENERAL_SPECIFIC": {
        "covered": 1,
        "denominator": 1,
        "direction_accuracy": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "passed": 0,
        "precision_conservative": {
          "denominator": 1,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "precision_observed": {
          "denominator": 1,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      },
      "REFERENCE": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      }
    },
    "cl-d10ad02902": {
      "CONFLICT": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      },
      "DUPLICATE": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": null,
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      },
      "GENERAL_SPECIFIC": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 3,
          "passed": 0,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.5615
          ]
        },
        "recall_weighted": null
      },
      "REFERENCE": {
        "covered": 0,
        "denominator": 0,
        "direction_accuracy": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "passed": 0,
        "precision_conservative": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "denominator": 0,
          "passed": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "recall_weighted": null
      }
    }
  },
  "cluster_intervals": {
    "CONFLICT": {
      "direction_accuracy": null,
      "precision_conservative": null,
      "precision_observed": null,
      "recall_observed": {
        "K": 2,
        "N": 5,
        "clusters_passed": 0,
        "conf": 0.95,
        "deff": null,
        "icc": null,
        "lower": 0.0,
        "method": "harness.scripts.wilson.cluster_adjusted",
        "n_eff": 2.0,
        "pass_threshold": 1.0,
        "route": "cluster-floor",
        "upper": 0.6576197724933468
      }
    },
    "DUPLICATE": {
      "direction_accuracy": null,
      "precision_conservative": {
        "K": 1,
        "N": 1,
        "clusters_passed": 0,
        "conf": 0.95,
        "deff": null,
        "icc": null,
        "lower": 0.0,
        "method": "harness.scripts.wilson.cluster_adjusted",
        "n_eff": 1.0,
        "pass_threshold": 1.0,
        "route": "cluster-floor",
        "upper": 0.7934506856227626
      },
      "precision_observed": {
        "K": 1,
        "N": 1,
        "clusters_passed": 0,
        "conf": 0.95,
        "deff": null,
        "icc": null,
        "lower": 0.0,
        "method": "harness.scripts.wilson.cluster_adjusted",
        "n_eff": 1.0,
        "pass_threshold": 1.0,
        "route": "cluster-floor",
        "upper": 0.7934506856227626
      },
      "recall_observed": {
        "K": 2,
        "N": 2,
        "clusters_passed": 0,
        "conf": 0.95,
        "deff": null,
        "icc": null,
        "lower": 0.0,
        "method": "harness.scripts.wilson.cluster_adjusted",
        "n_eff": 2.0,
        "pass_threshold": 1.0,
        "route": "cluster-floor",
        "upper": 0.6576197724933468
      }
    },
    "GENERAL_SPECIFIC": {
      "direction_accuracy": {
        "K": 2,
        "N": 4,
        "clusters_passed": 2,
        "conf": 0.95,
        "deff": null,
        "icc": null,
        "lower": 0.34238022750665315,
        "method": "harness.scripts.wilson.cluster_adjusted",
        "n_eff": 2.0,
        "pass_threshold": 1.0,
        "route": "cluster-floor",
        "upper": 1.0
      },
      "precision_conservative": {
        "K": 3,
        "N": 10,
        "clusters_passed": 1,
        "conf": 0.95,
        "deff": null,
        "icc": null,
        "lower": 0.06149194472039632,
        "method": "harness.scripts.wilson.cluster_adjusted",
        "n_eff": 3.0,
        "pass_threshold": 1.0,
        "route": "cluster-floor",
        "upper": 0.7923403991979523
      },
      "precision_observed": {
        "K": 3,
        "N": 9,
        "clusters_passed": 1,
        "conf": 0.95,
        "deff": null,
        "icc": null,
        "lower": 0.06149194472039632,
        "method": "harness.scripts.wilson.cluster_adjusted",
        "n_eff": 3.0,
        "pass_threshold": 1.0,
        "route": "cluster-floor",
        "upper": 0.7923403991979523
      },
      "recall_observed": {
        "K": 5,
        "N": 13,
        "clusters_passed": 1,
        "conf": 0.95,
        "deff": null,
        "icc": null,
        "lower": 0.036224108632430085,
        "method": "harness.scripts.wilson.cluster_adjusted",
        "n_eff": 5.0,
        "pass_threshold": 1.0,
        "route": "cluster-floor",
        "upper": 0.6244653702374746
      }
    },
    "REFERENCE": {
      "direction_accuracy": null,
      "precision_conservative": null,
      "precision_observed": null,
      "recall_observed": {
        "K": 3,
        "N": 4,
        "clusters_passed": 0,
        "conf": 0.95,
        "deff": null,
        "icc": null,
        "lower": 0.0,
        "method": "harness.scripts.wilson.cluster_adjusted",
        "n_eff": 3.0,
        "pass_threshold": 1.0,
        "route": "cluster-floor",
        "upper": 0.5614970317550454
      }
    }
  },
  "false_duplicate": {
    "observed": 1,
    "unreviewed": 0
  },
  "direction_accuracy": {
    "GENERAL_SPECIFIC": {
      "denominator": 4,
      "passed": 4,
      "rate": 1.0,
      "wilson95": [
        0.5101,
        1.0
      ]
    },
    "REFERENCE": {
      "denominator": 0,
      "passed": 0,
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
    "duplicate_value_mismatch": 0,
    "invalid_label": 0,
    "malformed": 0,
    "missing_direction": 0,
    "no_answer": 0,
    "reference_explicit": 3,
    "ungrounded_span": 3,
    "unknown_pair": 0,
    "unrelated": 21
  },
  "injection_signals": 0,
  "tokens_per_doc": {
    "pd-ae9bb69ee7": {
      "completion": 663,
      "prompt": 6089
    },
    "pd-b300e5ad70": {
      "completion": 128,
      "prompt": 4290
    },
    "pd-b6d8628d32": {
      "completion": 283,
      "prompt": 4567
    },
    "pd-bf1d9346b4": {
      "completion": 1469,
      "prompt": 13192
    },
    "pd-e0d65645f2": {
      "completion": 25,
      "prompt": 3212
    },
    "pd-eec95ad3b2": {
      "completion": 401,
      "prompt": 5963
    },
    "pd-fa299625d8": {
      "completion": 171,
      "prompt": 3655
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
    "p50": 6919.61,
    "p95": 27796.83
  }
}
```

M?t d? ?o?n DUPLICATE kh?c gold GPT dev ch?a ???c ng??i duy?t x?c nh?n; ??y l? sai kh?c v?i ng??i g?n nh?n, kh?ng ph?i b?ng ch?ng ?? ch?nh x?c nghi?p v?.
Guard multiset s? ?? ???c ki?m b?ng code; ch?a c? b?ng ch?ng cho m?t guard ng? ngh?a m?i. Gi? pairs-v1, kh?ng tune tr?n held-out, c? pairs m?c ??nh t?t.
