# P5 — bake-off cặp hợp đồng

Khuyến nghị: `KEEP_OFF_FALSE_DUPLICATE`. Đo trên mẫu HĐ công khai.

Precision bảo thủ dùng cho cổng; 1/π chỉ báo và không có khoảng tin cậy. Đồng thuận GPT↔người là cận trên vì người duyệt thấy nhãn GPT. Không có người gán mù thứ hai.

Run1 C 10/11, B 8/11, E precision 11/32 chỉ định hướng; có thể dùng GPT và khác dữ liệu.

```json
{
  "decision": {
    "verdict": "KEEP_OFF_FALSE_DUPLICATE",
    "recommendation_only": true,
    "thresholds_source": "review_policy.py",
    "thresholds": {
      "min_n": 60,
      "min_wilson_lower": 0.85
    },
    "decisions_sha256": "c7d45402809b71a9a575ff4cca57aadae78eb1d7e1a87bc50758f6e798399952",
    "per_label": {
      "GENERAL_SPECIFIC": {
        "trial": 2,
        "k": 1,
        "n": 16,
        "rate": 0.0625,
        "wilson_lower": 0.01111905730833121,
        "wilson_upper": 0.2832926836802987,
        "method": "wilson",
        "conf": 0.95,
        "cluster_lower": 0.0,
        "precision_observed": {
          "passed": 1,
          "denominator": 16,
          "rate": 0.0625,
          "wilson95": [
            0.0111,
            0.2833
          ]
        },
        "precision_weighted": 0.0532,
        "recall_observed": {
          "passed": 1,
          "denominator": 34,
          "rate": 0.0294,
          "wilson95": [
            0.0052,
            0.1492
          ]
        },
        "recall_weighted": 0.0294,
        "passed": false,
        "min_n_needed": null,
        "min_n_all_pass": 22,
        "additional_docs_estimate": null,
        "sizing_note": "Ước tính giữ tỷ lệ đo, dùng floor(p*n); null: chưa có cỡ hữu hạn được chứng minh. all-pass là trường hợp tốt nhất."
      },
      "CONFLICT": {
        "trial": 1,
        "k": 4,
        "n": 7,
        "rate": 0.5714285714285714,
        "wilson_lower": 0.2504542304090258,
        "wilson_upper": 0.8417830777373732,
        "method": "wilson",
        "conf": 0.95,
        "cluster_lower": 0.06149194472039632,
        "precision_observed": {
          "passed": 4,
          "denominator": 7,
          "rate": 0.5714,
          "wilson95": [
            0.2505,
            0.8418
          ]
        },
        "precision_weighted": 0.4762,
        "recall_observed": {
          "passed": 4,
          "denominator": 30,
          "rate": 0.1333,
          "wilson95": [
            0.0531,
            0.2968
          ]
        },
        "recall_weighted": 0.1333,
        "passed": false,
        "min_n_needed": null,
        "min_n_all_pass": 22,
        "additional_docs_estimate": null,
        "sizing_note": "Ước tính giữ tỷ lệ đo, dùng floor(p*n); null: chưa có cỡ hữu hạn được chứng minh. all-pass là trường hợp tốt nhất."
      },
      "DUPLICATE": {
        "trial": 1,
        "k": 0,
        "n": 1,
        "rate": 0.0,
        "wilson_lower": 0.0,
        "wilson_upper": 0.7934567085261071,
        "method": "wilson",
        "conf": 0.95,
        "cluster_lower": 0.0,
        "precision_observed": {
          "passed": 0,
          "denominator": 1,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.7935
          ]
        },
        "precision_weighted": 0.0,
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
        "n": 7,
        "rate": 0.0,
        "wilson_lower": 0.0,
        "wilson_upper": 0.35433884297520657,
        "method": "wilson",
        "conf": 0.95,
        "cluster_lower": 0.0,
        "precision_observed": {
          "passed": 0,
          "denominator": 7,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.3543
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
        "b": 4,
        "c": 0,
        "n_items": 101,
        "method": "mcnemar-wilson",
        "n_disc": 4,
        "lower": 0.5101091635454027,
        "upper": 1.0,
        "conclusive": true
      }
    },
    "feasibility": {
      "expected_n": {
        "GENERAL_SPECIFIC": 18.31578947368421,
        "CONFLICT": 9.157894736842104,
        "DUPLICATE": 9.157894736842104,
        "REFERENCE": 9.157894736842104
      },
      "status": "KEEP_OFF_INSUFFICIENT_N expected",
      "skipped_variants": {
        "E": "every label expected_n < MIN_N/2"
      }
    },
    "variants_run": [
      "C",
      "B"
    ],
    "budget_blocked_variants": []
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
          "passed": 0,
          "denominator": 101,
          "rate": 0.0,
          "wilson95": [
            0.0,
            0.0366
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
      "spread": 0.0396,
      "over_budget": false
    }
  },
  "method": "wilson 95%",
  "labeler_calibration": {
    "by_stratum": {
      "S3": {
        "UNRELATED": {
          "UNRELATED": 433
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
          "UNRELATED": 77
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
          "UNRELATED": 20
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
          "UNRELATED": 24
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
        "UNRELATED": 554
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
      "passed": 655,
      "denominator": 655,
      "rate": 1.0,
      "wilson95": [
        0.9942,
        1.0
      ]
    },
    "note": "Đồng thuận GPT↔người là cận trên: người duyệt thấy nhãn GPT khi duyệt (không có người gán mù thứ hai).",
    "judge_screen": {
      "GENERAL_SPECIFIC": {
        "TP": 34,
        "FN": 0,
        "TN": 621,
        "FP": 0,
        "sens": 1.0,
        "spec": 1.0,
        "sens_ci": [
          0.8984854458466762,
          1.0
        ],
        "spec_ci": [
          0.9938521063760007,
          1.0
        ],
        "youden_j": 1.0,
        "verdict": "ok",
        "bias_direction": null,
        "n_calib": 655
      },
      "CONFLICT": {
        "TP": 30,
        "FN": 0,
        "TN": 625,
        "FP": 0,
        "sens": 1.0,
        "spec": 1.0,
        "sens_ci": [
          0.8864866068260314,
          1.0
        ],
        "spec_ci": [
          0.9938912125356713,
          1.0
        ],
        "youden_j": 1.0,
        "verdict": "ok",
        "bias_direction": null,
        "n_calib": 655
      },
      "DUPLICATE": {
        "TP": 29,
        "FN": 0,
        "TN": 626,
        "FP": 0,
        "sens": 1.0,
        "spec": 1.0,
        "sens_ci": [
          0.8830302015002593,
          1.0
        ],
        "spec_ci": [
          0.993900911464471,
          1.0
        ],
        "youden_j": 1.0,
        "verdict": "ok",
        "bias_direction": null,
        "n_calib": 655
      },
      "REFERENCE": {
        "TP": 8,
        "FN": 0,
        "TN": 647,
        "FP": 0,
        "sens": 1.0,
        "spec": 1.0,
        "sens_ci": [
          0.6755924351161198,
          1.0
        ],
        "spec_ci": [
          0.9940977041818221,
          1.0
        ],
        "youden_j": 1.0,
        "verdict": "ok",
        "bias_direction": null,
        "n_calib": 655
      }
    },
    "upper_bound_only": true
  },
  "precision_difference": {
    "C_vs_B": {
      "GENERAL_SPECIFIC": {
        "diff": 0.0625,
        "lower": -0.3312014453167592,
        "upper": 0.28328737570298934,
        "conclusive": false
      },
      "CONFLICT": {
        "diff": 0.5714285714285714,
        "lower": -0.4788199104641737,
        "upper": 0.8417801447485302,
        "conclusive": false
      },
      "DUPLICATE": {
        "diff": 0.0,
        "lower": -0.7934506856227626,
        "upper": 0.7934506856227626,
        "conclusive": false
      },
      "REFERENCE": {
        "diff": 0.0,
        "lower": -0.27753279986288915,
        "upper": 0.3543304350666873,
        "conclusive": false
      }
    }
  },
  "dev_tuning_rounds": {
    "prompt": 0,
    "lexicon": 0
  },
  "heldout_trial_count": 4,
  "trials": [
    {
      "variant": "C",
      "trial": 1,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 15,
          "covered": 15,
          "passed": 1,
          "precision_conservative": {
            "passed": 1,
            "denominator": 15,
            "rate": 0.0667,
            "wilson95": [
              0.0119,
              0.2982
            ]
          },
          "precision_observed": {
            "passed": 1,
            "denominator": 15,
            "rate": 0.0667,
            "wilson95": [
              0.0119,
              0.2982
            ]
          },
          "recall_observed": {
            "passed": 1,
            "denominator": 34,
            "rate": 0.0294,
            "wilson95": [
              0.0052,
              0.1492
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
          "precision_weighted": 0.061,
          "recall_weighted": 0.0294
        },
        "CONFLICT": {
          "denominator": 7,
          "covered": 7,
          "passed": 4,
          "precision_conservative": {
            "passed": 4,
            "denominator": 7,
            "rate": 0.5714,
            "wilson95": [
              0.2505,
              0.8418
            ]
          },
          "precision_observed": {
            "passed": 4,
            "denominator": 7,
            "rate": 0.5714,
            "wilson95": [
              0.2505,
              0.8418
            ]
          },
          "recall_observed": {
            "passed": 4,
            "denominator": 30,
            "rate": 0.1333,
            "wilson95": [
              0.0531,
              0.2968
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": 0.4762,
          "recall_weighted": 0.1333
        },
        "DUPLICATE": {
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
            "denominator": 29,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.117
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": 0.0,
          "recall_weighted": 0.0
        },
        "REFERENCE": {
          "denominator": 7,
          "covered": 7,
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
            "denominator": 7,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.3543
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
            "denominator": 7,
            "covered": 7,
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
              "denominator": 7,
              "rate": 0.1429,
              "wilson95": [
                0.0257,
                0.5131
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
            "precision_weighted": 0.1429,
            "recall_weighted": 0.0625
          },
          "CONFLICT": {
            "denominator": 2,
            "covered": 2,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 2,
              "rate": 1.0,
              "wilson95": [
                0.3424,
                1.0
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
              "denominator": 25,
              "rate": 0.08,
              "wilson95": [
                0.0222,
                0.2497
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 1.0,
            "recall_weighted": 0.08
          },
          "DUPLICATE": {
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
              "denominator": 28,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1206
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
          },
          "REFERENCE": {
            "denominator": 6,
            "covered": 6,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 6,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3903
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
              "denominator": 3,
              "rate": 0.3333,
              "wilson95": [
                0.0615,
                0.7923
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 0.5,
            "recall_weighted": 0.3333
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
            "denominator": 5,
            "covered": 5,
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
              "denominator": 5,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.4345
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
          },
          "CONFLICT": {
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
              "denominator": 2,
              "rate": 0.5,
              "wilson95": [
                0.0945,
                0.9055
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 0.2273,
            "recall_weighted": 0.5
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
            "denominator": 8,
            "covered": 8,
            "passed": 1,
            "precision_conservative": {
              "passed": 1,
              "denominator": 8,
              "rate": 0.125,
              "wilson95": [
                0.0224,
                0.4709
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
            "precision_weighted": 0.1064,
            "recall_weighted": 0.1111
          },
          "CONFLICT": {
            "denominator": 4,
            "covered": 4,
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
              "denominator": 4,
              "rate": 0.5,
              "wilson95": [
                0.15,
                0.85
              ]
            },
            "recall_observed": {
              "passed": 2,
              "denominator": 14,
              "rate": 0.1429,
              "wilson95": [
                0.0401,
                0.3994
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 0.3704,
            "recall_weighted": 0.1429
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "direction_accuracy": null,
            "precision_weighted": 0.5,
            "recall_weighted": 1.0
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
            "direction_accuracy": null,
            "precision_weighted": 0.0,
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
              "denominator": 11,
              "rate": 0.0909,
              "wilson95": [
                0.0162,
                0.3774
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 1.0,
            "recall_weighted": 0.0909
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
          "precision_conservative": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 3.0,
            "lower": 0.06149194472039632,
            "upper": 0.7923403991979523,
            "K": 3,
            "N": 7,
            "clusters_passed": 1,
            "pass_threshold": 1.0
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 3.0,
            "lower": 0.06149194472039632,
            "upper": 0.7923403991979523,
            "K": 3,
            "N": 7,
            "clusters_passed": 1,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 7.0,
            "lower": 0.02567962434474358,
            "upper": 0.5131278292743188,
            "K": 7,
            "N": 30,
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
            "n_eff": 5.0,
            "lower": 0.0,
            "upper": 0.43448246478317465,
            "K": 5,
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
            "n_eff": 5.0,
            "lower": 0.0,
            "upper": 0.43448246478317465,
            "K": 5,
            "N": 15,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.0,
            "deff": 1.0,
            "n_eff": 34.0,
            "lower": 0.0052109062762689395,
            "upper": 0.14915573292685927,
            "K": 11,
            "N": 34
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
            "N": 7,
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
            "N": 7,
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
      "prompt_tokens": 69220,
      "completion_tokens": 16217,
      "elapsed_s": 299.092768,
      "latency_ms": {
        "p50": 13333.58,
        "p95": 58423.7
      },
      "false_duplicate": {
        "observed": 1,
        "unreviewed": 0
      },
      "rejected": {
        "bad_span": 1,
        "citation_invalid": 0,
        "conflict_same_span": 0,
        "duplicate_id": 0,
        "duplicate_value_mismatch": 2,
        "invalid_label": 0,
        "malformed": 0,
        "missing_direction": 0,
        "no_answer": 0,
        "reference_explicit": 2,
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
          "denominator": 16,
          "covered": 16,
          "passed": 1,
          "precision_conservative": {
            "passed": 1,
            "denominator": 16,
            "rate": 0.0625,
            "wilson95": [
              0.0111,
              0.2833
            ]
          },
          "precision_observed": {
            "passed": 1,
            "denominator": 16,
            "rate": 0.0625,
            "wilson95": [
              0.0111,
              0.2833
            ]
          },
          "recall_observed": {
            "passed": 1,
            "denominator": 34,
            "rate": 0.0294,
            "wilson95": [
              0.0052,
              0.1492
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
          "precision_weighted": 0.0532,
          "recall_weighted": 0.0294
        },
        "CONFLICT": {
          "denominator": 3,
          "covered": 3,
          "passed": 3,
          "precision_conservative": {
            "passed": 3,
            "denominator": 3,
            "rate": 1.0,
            "wilson95": [
              0.4385,
              1.0
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
            "denominator": 30,
            "rate": 0.1,
            "wilson95": [
              0.0346,
              0.2562
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": 1.0,
          "recall_weighted": 0.1
        },
        "DUPLICATE": {
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
            "denominator": 29,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.117
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": 0.0,
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
            "denominator": 2,
            "covered": 2,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 2,
              "rate": 1.0,
              "wilson95": [
                0.3424,
                1.0
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
              "denominator": 25,
              "rate": 0.08,
              "wilson95": [
                0.0222,
                0.2497
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 1.0,
            "recall_weighted": 0.08
          },
          "DUPLICATE": {
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
              "denominator": 28,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1206
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 0.0,
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
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
            "direction_accuracy": null,
            "precision_weighted": 1.0,
            "recall_weighted": 0.3333
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
            "denominator": 9,
            "covered": 9,
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
              "denominator": 9,
              "rate": 0.1111,
              "wilson95": [
                0.0199,
                0.435
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
            "precision_weighted": 0.0847,
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
            "denominator": 11,
            "covered": 11,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 11,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2588
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 11,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2588
              ]
            },
            "recall_observed": {
              "passed": 0,
              "denominator": 9,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2992
              ]
            },
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
              "denominator": 14,
              "rate": 0.0714,
              "wilson95": [
                0.0127,
                0.3147
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 1.0,
            "recall_weighted": 0.0714
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "precision_weighted": 1.0,
            "recall_weighted": 1.0
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
            "direction_accuracy": null,
            "precision_weighted": 0.0,
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
              "denominator": 11,
              "rate": 0.0909,
              "wilson95": [
                0.0162,
                0.3774
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 1.0,
            "recall_weighted": 0.0909
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
          "precision_conservative": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 3.0,
            "lower": 0.4385029682449546,
            "upper": 1.0,
            "K": 3,
            "N": 3,
            "clusters_passed": 3,
            "pass_threshold": 1.0
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 3.0,
            "lower": 0.4385029682449546,
            "upper": 1.0,
            "K": 3,
            "N": 3,
            "clusters_passed": 3,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 7.0,
            "lower": 0.02567962434474358,
            "upper": 0.5131278292743188,
            "K": 7,
            "N": 30,
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
            "lower": 0.030053369748306635,
            "upper": 0.5635028221864702,
            "K": 6,
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
            "n_eff": 6.0,
            "lower": 0.030053369748306635,
            "upper": 0.5635028221864702,
            "K": 6,
            "N": 16,
            "clusters_passed": 1,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.4664966515941171,
            "deff": 1.9754020896967903,
            "n_eff": 17.21168575113675,
            "lower": 0.010460400984997564,
            "upper": 0.26982030637575394,
            "K": 11,
            "N": 34
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
      "prompt_tokens": 69220,
      "completion_tokens": 15760,
      "elapsed_s": 289.823102,
      "latency_ms": {
        "p50": 13257.51,
        "p95": 57717.41
      },
      "false_duplicate": {
        "observed": 1,
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
        "reference_explicit": 2,
        "ungrounded_span": 0,
        "unknown_pair": 0,
        "unrelated": 148
      },
      "injection_signals": 0,
      "over_budget": false
    },
    {
      "variant": "B",
      "trial": 1,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 6,
          "covered": 6,
          "passed": 0,
          "precision_conservative": {
            "passed": 0,
            "denominator": 6,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.3903
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
            "denominator": 34,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.1015
            ]
          },
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
            "denominator": 29,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.117
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": 0.0,
          "recall_weighted": 0.0
        },
        "REFERENCE": {
          "denominator": 10,
          "covered": 10,
          "passed": 0,
          "precision_conservative": {
            "passed": 0,
            "denominator": 10,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.2775
            ]
          },
          "precision_observed": {
            "passed": 0,
            "denominator": 10,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.2775
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
              "denominator": 28,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1206
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
          },
          "REFERENCE": {
            "denominator": 10,
            "covered": 10,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 10,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2775
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 10,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2775
              ]
            },
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
              "denominator": 9,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2992
              ]
            },
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "direction_accuracy": null,
            "precision_weighted": 0.0,
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "denominator": 7,
            "covered": 7,
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
              "denominator": 7,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3543
              ]
            },
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
            "n_eff": 5.0,
            "lower": 0.0,
            "upper": 0.43448246478317465,
            "K": 5,
            "N": 6,
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
            "lower": 0.0,
            "upper": 0.43448246478317465,
            "K": 5,
            "N": 6,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 1.0,
            "deff": 3.090909090909091,
            "n_eff": 11.0,
            "lower": 0.0,
            "upper": 0.25883296696803165,
            "K": 11,
            "N": 34
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
            "n_eff": 3.0,
            "lower": 0.0,
            "upper": 0.5614970317550454,
            "K": 3,
            "N": 10,
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
            "N": 10,
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
        "passed": 0,
        "denominator": 101,
        "rate": 0.0,
        "wilson95": [
          0.0,
          0.0366
        ]
      },
      "llm_calls": 27,
      "prompt_tokens": 66334,
      "completion_tokens": 13862,
      "elapsed_s": 257.704343,
      "latency_ms": {
        "p50": 11171.8,
        "p95": 55596.28
      },
      "false_duplicate": {
        "observed": 1,
        "unreviewed": 0
      },
      "rejected": {
        "bad_span": 5,
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
        "unrelated": 141
      },
      "injection_signals": 0,
      "over_budget": false
    },
    {
      "variant": "B",
      "trial": 2,
      "by_label": {
        "GENERAL_SPECIFIC": {
          "denominator": 10,
          "covered": 10,
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
            "denominator": 10,
            "rate": 0.1,
            "wilson95": [
              0.0179,
              0.4042
            ]
          },
          "recall_observed": {
            "passed": 1,
            "denominator": 34,
            "rate": 0.0294,
            "wilson95": [
              0.0052,
              0.1492
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
          "recall_weighted": 0.0294
        },
        "CONFLICT": {
          "denominator": 3,
          "covered": 3,
          "passed": 3,
          "precision_conservative": {
            "passed": 3,
            "denominator": 3,
            "rate": 1.0,
            "wilson95": [
              0.4385,
              1.0
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
            "denominator": 30,
            "rate": 0.1,
            "wilson95": [
              0.0346,
              0.2562
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": 1.0,
          "recall_weighted": 0.1
        },
        "DUPLICATE": {
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
            "denominator": 29,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.117
            ]
          },
          "direction_accuracy": null,
          "precision_weighted": 0.0,
          "recall_weighted": 0.0
        },
        "REFERENCE": {
          "denominator": 6,
          "covered": 6,
          "passed": 0,
          "precision_conservative": {
            "passed": 0,
            "denominator": 6,
            "rate": 0.0,
            "wilson95": [
              0.0,
              0.3903
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
            "denominator": 7,
            "covered": 7,
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
              "denominator": 7,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3543
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
            "denominator": 3,
            "covered": 3,
            "passed": 3,
            "precision_conservative": {
              "passed": 3,
              "denominator": 3,
              "rate": 1.0,
              "wilson95": [
                0.4385,
                1.0
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
              "denominator": 25,
              "rate": 0.12,
              "wilson95": [
                0.0417,
                0.2996
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 1.0,
            "recall_weighted": 0.12
          },
          "DUPLICATE": {
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
              "denominator": 28,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.1206
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 0.0,
            "recall_weighted": 0.0
          },
          "REFERENCE": {
            "denominator": 6,
            "covered": 6,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 6,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.3903
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
              "denominator": 9,
              "rate": 0.0,
              "wilson95": [
                0.0,
                0.2992
              ]
            },
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
              "denominator": 14,
              "rate": 0.0714,
              "wilson95": [
                0.0127,
                0.3147
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 1.0,
            "recall_weighted": 0.0714
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "direction_accuracy": null,
            "precision_weighted": 0.0,
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
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
            "denominator": 0,
            "covered": 0,
            "passed": 0,
            "precision_conservative": {
              "passed": 0,
              "denominator": 0,
              "rate": null,
              "wilson95": [
                0.0,
                1.0
              ]
            },
            "precision_observed": {
              "passed": 0,
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
            "denominator": 2,
            "covered": 2,
            "passed": 2,
            "precision_conservative": {
              "passed": 2,
              "denominator": 2,
              "rate": 1.0,
              "wilson95": [
                0.3424,
                1.0
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
              "denominator": 11,
              "rate": 0.1818,
              "wilson95": [
                0.0514,
                0.477
              ]
            },
            "direction_accuracy": null,
            "precision_weighted": 1.0,
            "recall_weighted": 0.1818
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
          "precision_conservative": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 2.0,
            "lower": 0.34238022750665315,
            "upper": 1.0,
            "K": 2,
            "N": 3,
            "clusters_passed": 2,
            "pass_threshold": 1.0
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 2.0,
            "lower": 0.34238022750665315,
            "upper": 1.0,
            "K": 2,
            "N": 3,
            "clusters_passed": 2,
            "pass_threshold": 1.0
          },
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
            "n_eff": 5.0,
            "lower": 0.0,
            "upper": 0.43448246478317465,
            "K": 5,
            "N": 10,
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
            "lower": 0.0,
            "upper": 0.43448246478317465,
            "K": 5,
            "N": 10,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "recall_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "icc-upper",
            "icc": 0.6846967061242092,
            "deff": 2.4316385673506193,
            "n_eff": 13.982341149097888,
            "lower": 0.0,
            "upper": 0.21531080273763575,
            "K": 11,
            "N": 34
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
            "N": 6,
            "clusters_passed": 0,
            "pass_threshold": 1.0
          },
          "precision_observed": {
            "method": "harness.scripts.wilson.cluster_adjusted",
            "conf": 0.95,
            "route": "cluster-floor",
            "icc": null,
            "deff": null,
            "n_eff": 2.0,
            "lower": 0.0,
            "upper": 0.6576197724933468,
            "K": 2,
            "N": 6,
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
      "llm_calls": 27,
      "prompt_tokens": 66334,
      "completion_tokens": 14336,
      "elapsed_s": 267.43472,
      "latency_ms": {
        "p50": 11562.8,
        "p95": 57106.7
      },
      "false_duplicate": {
        "observed": 1,
        "unreviewed": 0
      },
      "rejected": {
        "bad_span": 1,
        "citation_invalid": 0,
        "conflict_same_span": 0,
        "duplicate_id": 0,
        "duplicate_value_mismatch": 3,
        "invalid_label": 0,
        "malformed": 0,
        "missing_direction": 0,
        "no_answer": 0,
        "reference_explicit": 1,
        "ungrounded_span": 0,
        "unknown_pair": 0,
        "unrelated": 140
      },
      "injection_signals": 0,
      "over_budget": false
    }
  ]
}
```
