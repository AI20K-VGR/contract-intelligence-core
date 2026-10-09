# P5 — bake-off cặp hợp đồng

Khuyến nghị: `HUMAN_DECISION`. Đo trên mẫu HĐ công khai.

Precision bảo thủ dùng cho cổng; 1/π chỉ báo và không có khoảng tin cậy. Đồng thuận GPT↔người là cận trên vì người duyệt thấy nhãn GPT. Không có người gán mù thứ hai.

Run1 C 10/11, B 8/11, E precision 11/32 chỉ định hướng; có thể dùng GPT và khác dữ liệu.

```json
{
  "decision": {
    "verdict": "HUMAN_DECISION",
    "recommendation_only": true,
    "thresholds_source": "review_policy.py",
    "thresholds": {
      "min_n": 60,
      "min_wilson_lower": 0.85
    },
    "decisions_sha256": "1271c998e07c6085345522e0da394b293ae6de6ea19a03b20962170e3f805a64",
    "per_label": {
      "GENERAL_SPECIFIC": {
        "trial": 1,
        "k": 3,
        "n": 28,
        "rate": 0.10714285714285714,
        "wilson_lower": 0.03711769205479949,
        "wilson_upper": 0.2719622536765708,
        "method": "wilson",
        "conf": 0.95,
        "cluster_lower": 0.0,
        "precision_observed": {
          "passed": 3,
          "denominator": 17,
          "rate": 0.1765,
          "wilson95": [
            0.0619,
            0.4103
          ]
        },
        "precision_weighted": 0.1415,
        "recall_observed": {
          "passed": 3,
          "denominator": 34,
          "rate": 0.0882,
          "wilson95": [
            0.0305,
            0.2296
          ]
        },
        "recall_weighted": 0.0882,
        "passed": false,
        "min_n_needed": null,
        "min_n_all_pass": 22,
        "additional_docs_estimate": null,
        "sizing_note": "Ước tính giữ tỷ lệ đo, dùng floor(p*n); null: chưa có cỡ hữu hạn được chứng minh. all-pass là trường hợp tốt nhất."
      },
      "CONFLICT": {
        "trial": 1,
        "k": 0,
        "n": 0,
        "rate": null,
        "wilson_lower": 0.0,
        "wilson_upper": 1.0,
        "method": "wilson",
        "conf": 0.95,
        "cluster_lower": 0,
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "passed": 0,
          "denominator": 30,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.1135
          ]
        },
        "recall_weighted": 0.0,
        "passed": false,
        "min_n_needed": null,
        "min_n_all_pass": 22,
        "additional_docs_estimate": null,
        "sizing_note": "Ước tính giữ tỷ lệ đo, dùng floor(p*n); null: chưa có cỡ hữu hạn được chứng minh. all-pass là trường hợp tốt nhất."
      },
      "DUPLICATE": {
        "trial": 1,
        "k": 0,
        "n": 0,
        "rate": null,
        "wilson_lower": 0.0,
        "wilson_upper": 1.0,
        "method": "wilson",
        "conf": 0.95,
        "cluster_lower": 0,
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "passed": 0,
          "denominator": 29,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.117
          ]
        },
        "recall_weighted": 0.0,
        "passed": false,
        "min_n_needed": null,
        "min_n_all_pass": 22,
        "additional_docs_estimate": null,
        "sizing_note": "Ước tính giữ tỷ lệ đo, dùng floor(p*n); null: chưa có cỡ hữu hạn được chứng minh. all-pass là trường hợp tốt nhất."
      },
      "REFERENCE": {
        "trial": 1,
        "k": 0,
        "n": 0,
        "rate": null,
        "wilson_lower": 0.0,
        "wilson_upper": 1.0,
        "method": "wilson",
        "conf": 0.95,
        "cluster_lower": 0,
        "precision_observed": {
          "passed": 0,
          "denominator": 0,
          "rate": null,
          "wilson95": [
            0.0,
            1.0
          ]
        },
        "precision_weighted": null,
        "recall_observed": {
          "passed": 0,
          "denominator": 8,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.3244
          ]
        },
        "recall_weighted": 0.0,
        "passed": false,
        "min_n_needed": null,
        "min_n_all_pass": 22,
        "additional_docs_estimate": null,
        "sizing_note": "Ước tính giữ tỷ lệ đo, dùng floor(p*n); null: chưa có cỡ hữu hạn được chứng minh. all-pass là trường hợp tốt nhất."
      }
    },
    "weighted_discrepancies": [],
    "mcnemar": {
      "C_vs_B": {
        "b": 1,
        "c": 0,
        "n_items": 101,
        "method": "mcnemar-wilson",
        "n_disc": 1,
        "lower": 0.20654931437723745,
        "upper": 1.0,
        "conclusive": false
      },
      "C_vs_E": {
        "b": 0,
        "c": 6,
        "n_items": 101,
        "method": "mcnemar-wilson",
        "n_disc": 6,
        "lower": 0.0,
        "upper": 0.3903342879021653,
        "conclusive": true
      }
    },
    "feasibility": {
      "expected_n": {
        "GENERAL_SPECIFIC": 45.78947368421052,
        "CONFLICT": 0.0,
        "DUPLICATE": 4.578947368421052,
        "REFERENCE": 0.0
      },
      "status": "E retained",
      "skipped_variants": {}
    },
    "variants_run": [
      "C",
      "B",
      "E"
    ],
    "budget_blocked_variants": [
      "E"
    ]
  },
  "scoreboard": {
    "C": {
      "recall_any_trials": [
        {
          "passed": 3,
          "denominator": 101,
          "rate": 0.0297,
          "wilson95": [
            0.0102,
            0.0837
          ]
        },
        {
          "passed": 4,
          "denominator": 101,
          "rate": 0.0396,
          "wilson95": [
            0.0155,
            0.0974
          ]
        }
      ],
      "spread": 0.009900000000000003,
      "over_budget": false
    },
    "B": {
      "recall_any_trials": [
        {
          "passed": 2,
          "denominator": 101,
          "rate": 0.0198,
          "wilson95": [
            0.0054,
            0.0693
          ]
        },
        {
          "passed": 3,
          "denominator": 101,
          "rate": 0.0297,
          "wilson95": [
            0.0102,
            0.0837
          ]
        }
      ],
      "spread": 0.009899999999999999,
      "over_budget": false
    },
    "E": {
      "recall_any_trials": [
        {
          "passed": 9,
          "denominator": 101,
          "rate": 0.0891,
          "wilson95": [
            0.0476,
            0.1607
          ]
        },
        {
          "passed": 9,
          "denominator": 101,
          "rate": 0.0891,
          "wilson95": [
            0.0476,
            0.1607
          ]
        }
      ],
      "spread": 0.0,
      "over_budget": true
    }
  },
  "method": "wilson 95%",
  "labeler_calibration": {
    "by_stratum": {
      "S3": {
        "UNRELATED": {
          "UNRELATED": 49
        },
        "CONFLICT": {
          "CONFLICT": 3
        },
        "GENERAL_SPECIFIC": {
          "GENERAL_SPECIFIC": 16
        },
        "REFERENCE": {
          "REFERENCE": 4
        }
      },
      "S1": {
        "UNRELATED": {
          "UNRELATED": 11
        },
        "DUPLICATE": {
          "DUPLICATE": 28
        },
        "GENERAL_SPECIFIC": {
          "GENERAL_SPECIFIC": 16
        },
        "CONFLICT": {
          "CONFLICT": 25
        }
      },
      "S2": {
        "UNRELATED": {
          "UNRELATED": 10
        },
        "DUPLICATE": {
          "DUPLICATE": 1
        },
        "REFERENCE": {
          "REFERENCE": 1
        }
      },
      "S4": {
        "UNRELATED": {
          "UNRELATED": 10
        },
        "GENERAL_SPECIFIC": {
          "GENERAL_SPECIFIC": 2
        },
        "CONFLICT": {
          "CONFLICT": 2
        },
        "REFERENCE": {
          "REFERENCE": 3
        }
      }
    },
    "overall": {
      "UNRELATED": {
        "UNRELATED": 80
      },
      "DUPLICATE": {
        "DUPLICATE": 29
      },
      "GENERAL_SPECIFIC": {
        "GENERAL_SPECIFIC": 34
      },
      "CONFLICT": {
        "CONFLICT": 30
      },
      "REFERENCE": {
        "REFERENCE": 8
      }
    },
    "agreement": {
      "passed": 181,
      "denominator": 181,
      "rate": 1.0,
      "wilson95": [
        0.9792,
        1.0
      ]
    },
    "note": "Đồng thuận GPT↔người là cận trên: người duyệt thấy nhãn GPT khi duyệt (không có người gán mù thứ hai).",
    "judge_screen": {
      "GENERAL_SPECIFIC": {
        "TP": 34,
        "FN": 0,
        "TN": 147,
        "FP": 0,
        "sens": 1.0,
        "spec": 1.0,
        "sens_ci": [
          0.8984854458466762,
          1.0
        ],
        "spec_ci": [
          0.9745331366407661,
          1.0
        ],
        "youden_j": 1.0,
        "verdict": "ok",
        "bias_direction": null,
        "n_calib": 181
      },
      "CONFLICT": {
        "TP": 30,
        "FN": 0,
        "TN": 151,
        "FP": 0,
        "sens": 1.0,
        "spec": 1.0,
        "sens_ci": [
          0.8864866068260314,
          1.0
        ],
        "spec_ci": [
          0.9751910189302563,
          1.0
        ],
        "youden_j": 1.0,
        "verdict": "ok",
        "bias_direction": null,
        "n_calib": 181
      },
      "DUPLICATE": {
        "TP": 29,
        "FN": 0,
        "TN": 152,
        "FP": 0,
        "sens": 1.0,
        "spec": 1.0,
        "sens_ci": [
          0.8830302015002593,
          1.0
        ],
        "spec_ci": [
          0.9753502126471109,
          1.0
        ],
        "youden_j": 1.0,
        "verdict": "ok",
        "bias_direction": null,
        "n_calib": 181
      },
      "REFERENCE": {
        "TP": 8,
        "FN": 0,
        "TN": 173,
        "FP": 0,
        "sens": 1.0,
        "spec": 1.0,
        "sens_ci": [
          0.6755924351161198,
          1.0
        ],
        "spec_ci": [
          0.9782773855954833,
          1.0
        ],
        "youden_j": 1.0,
        "verdict": "ok",
        "bias_direction": null,
        "n_calib": 181
      }
    },
    "upper_bound_only": true
  },
  "precision_difference": {
    "C_vs_B": {
      "GENERAL_SPECIFIC": {
        "diff": -0.026190476190476195,
        "lower": -0.2814688506488209,
        "upper": 0.1645314162796372,
        "conclusive": false
      },
      "CONFLICT": {
        "diff": 0.0,
        "lower": -1.0,
        "upper": 1.0,
        "conclusive": false
      },
      "DUPLICATE": {
        "diff": 0.0,
        "lower": -1.0,
        "upper": 1.0,
        "conclusive": false
      },
      "REFERENCE": {
        "diff": 0.0,
        "lower": -1.0,
        "upper": 1.0,
        "conclusive": false
      }
    },
    "C_vs_E": {
      "GENERAL_SPECIFIC": {
        "diff": -0.05612244897959183,
        "lower": -0.20123396034260105,
        "upper": 0.12627765701044597,
        "conclusive": false
      },
      "CONFLICT": {
        "diff": 0.0,
        "lower": -1.0,
        "upper": 1.0,
        "conclusive": false
      },
      "DUPLICATE": {
        "diff": 0.0,
        "lower": -1.0,
        "upper": 1.0,
        "conclusive": false
      },
      "REFERENCE": {
        "diff": -0.1111111111111111,
        "lower": -0.43499970557665596,
        "upper": 0.8930408341493583,
        "conclusive": false
      }
    }
  },
  "dev_tuning_rounds": {
    "prompt": 0,
    "lexicon": 0
  },
  "heldout_trial_count": 6,
  "trials": [
    {
      "variant": "C",
      "trial": 1,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 28,
          "covered": 17,
          "passed": 3,
          "precision_conservative": {
            "passed": 3,
            "denominator": 28,
            "rate": 0.1071,
            "wilson95": [
              0.0371,
              0.272
            ]
          },
          "precision_observed": {
            "passed": 3,
            "denominator": 17,
            "rate": 0.1765,
            "wilson95": [
              0.0619,
              0.4103
            ]
          },
          "recall_observed": {
            "passed": 3,
            "denominator": 34,
            "rate": 0.0882,
            "wilson95": [
              0.0305,
              0.2296
            ]
          },
          "direction_accuracy": {
            "passed": 1,
            "denominator": 3,
            "rate": 0.3333,
            "wilson95": [
              0.0615,
              0.7923
            ]
          },
          "precision_weighted": 0.1415,
          "recall_weighted": 0.0882
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
            "denominator": 30,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.1135
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": null,
          "recall_weighted": 0.0
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
            "denominator": 29,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.117
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": null,
          "recall_weighted": 0.0
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
            "denominator": 8,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.3244
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
          "recall_weighted": 0.0
        }
      },
      "by_stratum": {
        "S1": {
          "GENERAL_SPECIFIC": {
            "denominator": 10,
            "covered": 8,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 10,
              "rate": 0.1,
              "wilson95": [
                0.0179,
                0.4042
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 8,
              "rate": 0.125,
              "wilson95": [
                0.0224,
                0.4709
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 16,
              "rate": 0.0625,
              "wilson95": [
                0.0111,
                0.2833
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.125,
            "recall_weighted": 0.0625
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
              "denominator": 25,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1332
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 28,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1206
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "S2": {
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "S3": {
          "GENERAL_SPECIFIC": {
            "denominator": 6,
            "covered": 3,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 6,
              "rate": 0.1667,
              "wilson95": [
                0.0301,
                0.5635
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 16,
              "rate": 0.0625,
              "wilson95": [
                0.0111,
                0.2833
              ]
            },
            "direction_accuracy": {
              "passed": 1,
              "denominator": 1,
              "rate": 1.0,
              "wilson95": [
                0.2065,
                1.0
              ]
            },
            "precision_weighted": 0.3333,
            "recall_weighted": 0.0625
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "recall_weighted": 0.0
          }
        },
        "S4": {
          "GENERAL_SPECIFIC": {
            "denominator": 12,
            "covered": 6,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 12,
              "rate": 0.0833,
              "wilson95": [
                0.0149,
                0.3539
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 6,
              "rate": 0.1667,
              "wilson95": [
                0.0301,
                0.5635
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.098,
            "recall_weighted": 0.5
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
          }
        }
      },
      "by_doc": {
        "pd-0cd20d2016": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
        "pd-0dd5942e4e": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "pd-0ef7060ac8": {
          "GENERAL_SPECIFIC": {
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
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 1.0,
            "recall_weighted": 0.3333
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "pd-176a825fca": {
          "GENERAL_SPECIFIC": {
            "denominator": 14,
            "covered": 8,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 14,
              "rate": 0.0714,
              "wilson95": [
                0.0127,
                0.3147
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 8,
              "rate": 0.125,
              "wilson95": [
                0.0224,
                0.4709
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 9,
              "rate": 0.1111,
              "wilson95": [
                0.0199,
                0.435
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.082,
            "recall_weighted": 0.1111
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
              "denominator": 14,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2153
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-1c0f85fee4": {
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
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 14,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2153
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-1e78e105fc": {
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
        "pd-21d3913039": {
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
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-242e0b7a96": {
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
        "pd-2e28a08bfa": {
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
            "recall_weighted": 0.0
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
        "pd-3d8842533f": {
          "GENERAL_SPECIFIC": {
            "denominator": 3,
            "covered": 3,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
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
            "direction_accuracy": {
              "passed": 1,
              "denominator": 1,
              "rate": 1.0,
              "wilson95": [
                0.2065,
                1.0
              ]
            },
            "precision_weighted": 0.3333,
            "recall_weighted": 1.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-43cd896d78": {
          "GENERAL_SPECIFIC": {
            "denominator": 3,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 8,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3244
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-96be63cf8b": {
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
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-a3a3c94483": {
          "GENERAL_SPECIFIC": {
            "denominator": 4,
            "covered": 3,
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "recall_observed": {
              "passed": 0,
              "denominator": 6,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3903
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
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
              "denominator": 11,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2588
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 5,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4345
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 7.0,
            "lower": 0.0,
            "upper": 0.3543304350666873,
            "K": 7,
            "N": 30,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": null
        },
        "DUPLICATE": {
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 4.0,
            "lower": 0.0,
            "upper": 0.4898908364545972,
            "K": 4,
            "N": 29,
            "clusters_passed": 0,
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
            "n_eff": 7.0,
            "lower": 0.0,
            "upper": 0.3543304350666873,
            "K": 7,
            "N": 28,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 5.0,
            "lower": 0.036224108632430085,
            "upper": 0.6244653702374746,
            "K": 5,
            "N": 17,
            "clusters_passed": 1,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.6272847818146026,
            "deff": 2.311595452885078,
            "n_eff": 14.708455996296825,
            "lower": 0.011866895493268581,
            "upper": 0.2981652987378002,
            "K": 11,
            "N": 34
          },
          "direction_accuracy": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 3.0,
            "lower": 0.06149194472039632,
            "upper": 0.7923403991979523,
            "K": 3,
            "N": 3,
            "clusters_passed": 1,
            "pass_threshold": 1.0
          }
        },
        "REFERENCE": {
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 6.0,
            "lower": 0.0,
            "upper": 0.3903342879021653,
            "K": 6,
            "N": 8,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": null
        }
      },
      "recall_any": {
        "passed": 3,
        "denominator": 101,
        "rate": 0.0297,
        "wilson95": [
          0.0102,
          0.0837
        ]
      },
      "llm_calls": 28,
      "prompt_tokens": 45252,
      "completion_tokens": 9491,
      "elapsed_s": 204.675559,
      "latency_ms": {
        "p50": 9062.35,
        "p95": 36352.41
      },
      "false_duplicate": {
        "observed": 0,
        "unreviewed": 0
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
        "reference_explicit": 0,
        "ungrounded_span": 0,
        "unknown_pair": 0,
        "unrelated": 146
      },
      "injection_signals": 0,
      "over_budget": false
    },
    {
      "variant": "C",
      "trial": 2,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 29,
          "covered": 18,
          "passed": 4,
          "precision_conservative": {
            "passed": 4,
            "denominator": 29,
            "rate": 0.1379,
            "wilson95": [
              0.055,
              0.3056
            ]
          },
          "precision_observed": {
            "passed": 4,
            "denominator": 18,
            "rate": 0.2222,
            "wilson95": [
              0.09,
              0.4522
            ]
          },
          "recall_observed": {
            "passed": 4,
            "denominator": 34,
            "rate": 0.1176,
            "wilson95": [
              0.0467,
              0.2662
            ]
          },
          "direction_accuracy": {
            "passed": 1,
            "denominator": 4,
            "rate": 0.25,
            "wilson95": [
              0.0456,
              0.6994
            ]
          },
          "precision_weighted": 0.1802,
          "recall_weighted": 0.1176
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
            "denominator": 30,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.1135
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": null,
          "recall_weighted": 0.0
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
            "denominator": 29,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.117
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": null,
          "recall_weighted": 0.0
        },
        "REFERENCE": {
          "denominator": 1,
          "covered": 1,
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
            "denominator": 1,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.7935
            ]
          },
          "recall_observed": {
            "passed": 0,
            "denominator": 8,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.3244
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
          "precision_weighted": 0.0,
          "recall_weighted": 0.0
        }
      },
      "by_stratum": {
        "S1": {
          "GENERAL_SPECIFIC": {
            "denominator": 10,
            "covered": 8,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 10,
              "rate": 0.1,
              "wilson95": [
                0.0179,
                0.4042
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 8,
              "rate": 0.125,
              "wilson95": [
                0.0224,
                0.4709
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 16,
              "rate": 0.0625,
              "wilson95": [
                0.0111,
                0.2833
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.125,
            "recall_weighted": 0.0625
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
              "denominator": 25,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1332
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 28,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1206
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "S2": {
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "S3": {
          "GENERAL_SPECIFIC": {
            "denominator": 7,
            "covered": 4,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 7,
              "rate": 0.2857,
              "wilson95": [
                0.0822,
                0.6411
              ]
            },
            "precision_observed": {
              "passed": 2,
              "denominator": 4,
              "rate": 0.5,
              "wilson95": [
                0.15,
                0.85
              ]
            },
            "recall_observed": {
              "passed": 2,
              "denominator": 16,
              "rate": 0.125,
              "wilson95": [
                0.035,
                0.3602
              ]
            },
            "direction_accuracy": {
              "passed": 1,
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
              ]
            },
            "precision_weighted": 0.5,
            "recall_weighted": 0.125
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "recall_weighted": 0.0
          }
        },
        "S4": {
          "GENERAL_SPECIFIC": {
            "denominator": 12,
            "covered": 6,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 12,
              "rate": 0.0833,
              "wilson95": [
                0.0149,
                0.3539
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 6,
              "rate": 0.1667,
              "wilson95": [
                0.0301,
                0.5635
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.098,
            "recall_weighted": 0.5
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "covered": 1,
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "recall_observed": {
              "passed": 0,
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
          }
        }
      },
      "by_doc": {
        "pd-0cd20d2016": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
        "pd-0dd5942e4e": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "pd-0ef7060ac8": {
          "GENERAL_SPECIFIC": {
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
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 1.0,
            "recall_weighted": 0.3333
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "pd-176a825fca": {
          "GENERAL_SPECIFIC": {
            "denominator": 14,
            "covered": 8,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 14,
              "rate": 0.0714,
              "wilson95": [
                0.0127,
                0.3147
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 8,
              "rate": 0.125,
              "wilson95": [
                0.0224,
                0.4709
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 9,
              "rate": 0.1111,
              "wilson95": [
                0.0199,
                0.435
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.082,
            "recall_weighted": 0.1111
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
              "denominator": 14,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2153
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-1c0f85fee4": {
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
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 14,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2153
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-1e78e105fc": {
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
        "pd-21d3913039": {
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
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-242e0b7a96": {
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
        "pd-2e28a08bfa": {
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
            "recall_weighted": 0.0
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
            "denominator": 1,
            "covered": 1,
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
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
            "precision_weighted": 0.0,
            "recall_weighted": null
          }
        },
        "pd-3d8842533f": {
          "GENERAL_SPECIFIC": {
            "denominator": 3,
            "covered": 3,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
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
            "direction_accuracy": {
              "passed": 1,
              "denominator": 1,
              "rate": 1.0,
              "wilson95": [
                0.2065,
                1.0
              ]
            },
            "precision_weighted": 0.3333,
            "recall_weighted": 1.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-43cd896d78": {
          "GENERAL_SPECIFIC": {
            "denominator": 3,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 8,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3244
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-96be63cf8b": {
          "GENERAL_SPECIFIC": {
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
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 1.0,
            "recall_weighted": 1.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-a3a3c94483": {
          "GENERAL_SPECIFIC": {
            "denominator": 4,
            "covered": 3,
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "recall_observed": {
              "passed": 0,
              "denominator": 6,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3903
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
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
              "denominator": 11,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2588
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 5,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4345
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 7.0,
            "lower": 0.0,
            "upper": 0.3543304350666873,
            "K": 7,
            "N": 30,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": null
        },
        "DUPLICATE": {
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 4.0,
            "lower": 0.0,
            "upper": 0.4898908364545972,
            "K": 4,
            "N": 29,
            "clusters_passed": 0,
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
            "n_eff": 8.0,
            "lower": 0.022417491450056726,
            "upper": 0.4708881822128534,
            "K": 8,
            "N": 29,
            "clusters_passed": 1,
            "pass_threshold": 1.0
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 6.0,
            "lower": 0.09677141110578047,
            "upper": 0.700006684861608,
            "K": 6,
            "N": 18,
            "clusters_passed": 2,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.7529366485969087,
            "deff": 2.5743220834299,
            "n_eff": 13.207360578090553,
            "lower": 0.04325817835808124,
            "upper": 0.42234631019482527,
            "K": 11,
            "N": 34
          },
          "direction_accuracy": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 4.0,
            "lower": 0.0455872608097006,
            "upper": 0.699358157417598,
            "K": 4,
            "N": 4,
            "clusters_passed": 1,
            "pass_threshold": 1.0
          }
        },
        "REFERENCE": {
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
            "N": 1,
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
            "lower": 0.0,
            "upper": 0.7934506856227626,
            "K": 1,
            "N": 1,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 6.0,
            "lower": 0.0,
            "upper": 0.3903342879021653,
            "K": 6,
            "N": 8,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": null
        }
      },
      "recall_any": {
        "passed": 4,
        "denominator": 101,
        "rate": 0.0396,
        "wilson95": [
          0.0155,
          0.0974
        ]
      },
      "llm_calls": 28,
      "prompt_tokens": 45252,
      "completion_tokens": 9863,
      "elapsed_s": 215.827651,
      "latency_ms": {
        "p50": 10106.56,
        "p95": 38473.74
      },
      "false_duplicate": {
        "observed": 0,
        "unreviewed": 0
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
        "reference_explicit": 0,
        "ungrounded_span": 0,
        "unknown_pair": 0,
        "unrelated": 144
      },
      "injection_signals": 0,
      "over_budget": false
    },
    {
      "variant": "B",
      "trial": 1,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 15,
          "covered": 10,
          "passed": 2,
          "precision_conservative": {
            "passed": 2,
            "denominator": 15,
            "rate": 0.1333,
            "wilson95": [
              0.0374,
              0.3788
            ]
          },
          "precision_observed": {
            "passed": 2,
            "denominator": 10,
            "rate": 0.2,
            "wilson95": [
              0.0567,
              0.5098
            ]
          },
          "recall_observed": {
            "passed": 2,
            "denominator": 34,
            "rate": 0.0588,
            "wilson95": [
              0.0163,
              0.1909
            ]
          },
          "direction_accuracy": {
            "passed": 1,
            "denominator": 2,
            "rate": 0.5,
            "wilson95": [
              0.0945,
              0.9055
            ]
          },
          "precision_weighted": 0.2,
          "recall_weighted": 0.0588
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
            "denominator": 30,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.1135
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": null,
          "recall_weighted": 0.0
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
            "denominator": 29,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.117
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": null,
          "recall_weighted": 0.0
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
            "denominator": 8,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.3244
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
          "recall_weighted": 0.0
        }
      },
      "by_stratum": {
        "S1": {
          "GENERAL_SPECIFIC": {
            "denominator": 10,
            "covered": 8,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 10,
              "rate": 0.1,
              "wilson95": [
                0.0179,
                0.4042
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 8,
              "rate": 0.125,
              "wilson95": [
                0.0224,
                0.4709
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 16,
              "rate": 0.0625,
              "wilson95": [
                0.0111,
                0.2833
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.125,
            "recall_weighted": 0.0625
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
              "denominator": 25,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1332
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 28,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1206
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "S2": {
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "S3": {
          "GENERAL_SPECIFIC": {
            "denominator": 4,
            "covered": 2,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 4,
              "rate": 0.25,
              "wilson95": [
                0.0456,
                0.6994
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 16,
              "rate": 0.0625,
              "wilson95": [
                0.0111,
                0.2833
              ]
            },
            "direction_accuracy": {
              "passed": 1,
              "denominator": 1,
              "rate": 1.0,
              "wilson95": [
                0.2065,
                1.0
              ]
            },
            "precision_weighted": 0.5,
            "recall_weighted": 0.0625
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "recall_weighted": 0.0
          }
        },
        "S4": {
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
            "recall_weighted": 0.0
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
          }
        }
      },
      "by_doc": {
        "pd-0cd20d2016": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
        "pd-0dd5942e4e": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "pd-0ef7060ac8": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "pd-176a825fca": {
          "GENERAL_SPECIFIC": {
            "denominator": 3,
            "covered": 3,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 9,
              "rate": 0.1111,
              "wilson95": [
                0.0199,
                0.435
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.3333,
            "recall_weighted": 0.1111
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
              "denominator": 14,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2153
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-1c0f85fee4": {
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
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 14,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2153
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-1e78e105fc": {
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
        "pd-21d3913039": {
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
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-242e0b7a96": {
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
        "pd-2e28a08bfa": {
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
            "recall_weighted": 0.0
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
        "pd-3d8842533f": {
          "GENERAL_SPECIFIC": {
            "denominator": 2,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
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
            "direction_accuracy": {
              "passed": 1,
              "denominator": 1,
              "rate": 1.0,
              "wilson95": [
                0.2065,
                1.0
              ]
            },
            "precision_weighted": 0.5,
            "recall_weighted": 1.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-43cd896d78": {
          "GENERAL_SPECIFIC": {
            "denominator": 3,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 8,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3244
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-96be63cf8b": {
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
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-a3a3c94483": {
          "GENERAL_SPECIFIC": {
            "denominator": 4,
            "covered": 3,
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "recall_observed": {
              "passed": 0,
              "denominator": 6,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3903
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
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
              "denominator": 11,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2588
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 5,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4345
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 7.0,
            "lower": 0.0,
            "upper": 0.3543304350666873,
            "K": 7,
            "N": 30,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": null
        },
        "DUPLICATE": {
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 4.0,
            "lower": 0.0,
            "upper": 0.4898908364545972,
            "K": 4,
            "N": 29,
            "clusters_passed": 0,
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
            "n_eff": 7.0,
            "lower": 0.0,
            "upper": 0.3543304350666873,
            "K": 7,
            "N": 15,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 4.0,
            "lower": 0.0,
            "upper": 0.4898908364545972,
            "K": 4,
            "N": 10,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.7255189913183572,
            "deff": 2.5169942545747466,
            "n_eff": 13.508175451018023,
            "lower": 0.012722215247890911,
            "upper": 0.31468704424151117,
            "K": 11,
            "N": 34
          },
          "direction_accuracy": {
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
          }
        },
        "REFERENCE": {
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 6.0,
            "lower": 0.0,
            "upper": 0.3903342879021653,
            "K": 6,
            "N": 8,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": null
        }
      },
      "recall_any": {
        "passed": 2,
        "denominator": 101,
        "rate": 0.0198,
        "wilson95": [
          0.0054,
          0.0693
        ]
      },
      "llm_calls": 27,
      "prompt_tokens": 43222,
      "completion_tokens": 8193,
      "elapsed_s": 186.923525,
      "latency_ms": {
        "p50": 8656.28,
        "p95": 37746.58
      },
      "false_duplicate": {
        "observed": 0,
        "unreviewed": 0
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
        "reference_explicit": 0,
        "ungrounded_span": 0,
        "unknown_pair": 0,
        "unrelated": 150
      },
      "injection_signals": 0,
      "over_budget": false
    },
    {
      "variant": "B",
      "trial": 2,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 16,
          "covered": 11,
          "passed": 3,
          "precision_conservative": {
            "passed": 3,
            "denominator": 16,
            "rate": 0.1875,
            "wilson95": [
              0.0659,
              0.4301
            ]
          },
          "precision_observed": {
            "passed": 3,
            "denominator": 11,
            "rate": 0.2727,
            "wilson95": [
              0.0975,
              0.5657
            ]
          },
          "recall_observed": {
            "passed": 3,
            "denominator": 34,
            "rate": 0.0882,
            "wilson95": [
              0.0305,
              0.2296
            ]
          },
          "direction_accuracy": {
            "passed": 0,
            "denominator": 3,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.5615
            ]
          },
          "precision_weighted": 0.2727,
          "recall_weighted": 0.0882
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
            "denominator": 30,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.1135
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": null,
          "recall_weighted": 0.0
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
            "denominator": 29,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.117
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": null,
          "recall_weighted": 0.0
        },
        "REFERENCE": {
          "denominator": 1,
          "covered": 1,
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
            "denominator": 1,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.7935
            ]
          },
          "recall_observed": {
            "passed": 0,
            "denominator": 8,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.3244
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
          "precision_weighted": 0.0,
          "recall_weighted": 0.0
        }
      },
      "by_stratum": {
        "S1": {
          "GENERAL_SPECIFIC": {
            "denominator": 10,
            "covered": 8,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 10,
              "rate": 0.1,
              "wilson95": [
                0.0179,
                0.4042
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 8,
              "rate": 0.125,
              "wilson95": [
                0.0224,
                0.4709
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 16,
              "rate": 0.0625,
              "wilson95": [
                0.0111,
                0.2833
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.125,
            "recall_weighted": 0.0625
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
              "denominator": 25,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1332
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 28,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1206
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
          },
          "REFERENCE": {
            "denominator": 1,
            "covered": 1,
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
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
            "precision_weighted": 0.0,
            "recall_weighted": null
          }
        },
        "S2": {
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "S3": {
          "GENERAL_SPECIFIC": {
            "denominator": 5,
            "covered": 3,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 5,
              "rate": 0.4,
              "wilson95": [
                0.1176,
                0.7693
              ]
            },
            "precision_observed": {
              "passed": 2,
              "denominator": 3,
              "rate": 0.6667,
              "wilson95": [
                0.2077,
                0.9385
              ]
            },
            "recall_observed": {
              "passed": 2,
              "denominator": 16,
              "rate": 0.125,
              "wilson95": [
                0.035,
                0.3602
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
              ]
            },
            "precision_weighted": 0.6667,
            "recall_weighted": 0.125
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "recall_weighted": 0.0
          }
        },
        "S4": {
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
            "recall_weighted": 0.0
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
          }
        }
      },
      "by_doc": {
        "pd-0cd20d2016": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
        "pd-0dd5942e4e": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "pd-0ef7060ac8": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "pd-176a825fca": {
          "GENERAL_SPECIFIC": {
            "denominator": 3,
            "covered": 3,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 9,
              "rate": 0.1111,
              "wilson95": [
                0.0199,
                0.435
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.3333,
            "recall_weighted": 0.1111
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
              "denominator": 14,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2153
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
          },
          "REFERENCE": {
            "denominator": 1,
            "covered": 1,
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
          }
        },
        "pd-1c0f85fee4": {
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
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 14,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2153
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-1e78e105fc": {
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
        "pd-21d3913039": {
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
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-242e0b7a96": {
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
        "pd-2e28a08bfa": {
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
            "recall_weighted": 0.0
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
        "pd-3d8842533f": {
          "GENERAL_SPECIFIC": {
            "denominator": 2,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
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
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.5,
            "recall_weighted": 1.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-43cd896d78": {
          "GENERAL_SPECIFIC": {
            "denominator": 3,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 8,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3244
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-96be63cf8b": {
          "GENERAL_SPECIFIC": {
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
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 1.0,
            "recall_weighted": 1.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-a3a3c94483": {
          "GENERAL_SPECIFIC": {
            "denominator": 4,
            "covered": 3,
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "recall_observed": {
              "passed": 0,
              "denominator": 6,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3903
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
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
              "denominator": 11,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2588
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 5,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4345
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 7.0,
            "lower": 0.0,
            "upper": 0.3543304350666873,
            "K": 7,
            "N": 30,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": null
        },
        "DUPLICATE": {
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 4.0,
            "lower": 0.0,
            "upper": 0.4898908364545972,
            "K": 4,
            "N": 29,
            "clusters_passed": 0,
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
            "n_eff": 8.0,
            "lower": 0.022417491450056726,
            "upper": 0.4708881822128534,
            "K": 8,
            "N": 16,
            "clusters_passed": 1,
            "pass_threshold": 1.0
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 5.0,
            "lower": 0.036224108632430085,
            "upper": 0.6244653702374746,
            "K": 5,
            "N": 11,
            "clusters_passed": 1,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.8389188933450566,
            "deff": 2.7541031406305727,
            "n_eff": 12.345216669051633,
            "lower": 0.014865094404917123,
            "upper": 0.3538799111411169,
            "K": 11,
            "N": 34
          },
          "direction_accuracy": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 3.0,
            "lower": 0.0,
            "upper": 0.5614970317550454,
            "K": 3,
            "N": 3,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          }
        },
        "REFERENCE": {
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
            "N": 1,
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
            "lower": 0.0,
            "upper": 0.7934506856227626,
            "K": 1,
            "N": 1,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 6.0,
            "lower": 0.0,
            "upper": 0.3903342879021653,
            "K": 6,
            "N": 8,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": null
        }
      },
      "recall_any": {
        "passed": 3,
        "denominator": 101,
        "rate": 0.0297,
        "wilson95": [
          0.0102,
          0.0837
        ]
      },
      "llm_calls": 27,
      "prompt_tokens": 43222,
      "completion_tokens": 8166,
      "elapsed_s": 178.249314,
      "latency_ms": {
        "p50": 9526.18,
        "p95": 34407.17
      },
      "false_duplicate": {
        "observed": 0,
        "unreviewed": 0
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
        "reference_explicit": 0,
        "ungrounded_span": 0,
        "unknown_pair": 0,
        "unrelated": 148
      },
      "injection_signals": 0,
      "over_budget": false
    },
    {
      "variant": "E",
      "trial": 1,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 49,
          "covered": 22,
          "passed": 8,
          "precision_conservative": {
            "passed": 8,
            "denominator": 49,
            "rate": 0.1633,
            "wilson95": [
              0.0851,
              0.2904
            ]
          },
          "precision_observed": {
            "passed": 8,
            "denominator": 22,
            "rate": 0.3636,
            "wilson95": [
              0.1973,
              0.5705
            ]
          },
          "recall_observed": {
            "passed": 8,
            "denominator": 34,
            "rate": 0.2353,
            "wilson95": [
              0.1244,
              0.4
            ]
          },
          "direction_accuracy": {
            "passed": 4,
            "denominator": 8,
            "rate": 0.5,
            "wilson95": [
              0.2152,
              0.7848
            ]
          },
          "precision_weighted": 0.3226,
          "recall_weighted": 0.2353
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
            "denominator": 30,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.1135
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": null,
          "recall_weighted": 0.0
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
            "denominator": 29,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.117
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": null,
          "recall_weighted": 0.0
        },
        "REFERENCE": {
          "denominator": 9,
          "covered": 4,
          "passed": 1,
          "precision_conservative": {
            "passed": 1,
            "denominator": 9,
            "rate": 0.1111,
            "wilson95": [
              0.0199,
              0.435
            ]
          },
          "precision_observed": {
            "passed": 1,
            "denominator": 4,
            "rate": 0.25,
            "wilson95": [
              0.0456,
              0.6994
            ]
          },
          "recall_observed": {
            "passed": 1,
            "denominator": 8,
            "rate": 0.125,
            "wilson95": [
              0.0224,
              0.4709
            ]
          },
          "direction_accuracy": {
            "passed": 0,
            "denominator": 1,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.7935
            ]
          },
          "precision_weighted": 0.0508,
          "recall_weighted": 0.125
        }
      },
      "by_stratum": {
        "S1": {
          "GENERAL_SPECIFIC": {
            "denominator": 12,
            "covered": 9,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 12,
              "rate": 0.0833,
              "wilson95": [
                0.0149,
                0.3539
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 9,
              "rate": 0.1111,
              "wilson95": [
                0.0199,
                0.435
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 16,
              "rate": 0.0625,
              "wilson95": [
                0.0111,
                0.2833
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.1111,
            "recall_weighted": 0.0625
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
              "denominator": 25,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1332
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 28,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1206
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "S2": {
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
          },
          "REFERENCE": {
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
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 1.0,
            "recall_weighted": 1.0
          }
        },
        "S3": {
          "GENERAL_SPECIFIC": {
            "denominator": 28,
            "covered": 8,
            "passed": 6,
            "precision_conservative": {
              "passed": 6,
              "denominator": 28,
              "rate": 0.2143,
              "wilson95": [
                0.1021,
                0.3954
              ]
            },
            "precision_observed": {
              "passed": 6,
              "denominator": 8,
              "rate": 0.75,
              "wilson95": [
                0.4093,
                0.9285
              ]
            },
            "recall_observed": {
              "passed": 6,
              "denominator": 16,
              "rate": 0.375,
              "wilson95": [
                0.1848,
                0.6136
              ]
            },
            "direction_accuracy": {
              "passed": 4,
              "denominator": 6,
              "rate": 0.6667,
              "wilson95": [
                0.3,
                0.9032
              ]
            },
            "precision_weighted": 0.75,
            "recall_weighted": 0.375
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "denominator": 8,
            "covered": 3,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 8,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3244
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "recall_observed": {
              "passed": 0,
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
          }
        },
        "S4": {
          "GENERAL_SPECIFIC": {
            "denominator": 9,
            "covered": 5,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 9,
              "rate": 0.1111,
              "wilson95": [
                0.0199,
                0.435
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 5,
              "rate": 0.2,
              "wilson95": [
                0.0362,
                0.6245
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.1282,
            "recall_weighted": 0.5
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
          }
        }
      },
      "by_doc": {
        "pd-0cd20d2016": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
            "denominator": 3,
            "covered": 1,
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
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
            "precision_weighted": 0.0,
            "recall_weighted": null
          }
        },
        "pd-0dd5942e4e": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "pd-0ef7060ac8": {
          "GENERAL_SPECIFIC": {
            "denominator": 6,
            "covered": 3,
            "passed": 3,
            "precision_conservative": {
              "passed": 3,
              "denominator": 6,
              "rate": 0.5,
              "wilson95": [
                0.1876,
                0.8124
              ]
            },
            "precision_observed": {
              "passed": 3,
              "denominator": 3,
              "rate": 1.0,
              "wilson95": [
                0.4385,
                1.0
              ]
            },
            "recall_observed": {
              "passed": 3,
              "denominator": 3,
              "rate": 1.0,
              "wilson95": [
                0.4385,
                1.0
              ]
            },
            "direction_accuracy": {
              "passed": 2,
              "denominator": 3,
              "rate": 0.6667,
              "wilson95": [
                0.2077,
                0.9385
              ]
            },
            "precision_weighted": 1.0,
            "recall_weighted": 1.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "pd-176a825fca": {
          "GENERAL_SPECIFIC": {
            "denominator": 15,
            "covered": 9,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 15,
              "rate": 0.1333,
              "wilson95": [
                0.0374,
                0.3788
              ]
            },
            "precision_observed": {
              "passed": 2,
              "denominator": 9,
              "rate": 0.2222,
              "wilson95": [
                0.0632,
                0.5474
              ]
            },
            "recall_observed": {
              "passed": 2,
              "denominator": 9,
              "rate": 0.2222,
              "wilson95": [
                0.0632,
                0.5474
              ]
            },
            "direction_accuracy": {
              "passed": 1,
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
              ]
            },
            "precision_weighted": 0.1695,
            "recall_weighted": 0.2222
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
              "denominator": 14,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2153
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-1c0f85fee4": {
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
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 14,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2153
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
          },
          "REFERENCE": {
            "denominator": 2,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.5,
            "recall_weighted": 0.5
          }
        },
        "pd-1e78e105fc": {
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
        "pd-21d3913039": {
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
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-242e0b7a96": {
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
        "pd-2e28a08bfa": {
          "GENERAL_SPECIFIC": {
            "denominator": 4,
            "covered": 1,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 4,
              "rate": 0.25,
              "wilson95": [
                0.0456,
                0.6994
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
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 1.0,
            "recall_weighted": 1.0
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
            "denominator": 1,
            "covered": 1,
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
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
            "precision_weighted": 0.0,
            "recall_weighted": null
          }
        },
        "pd-3d8842533f": {
          "GENERAL_SPECIFIC": {
            "denominator": 3,
            "covered": 3,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
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
            "direction_accuracy": {
              "passed": 1,
              "denominator": 1,
              "rate": 1.0,
              "wilson95": [
                0.2065,
                1.0
              ]
            },
            "precision_weighted": 0.3333,
            "recall_weighted": 1.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-43cd896d78": {
          "GENERAL_SPECIFIC": {
            "denominator": 3,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 8,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3244
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-4b7adfd987": {
          "GENERAL_SPECIFIC": {
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
        "pd-96be63cf8b": {
          "GENERAL_SPECIFIC": {
            "denominator": 4,
            "covered": 1,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 4,
              "rate": 0.25,
              "wilson95": [
                0.0456,
                0.6994
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
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 1.0,
            "recall_weighted": 1.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-a3a3c94483": {
          "GENERAL_SPECIFIC": {
            "denominator": 4,
            "covered": 3,
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "recall_observed": {
              "passed": 0,
              "denominator": 6,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3903
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
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
              "denominator": 11,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2588
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 5,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4345
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 7.0,
            "lower": 0.0,
            "upper": 0.3543304350666873,
            "K": 7,
            "N": 30,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": null
        },
        "DUPLICATE": {
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 4.0,
            "lower": 0.0,
            "upper": 0.4898908364545972,
            "K": 4,
            "N": 29,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": null
        },
        "GENERAL_SPECIFIC": {
          "precision_conservative": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.24032173557808112,
            "deff": 1.665506344677763,
            "n_eff": 29.42048233954964,
            "lower": 0.0759785725289123,
            "upper": 0.34548439890195237,
            "K": 13,
            "N": 49
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 7.0,
            "lower": 0.1582198552514697,
            "upper": 0.7495416354723428,
            "K": 7,
            "N": 22,
            "clusters_passed": 3,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.8822823941382385,
            "deff": 2.8447722786526803,
            "n_eff": 11.95174751073672,
            "lower": 0.08894166839405476,
            "upper": 0.5323053349335656,
            "K": 11,
            "N": 34
          },
          "direction_accuracy": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 5.0,
            "lower": 0.036224108632430085,
            "upper": 0.6244653702374746,
            "K": 5,
            "N": 8,
            "clusters_passed": 1,
            "pass_threshold": 1.0
          }
        },
        "REFERENCE": {
          "precision_conservative": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 6.0,
            "lower": 0.0,
            "upper": 0.3903342879021653,
            "K": 6,
            "N": 9,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 3.0,
            "lower": 0.0,
            "upper": 0.5614970317550454,
            "K": 3,
            "N": 4,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 6.0,
            "lower": 0.0,
            "upper": 0.3903342879021653,
            "K": 6,
            "N": 8,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 1.0,
            "lower": 0.0,
            "upper": 0.7934506856227626,
            "K": 1,
            "N": 1,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          }
        }
      },
      "recall_any": {
        "passed": 9,
        "denominator": 101,
        "rate": 0.0891,
        "wilson95": [
          0.0476,
          0.1607
        ]
      },
      "llm_calls": 89,
      "prompt_tokens": 209728,
      "completion_tokens": 31925,
      "elapsed_s": 635.613463,
      "latency_ms": {
        "p50": 49078.21,
        "p95": 75294.38
      },
      "false_duplicate": {
        "observed": 0,
        "unreviewed": 0
      },
      "rejected": {
        "bad_span": 8,
        "citation_invalid": 0,
        "conflict_same_span": 0,
        "duplicate_id": 0,
        "duplicate_value_mismatch": 0,
        "invalid_label": 0,
        "malformed": 0,
        "missing_direction": 0,
        "no_answer": 0,
        "reference_explicit": 0,
        "ungrounded_span": 0,
        "unknown_pair": 0,
        "unrelated": 589
      },
      "injection_signals": 0,
      "over_budget": true
    },
    {
      "variant": "E",
      "trial": 2,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 46,
          "covered": 20,
          "passed": 8,
          "precision_conservative": {
            "passed": 8,
            "denominator": 46,
            "rate": 0.1739,
            "wilson95": [
              0.0909,
              0.3072
            ]
          },
          "precision_observed": {
            "passed": 8,
            "denominator": 20,
            "rate": 0.4,
            "wilson95": [
              0.2188,
              0.6134
            ]
          },
          "recall_observed": {
            "passed": 8,
            "denominator": 34,
            "rate": 0.2353,
            "wilson95": [
              0.1244,
              0.4
            ]
          },
          "direction_accuracy": {
            "passed": 4,
            "denominator": 8,
            "rate": 0.5,
            "wilson95": [
              0.2152,
              0.7848
            ]
          },
          "precision_weighted": 0.3509,
          "recall_weighted": 0.2353
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
            "denominator": 30,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.1135
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": null,
          "recall_weighted": 0.0
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
            "denominator": 29,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.117
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": null,
          "recall_weighted": 0.0
        },
        "REFERENCE": {
          "denominator": 9,
          "covered": 4,
          "passed": 1,
          "precision_conservative": {
            "passed": 1,
            "denominator": 9,
            "rate": 0.1111,
            "wilson95": [
              0.0199,
              0.435
            ]
          },
          "precision_observed": {
            "passed": 1,
            "denominator": 4,
            "rate": 0.25,
            "wilson95": [
              0.0456,
              0.6994
            ]
          },
          "recall_observed": {
            "passed": 1,
            "denominator": 8,
            "rate": 0.125,
            "wilson95": [
              0.0224,
              0.4709
            ]
          },
          "direction_accuracy": {
            "passed": 0,
            "denominator": 1,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.7935
            ]
          },
          "precision_weighted": 0.0845,
          "recall_weighted": 0.125
        }
      },
      "by_stratum": {
        "S1": {
          "GENERAL_SPECIFIC": {
            "denominator": 10,
            "covered": 8,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 10,
              "rate": 0.1,
              "wilson95": [
                0.0179,
                0.4042
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 8,
              "rate": 0.125,
              "wilson95": [
                0.0224,
                0.4709
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 16,
              "rate": 0.0625,
              "wilson95": [
                0.0111,
                0.2833
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.125,
            "recall_weighted": 0.0625
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
              "denominator": 25,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1332
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 28,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1206
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "S2": {
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
          },
          "REFERENCE": {
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
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 1.0,
            "recall_weighted": 1.0
          }
        },
        "S3": {
          "GENERAL_SPECIFIC": {
            "denominator": 27,
            "covered": 7,
            "passed": 6,
            "precision_conservative": {
              "passed": 6,
              "denominator": 27,
              "rate": 0.2222,
              "wilson95": [
                0.1061,
                0.4076
              ]
            },
            "precision_observed": {
              "passed": 6,
              "denominator": 7,
              "rate": 0.8571,
              "wilson95": [
                0.4869,
                0.9743
              ]
            },
            "recall_observed": {
              "passed": 6,
              "denominator": 16,
              "rate": 0.375,
              "wilson95": [
                0.1848,
                0.6136
              ]
            },
            "direction_accuracy": {
              "passed": 4,
              "denominator": 6,
              "rate": 0.6667,
              "wilson95": [
                0.3,
                0.9032
              ]
            },
            "precision_weighted": 0.8571,
            "recall_weighted": 0.375
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "denominator": 8,
            "covered": 3,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 8,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3244
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "recall_observed": {
              "passed": 0,
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
          }
        },
        "S4": {
          "GENERAL_SPECIFIC": {
            "denominator": 9,
            "covered": 5,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 9,
              "rate": 0.1111,
              "wilson95": [
                0.0199,
                0.435
              ]
            },
            "precision_observed": {
              "passed": 1,
              "denominator": 5,
              "rate": 0.2,
              "wilson95": [
                0.0362,
                0.6245
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.1282,
            "recall_weighted": 0.5
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
          }
        }
      },
      "by_doc": {
        "pd-0cd20d2016": {
          "GENERAL_SPECIFIC": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
        "pd-0dd5942e4e": {
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "pd-0ef7060ac8": {
          "GENERAL_SPECIFIC": {
            "denominator": 6,
            "covered": 3,
            "passed": 3,
            "precision_conservative": {
              "passed": 3,
              "denominator": 6,
              "rate": 0.5,
              "wilson95": [
                0.1876,
                0.8124
              ]
            },
            "precision_observed": {
              "passed": 3,
              "denominator": 3,
              "rate": 1.0,
              "wilson95": [
                0.4385,
                1.0
              ]
            },
            "recall_observed": {
              "passed": 3,
              "denominator": 3,
              "rate": 1.0,
              "wilson95": [
                0.4385,
                1.0
              ]
            },
            "direction_accuracy": {
              "passed": 2,
              "denominator": 3,
              "rate": 0.6667,
              "wilson95": [
                0.2077,
                0.9385
              ]
            },
            "precision_weighted": 1.0,
            "recall_weighted": 1.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
        "pd-176a825fca": {
          "GENERAL_SPECIFIC": {
            "denominator": 11,
            "covered": 8,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 11,
              "rate": 0.1818,
              "wilson95": [
                0.0514,
                0.477
              ]
            },
            "precision_observed": {
              "passed": 2,
              "denominator": 8,
              "rate": 0.25,
              "wilson95": [
                0.0715,
                0.5907
              ]
            },
            "recall_observed": {
              "passed": 2,
              "denominator": 9,
              "rate": 0.2222,
              "wilson95": [
                0.0632,
                0.5474
              ]
            },
            "direction_accuracy": {
              "passed": 1,
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
              ]
            },
            "precision_weighted": 0.1852,
            "recall_weighted": 0.2222
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
              "denominator": 14,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2153
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-1c0f85fee4": {
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
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 14,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2153
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
          },
          "REFERENCE": {
            "denominator": 2,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
              ]
            },
            "recall_observed": {
              "passed": 1,
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
              ]
            },
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 0.5,
            "recall_weighted": 0.5
          }
        },
        "pd-1e78e105fc": {
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
        "pd-21d3913039": {
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
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-242e0b7a96": {
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
        "pd-2e28a08bfa": {
          "GENERAL_SPECIFIC": {
            "denominator": 3,
            "covered": 1,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
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
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 1.0,
            "recall_weighted": 1.0
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
            "denominator": 1,
            "covered": 1,
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
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
            "precision_weighted": 0.0,
            "recall_weighted": null
          }
        },
        "pd-3d8842533f": {
          "GENERAL_SPECIFIC": {
            "denominator": 2,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
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
            "direction_accuracy": {
              "passed": 1,
              "denominator": 1,
              "rate": 1.0,
              "wilson95": [
                0.2065,
                1.0
              ]
            },
            "precision_weighted": 0.5,
            "recall_weighted": 1.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "covered": 1,
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
          }
        },
        "pd-43cd896d78": {
          "GENERAL_SPECIFIC": {
            "denominator": 3,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 8,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3244
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-4b7adfd987": {
          "GENERAL_SPECIFIC": {
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
        "pd-96be63cf8b": {
          "GENERAL_SPECIFIC": {
            "denominator": 6,
            "covered": 1,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 6,
              "rate": 0.1667,
              "wilson95": [
                0.0301,
                0.5635
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
            "direction_accuracy": {
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
              ]
            },
            "precision_weighted": 1.0,
            "recall_weighted": 1.0
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
            "recall_weighted": 0.0
          }
        },
        "pd-a3a3c94483": {
          "GENERAL_SPECIFIC": {
            "denominator": 4,
            "covered": 3,
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
              "denominator": 3,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.5615
              ]
            },
            "recall_observed": {
              "passed": 0,
              "denominator": 6,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3903
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
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
              "denominator": 11,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2588
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
              "denominator": 5,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4345
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": null,
            "recall_weighted": 0.0
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
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 7.0,
            "lower": 0.0,
            "upper": 0.3543304350666873,
            "K": 7,
            "N": 30,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": null
        },
        "DUPLICATE": {
          "precision_conservative": null,
          "precision_observed": null,
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 4.0,
            "lower": 0.0,
            "upper": 0.4898908364545972,
            "K": 4,
            "N": 29,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": null
        },
        "GENERAL_SPECIFIC": {
          "precision_conservative": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.2816518570811595,
            "deff": 1.7149624064367894,
            "n_eff": 26.822745400918198,
            "lower": 0.08180707142976532,
            "upper": 0.36698683618548433,
            "K": 13,
            "N": 46
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 7.0,
            "lower": 0.1582198552514697,
            "upper": 0.7495416354723428,
            "K": 7,
            "N": 20,
            "clusters_passed": 3,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.8822823941382385,
            "deff": 2.8447722786526803,
            "n_eff": 11.95174751073672,
            "lower": 0.08894166839405476,
            "upper": 0.5323053349335656,
            "K": 11,
            "N": 34
          },
          "direction_accuracy": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 5.0,
            "lower": 0.036224108632430085,
            "upper": 0.6244653702374746,
            "K": 5,
            "N": 8,
            "clusters_passed": 1,
            "pass_threshold": 1.0
          }
        },
        "REFERENCE": {
          "precision_conservative": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 7.0,
            "lower": 0.0,
            "upper": 0.3543304350666873,
            "K": 7,
            "N": 9,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 3.0,
            "lower": 0.0,
            "upper": 0.5614970317550454,
            "K": 3,
            "N": 4,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 6.0,
            "lower": 0.0,
            "upper": 0.3903342879021653,
            "K": 6,
            "N": 8,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "direction_accuracy": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 1.0,
            "lower": 0.0,
            "upper": 0.7934506856227626,
            "K": 1,
            "N": 1,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          }
        }
      },
      "recall_any": {
        "passed": 9,
        "denominator": 101,
        "rate": 0.0891,
        "wilson95": [
          0.0476,
          0.1607
        ]
      },
      "llm_calls": 89,
      "prompt_tokens": 209728,
      "completion_tokens": 31579,
      "elapsed_s": 639.616101,
      "latency_ms": {
        "p50": 44453.57,
        "p95": 78206.95
      },
      "false_duplicate": {
        "observed": 0,
        "unreviewed": 0
      },
      "rejected": {
        "bad_span": 2,
        "citation_invalid": 0,
        "conflict_same_span": 0,
        "duplicate_id": 0,
        "duplicate_value_mismatch": 0,
        "invalid_label": 0,
        "malformed": 0,
        "missing_direction": 0,
        "no_answer": 0,
        "reference_explicit": 0,
        "ungrounded_span": 0,
        "unknown_pair": 0,
        "unrelated": 598
      },
      "injection_signals": 0,
      "over_budget": true
    }
  ]
}
```
