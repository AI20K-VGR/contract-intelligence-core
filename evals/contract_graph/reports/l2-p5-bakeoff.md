# P5 — bake-off cặp hợp đồng

Khuyến nghị: `KEEP_OFF_INSUFFICIENT_N`. Đo trên mẫu HĐ công khai.

Precision bảo thủ dùng cho cổng; 1/π chỉ báo và không có khoảng tin cậy. Đồng thuận GPT↔người là cận trên vì người duyệt thấy nhãn GPT. Không có người gán mù thứ hai.

Run1 C 10/11, B 8/11, E precision 11/32 chỉ định hướng; có thể dùng GPT và khác dữ liệu.

```json
{
  "decision": {
    "verdict": "KEEP_OFF_INSUFFICIENT_N",
    "recommendation_only": true,
    "thresholds_source": "review_policy.py",
    "thresholds": {
      "min_n": 60,
      "min_wilson_lower": 0.85
    },
    "decisions_sha256": "1271c998e07c6085345522e0da394b293ae6de6ea19a03b20962170e3f805a64",
    "per_label": {
      "GENERAL_SPECIFIC": {
        "trial": 2,
        "k": 4,
        "n": 27,
        "rate": 0.14814814814814814,
        "wilson_lower": 0.059158318596448906,
        "wilson_upper": 0.32479063346829484,
        "method": "wilson",
        "conf": 0.95,
        "cluster_lower": 0.02567962434474358,
        "precision_observed": {
          "passed": 4,
          "denominator": 18,
          "rate": 0.2222,
          "wilson95": [
            0.09,
            0.4522
          ]
        },
        "precision_weighted": 0.1802,
        "recall_observed": {
          "passed": 4,
          "denominator": 34,
          "rate": 0.1176,
          "wilson95": [
            0.0467,
            0.2662
          ]
        },
        "recall_weighted": 0.1176,
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
        "n": 5,
        "rate": 0.0,
        "wilson_lower": 0.0,
        "wilson_upper": 0.43449149475208104,
        "method": "wilson",
        "conf": 0.95,
        "cluster_lower": 0.0,
        "precision_observed": {
          "passed": 0,
          "denominator": 3,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.5615
          ]
        },
        "precision_weighted": 0.0,
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
        "b": 2,
        "c": 0,
        "n_items": 101,
        "method": "mcnemar-wilson",
        "n_disc": 2,
        "lower": 0.34238022750665315,
        "upper": 1.0,
        "conclusive": false
      },
      "C_vs_E": {
        "b": 2,
        "c": 5,
        "n_items": 101,
        "method": "mcnemar-wilson",
        "n_disc": 7,
        "lower": 0.08221892400405678,
        "upper": 0.6410655481673806,
        "conclusive": false
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
          "passed": 5,
          "denominator": 101,
          "rate": 0.0495,
          "wilson95": [
            0.0213,
            0.1107
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
      "spread": 0.009899999999999999,
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
          "passed": 7,
          "denominator": 101,
          "rate": 0.0693,
          "wilson95": [
            0.034,
            0.1362
          ]
        },
        {
          "passed": 10,
          "denominator": 101,
          "rate": 0.099,
          "wilson95": [
            0.0547,
            0.1727
          ]
        }
      ],
      "spread": 0.029700000000000004,
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
        "diff": 0.02314814814814814,
        "lower": -0.22835008109014254,
        "upper": 0.22140375391074052,
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
        "lower": -0.7934506856227626,
        "upper": 0.43448246478317465,
        "conclusive": false
      }
    },
    "C_vs_E": {
      "GENERAL_SPECIFIC": {
        "diff": 0.039057239057239054,
        "lower": -0.10178282969648163,
        "upper": 0.22501312696746578,
        "conclusive": false
      },
      "CONFLICT": {
        "diff": 0.0,
        "lower": -0.6576197724933468,
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
        "diff": -0.05263157894736842,
        "lower": -0.24638731166898778,
        "upper": 0.38400114391234397,
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
          "covered": 19,
          "passed": 5,
          "precision_conservative": {
            "passed": 5,
            "denominator": 28,
            "rate": 0.1786,
            "wilson95": [
              0.0788,
              0.3559
            ]
          },
          "precision_observed": {
            "passed": 5,
            "denominator": 19,
            "rate": 0.2632,
            "wilson95": [
              0.1181,
              0.4879
            ]
          },
          "recall_observed": {
            "passed": 5,
            "denominator": 34,
            "rate": 0.1471,
            "wilson95": [
              0.0645,
              0.3013
            ]
          },
          "direction_accuracy": {
            "passed": 2,
            "denominator": 5,
            "rate": 0.4,
            "wilson95": [
              0.1176,
              0.7693
            ]
          },
          "precision_weighted": 0.2155,
          "recall_weighted": 0.1471
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
          "denominator": 5,
          "covered": 3,
          "passed": 0,
          "precision_conservative": {
            "passed": 0,
            "denominator": 5,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.4345
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
            "denominator": 11,
            "covered": 9,
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
              "denominator": 9,
              "rate": 0.2222,
              "wilson95": [
                0.0632,
                0.5474
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
            "precision_weighted": 0.2222,
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
            "denominator": 4,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
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
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
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
            "denominator": 11,
            "covered": 7,
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
              "denominator": 7,
              "rate": 0.2857,
              "wilson95": [
                0.0822,
                0.6411
              ]
            },
            "recall_observed": {
              "passed": 2,
              "denominator": 2,
              "rate": 1.0,
              "wilson95": [
                0.3424,
                1.0
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
            "precision_weighted": 0.1786,
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
        "pd-0ef7060ac8": {
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
            "denominator": 12,
            "covered": 7,
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
              "denominator": 7,
              "rate": 0.1429,
              "wilson95": [
                0.0257,
                0.5131
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
            "precision_weighted": 0.0893,
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
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
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
            "precision_weighted": 1.0,
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
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
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
            "denominator": 5,
            "covered": 3,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 5,
              "rate": 0.2,
              "wilson95": [
                0.0362,
                0.6245
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
            "covered": 4,
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
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "lower": 0.02567962434474358,
            "upper": 0.5131278292743188,
            "K": 7,
            "N": 28,
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
            "N": 19,
            "clusters_passed": 2,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.7165937702343136,
            "deff": 2.4983324286717465,
            "n_eff": 13.609077643072625,
            "lower": 0.04009392127146494,
            "upper": 0.3994137949697035,
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
            "lower": 0.11762077423264794,
            "upper": 0.769275718723987,
            "K": 5,
            "N": 5,
            "clusters_passed": 2,
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
            "n_eff": 5.0,
            "lower": 0.0,
            "upper": 0.43448246478317465,
            "K": 5,
            "N": 5,
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
            "N": 3,
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
        "passed": 5,
        "denominator": 101,
        "rate": 0.0495,
        "wilson95": [
          0.0213,
          0.1107
        ]
      },
      "llm_calls": 28,
      "prompt_tokens": 45140,
      "completion_tokens": 14500,
      "elapsed_s": 248.7356,
      "latency_ms": {
        "p50": 13098.53,
        "p95": 48313.43
      },
      "false_duplicate": {
        "observed": 0,
        "unreviewed": 0
      },
      "rejected": {
        "bad_span": 1,
        "citation_invalid": 0,
        "conflict_same_span": 0,
        "duplicate_id": 0,
        "duplicate_value_mismatch": 0,
        "invalid_label": 0,
        "malformed": 0,
        "missing_direction": 0,
        "no_answer": 0,
        "reference_explicit": 1,
        "ungrounded_span": 0,
        "unknown_pair": 0,
        "unrelated": 139
      },
      "injection_signals": 0,
      "over_budget": false
    },
    {
      "variant": "C",
      "trial": 2,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 27,
          "covered": 18,
          "passed": 4,
          "precision_conservative": {
            "passed": 4,
            "denominator": 27,
            "rate": 0.1481,
            "wilson95": [
              0.0592,
              0.3248
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
          "denominator": 3,
          "covered": 3,
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
            "denominator": 3,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.5615
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
            "denominator": 12,
            "covered": 10,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 12,
              "rate": 0.1667,
              "wilson95": [
                0.047,
                0.448
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
            "precision_weighted": 0.2,
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
            "covered": 2,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 5,
              "rate": 0.2,
              "wilson95": [
                0.0362,
                0.6245
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
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
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
            "denominator": 10,
            "covered": 6,
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
            "denominator": 2,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
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
            "denominator": 13,
            "covered": 8,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 13,
              "rate": 0.0769,
              "wilson95": [
                0.0137,
                0.3331
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
            "denominator": 5,
            "covered": 3,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 5,
              "rate": 0.2,
              "wilson95": [
                0.0362,
                0.6245
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
            "covered": 4,
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
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "lower": 0.02567962434474358,
            "upper": 0.5131278292743188,
            "K": 7,
            "N": 27,
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
            "N": 18,
            "clusters_passed": 1,
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
            "n_eff": 3.0,
            "lower": 0.0,
            "upper": 0.5614970317550454,
            "K": 3,
            "N": 3,
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
            "N": 3,
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
      "prompt_tokens": 45140,
      "completion_tokens": 12820,
      "elapsed_s": 220.02585,
      "latency_ms": {
        "p50": 9604.91,
        "p95": 45033.38
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
        "reference_explicit": 1,
        "ungrounded_span": 0,
        "unknown_pair": 0,
        "unrelated": 143
      },
      "injection_signals": 0,
      "over_budget": false
    },
    {
      "variant": "B",
      "trial": 1,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 16,
          "covered": 12,
          "passed": 2,
          "precision_conservative": {
            "passed": 2,
            "denominator": 16,
            "rate": 0.125,
            "wilson95": [
              0.035,
              0.3602
            ]
          },
          "precision_observed": {
            "passed": 2,
            "denominator": 12,
            "rate": 0.1667,
            "wilson95": [
              0.047,
              0.448
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
          "precision_weighted": 0.1667,
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
            "denominator": 13,
            "covered": 11,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 13,
              "rate": 0.1538,
              "wilson95": [
                0.0433,
                0.4224
              ]
            },
            "precision_observed": {
              "passed": 2,
              "denominator": 11,
              "rate": 0.1818,
              "wilson95": [
                0.0514,
                0.477
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
            "precision_weighted": 0.1818,
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
              "denominator": 16,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1936
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "denominator": 4,
            "covered": 4,
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
              "denominator": 4,
              "rate": 0.25,
              "wilson95": [
                0.0456,
                0.6994
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
            "precision_weighted": 0.25,
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
            "denominator": 5,
            "covered": 3,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 5,
              "rate": 0.2,
              "wilson95": [
                0.0362,
                0.6245
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
            "covered": 4,
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
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "n_eff": 6.0,
            "lower": 0.0,
            "upper": 0.3903342879021653,
            "K": 6,
            "N": 16,
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
            "N": 12,
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
        "passed": 2,
        "denominator": 101,
        "rate": 0.0198,
        "wilson95": [
          0.0054,
          0.0693
        ]
      },
      "llm_calls": 27,
      "prompt_tokens": 43114,
      "completion_tokens": 11823,
      "elapsed_s": 212.048903,
      "latency_ms": {
        "p50": 8894.04,
        "p95": 46003.54
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
        "reference_explicit": 2,
        "ungrounded_span": 0,
        "unknown_pair": 0,
        "unrelated": 146
      },
      "injection_signals": 0,
      "over_budget": false
    },
    {
      "variant": "B",
      "trial": 2,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 17,
          "covered": 12,
          "passed": 3,
          "precision_conservative": {
            "passed": 3,
            "denominator": 17,
            "rate": 0.1765,
            "wilson95": [
              0.0619,
              0.4103
            ]
          },
          "precision_observed": {
            "passed": 3,
            "denominator": 12,
            "rate": 0.25,
            "wilson95": [
              0.0889,
              0.5323
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
          "precision_weighted": 0.25,
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
            "denominator": 13,
            "covered": 10,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 13,
              "rate": 0.1538,
              "wilson95": [
                0.0433,
                0.4224
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
            "precision_weighted": 0.2,
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
              "passed": 0,
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "denominator": 5,
            "covered": 3,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 5,
              "rate": 0.2,
              "wilson95": [
                0.0362,
                0.6245
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
            "denominator": 5,
            "covered": 4,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 5,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4345
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "lower": 0.02567962434474358,
            "upper": 0.5131278292743188,
            "K": 7,
            "N": 17,
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
            "N": 12,
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
            "lower": 0.06149194472039632,
            "upper": 0.7923403991979523,
            "K": 3,
            "N": 3,
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
        "passed": 3,
        "denominator": 101,
        "rate": 0.0297,
        "wilson95": [
          0.0102,
          0.0837
        ]
      },
      "llm_calls": 27,
      "prompt_tokens": 43114,
      "completion_tokens": 12474,
      "elapsed_s": 215.901555,
      "latency_ms": {
        "p50": 9680.8,
        "p95": 47983.8
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
        "reference_explicit": 2,
        "ungrounded_span": 0,
        "unknown_pair": 0,
        "unrelated": 145
      },
      "injection_signals": 0,
      "over_budget": false
    },
    {
      "variant": "E",
      "trial": 1,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 55,
          "covered": 21,
          "passed": 6,
          "precision_conservative": {
            "passed": 6,
            "denominator": 55,
            "rate": 0.1091,
            "wilson95": [
              0.051,
              0.2183
            ]
          },
          "precision_observed": {
            "passed": 6,
            "denominator": 21,
            "rate": 0.2857,
            "wilson95": [
              0.1381,
              0.4996
            ]
          },
          "recall_observed": {
            "passed": 6,
            "denominator": 34,
            "rate": 0.1765,
            "wilson95": [
              0.0835,
              0.3351
            ]
          },
          "direction_accuracy": {
            "passed": 3,
            "denominator": 6,
            "rate": 0.5,
            "wilson95": [
              0.1876,
              0.8124
            ]
          },
          "precision_weighted": 0.2521,
          "recall_weighted": 0.1765
        },
        "CONFLICT": {
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
          "denominator": 11,
          "covered": 5,
          "passed": 1,
          "precision_conservative": {
            "passed": 1,
            "denominator": 11,
            "rate": 0.0909,
            "wilson95": [
              0.0162,
              0.3774
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
          "precision_weighted": 0.0656,
          "recall_weighted": 0.125
        }
      },
      "by_stratum": {
        "S1": {
          "GENERAL_SPECIFIC": {
            "denominator": 14,
            "covered": 10,
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
              "denominator": 10,
              "rate": 0.1,
              "wilson95": [
                0.0179,
                0.4042
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
            "precision_weighted": 0.1,
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
            "denominator": 3,
            "covered": 2,
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
            "precision_weighted": 0.3333,
            "recall_weighted": 1.0
          }
        },
        "S3": {
          "GENERAL_SPECIFIC": {
            "denominator": 32,
            "covered": 6,
            "passed": 4,
            "precision_conservative": {
              "passed": 4,
              "denominator": 32,
              "rate": 0.125,
              "wilson95": [
                0.0497,
                0.2807
              ]
            },
            "precision_observed": {
              "passed": 4,
              "denominator": 6,
              "rate": 0.6667,
              "wilson95": [
                0.3,
                0.9032
              ]
            },
            "recall_observed": {
              "passed": 4,
              "denominator": 16,
              "rate": 0.25,
              "wilson95": [
                0.1018,
                0.495
              ]
            },
            "direction_accuracy": {
              "passed": 3,
              "denominator": 4,
              "rate": 0.75,
              "wilson95": [
                0.3006,
                0.9544
              ]
            },
            "precision_weighted": 0.6667,
            "recall_weighted": 0.25
          },
          "CONFLICT": {
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
            "denominator": 7,
            "covered": 2,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 7,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3543
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
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "denominator": 5,
            "covered": 2,
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
              "denominator": 2,
              "rate": 1.0,
              "wilson95": [
                0.3424,
                1.0
              ]
            },
            "recall_observed": {
              "passed": 2,
              "denominator": 3,
              "rate": 0.6667,
              "wilson95": [
                0.2077,
                0.9385
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
            "precision_weighted": 1.0,
            "recall_weighted": 0.6667
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
            "denominator": 16,
            "covered": 9,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 16,
              "rate": 0.125,
              "wilson95": [
                0.035,
                0.3602
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
            "denominator": 5,
            "covered": 3,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 5,
              "rate": 0.2,
              "wilson95": [
                0.0362,
                0.6245
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
            "precision_weighted": 0.25,
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "denominator": 7,
            "covered": 1,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 7,
              "rate": 0.1429,
              "wilson95": [
                0.0257,
                0.5131
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
            "denominator": 4,
            "covered": 2,
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
        "pd-96be63cf8b": {
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
            "denominator": 5,
            "covered": 4,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 5,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4345
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 4,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4899
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
            "icc": 0.23531309639167824,
            "deff": 1.8432052620701804,
            "n_eff": 29.839324535253994,
            "lower": 0.03459988874733419,
            "upper": 0.25621082579184085,
            "K": 12,
            "N": 55
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
            "N": 21,
            "clusters_passed": 3,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.6085683354091364,
            "deff": 2.272461064946376,
            "n_eff": 14.961752491368783,
            "lower": 0.07047549346981555,
            "upper": 0.4518544871516935,
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
            "N": 6,
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
            "n_eff": 5.0,
            "lower": 0.0,
            "upper": 0.43448246478317465,
            "K": 5,
            "N": 11,
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
            "N": 5,
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
        "passed": 7,
        "denominator": 101,
        "rate": 0.0693,
        "wilson95": [
          0.034,
          0.1362
        ]
      },
      "llm_calls": 89,
      "prompt_tokens": 209372,
      "completion_tokens": 41293,
      "elapsed_s": 714.874393,
      "latency_ms": {
        "p50": 51185.71,
        "p95": 90877.48
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
        "unrelated": 587
      },
      "injection_signals": 0,
      "over_budget": true
    },
    {
      "variant": "E",
      "trial": 2,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 61,
          "covered": 24,
          "passed": 9,
          "precision_conservative": {
            "passed": 9,
            "denominator": 61,
            "rate": 0.1475,
            "wilson95": [
              0.0796,
              0.2572
            ]
          },
          "precision_observed": {
            "passed": 9,
            "denominator": 24,
            "rate": 0.375,
            "wilson95": [
              0.2116,
              0.5729
            ]
          },
          "recall_observed": {
            "passed": 9,
            "denominator": 34,
            "rate": 0.2647,
            "wilson95": [
              0.146,
              0.4312
            ]
          },
          "direction_accuracy": {
            "passed": 5,
            "denominator": 9,
            "rate": 0.5556,
            "wilson95": [
              0.2666,
              0.8112
            ]
          },
          "precision_weighted": 0.3082,
          "recall_weighted": 0.2647
        },
        "CONFLICT": {
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
          "denominator": 19,
          "covered": 12,
          "passed": 1,
          "precision_conservative": {
            "passed": 1,
            "denominator": 19,
            "rate": 0.0526,
            "wilson95": [
              0.0094,
              0.2464
            ]
          },
          "precision_observed": {
            "passed": 1,
            "denominator": 12,
            "rate": 0.0833,
            "wilson95": [
              0.0149,
              0.3539
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
          "precision_weighted": 0.0264,
          "recall_weighted": 0.125
        }
      },
      "by_stratum": {
        "S1": {
          "GENERAL_SPECIFIC": {
            "denominator": 14,
            "covered": 10,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 14,
              "rate": 0.1429,
              "wilson95": [
                0.0401,
                0.3994
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
            "precision_weighted": 0.2,
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
            "denominator": 2,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
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
            "denominator": 2,
            "covered": 1,
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
            "denominator": 3,
            "covered": 2,
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
            "precision_weighted": 0.3333,
            "recall_weighted": 1.0
          }
        },
        "S3": {
          "GENERAL_SPECIFIC": {
            "denominator": 34,
            "covered": 7,
            "passed": 6,
            "precision_conservative": {
              "passed": 6,
              "denominator": 34,
              "rate": 0.1765,
              "wilson95": [
                0.0835,
                0.3351
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
            "denominator": 12,
            "covered": 6,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 12,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2425
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 6,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3903
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
            "denominator": 11,
            "covered": 6,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 11,
              "rate": 0.0909,
              "wilson95": [
                0.0162,
                0.3774
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
            "denominator": 2,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
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
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
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
            "denominator": 5,
            "covered": 1,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 5,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4345
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
            "denominator": 4,
            "covered": 2,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 4,
              "rate": 0.5,
              "wilson95": [
                0.15,
                0.85
              ]
            },
            "precision_observed": {
              "passed": 2,
              "denominator": 2,
              "rate": 1.0,
              "wilson95": [
                0.3424,
                1.0
              ]
            },
            "recall_observed": {
              "passed": 2,
              "denominator": 3,
              "rate": 0.6667,
              "wilson95": [
                0.2077,
                0.9385
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
            "precision_weighted": 1.0,
            "recall_weighted": 0.6667
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
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
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
        "pd-176a825fca": {
          "GENERAL_SPECIFIC": {
            "denominator": 17,
            "covered": 9,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 17,
              "rate": 0.1176,
              "wilson95": [
                0.0329,
                0.3434
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
            "precision_weighted": 0.1515,
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
          }
        },
        "pd-1c0f85fee4": {
          "GENERAL_SPECIFIC": {
            "denominator": 2,
            "covered": 1,
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
              "denominator": 1,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.7935
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
            "denominator": 5,
            "covered": 3,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 5,
              "rate": 0.2,
              "wilson95": [
                0.0362,
                0.6245
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
            "precision_weighted": 0.25,
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
        "pd-242e0b7a96": {
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "denominator": 2,
            "covered": 2,
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
              "denominator": 2,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.6576
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "denominator": 4,
            "covered": 2,
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
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
          }
        },
        "pd-4b7adfd987": {
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "denominator": 7,
            "covered": 5,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 7,
              "rate": 0.1429,
              "wilson95": [
                0.0257,
                0.5131
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
              "denominator": 6,
              "rate": 0.1667,
              "wilson95": [
                0.0301,
                0.5635
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
            "precision_weighted": 0.2,
            "recall_weighted": 0.1667
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
            "icc": 0.20116275017137486,
            "deff": 1.675332089861044,
            "n_eff": 36.41069156925149,
            "lower": 0.06081815009132836,
            "upper": 0.286595303893562,
            "K": 14,
            "N": 61
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 9.0,
            "lower": 0.18877852109766463,
            "upper": 0.7333487065045068,
            "K": 9,
            "N": 24,
            "clusters_passed": 4,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.6343773614254752,
            "deff": 2.326425392071448,
            "n_eff": 14.614696055103842,
            "lower": 0.10897453325692372,
            "upper": 0.5195043405598055,
            "K": 11,
            "N": 34
          },
          "direction_accuracy": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 7.0,
            "lower": 0.1582198552514697,
            "upper": 0.7495416354723428,
            "K": 7,
            "N": 9,
            "clusters_passed": 3,
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
            "N": 19,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 7.0,
            "lower": 0.0,
            "upper": 0.3543304350666873,
            "K": 7,
            "N": 12,
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
        "passed": 10,
        "denominator": 101,
        "rate": 0.099,
        "wilson95": [
          0.0547,
          0.1727
        ]
      },
      "llm_calls": 89,
      "prompt_tokens": 209372,
      "completion_tokens": 42511,
      "elapsed_s": 737.984944,
      "latency_ms": {
        "p50": 48939.36,
        "p95": 87944.16
      },
      "false_duplicate": {
        "observed": 0,
        "unreviewed": 0
      },
      "rejected": {
        "bad_span": 1,
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
        "unrelated": 572
      },
      "injection_signals": 0,
      "over_budget": true
    }
  ]
}
```
