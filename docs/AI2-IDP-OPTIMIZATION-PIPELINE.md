# AI2 · IDP và Optimization Pipeline

AI2 không OCR lại PDF, không suy role contract/annex từ filename, không tạo bbox OCR, và không đưa ra kết luận pháp lý. Đầu vào bắt buộc là `ai1.snapshot.v1` đã qua schema/provenance validation.

```mermaid
flowchart LR
    AI1[AI1 Snapshot<br/>raw line/word · bbox · render digest] --> VAL[AI2 Snapshot Validator]
    MAN[Confirmed Dossier Manifest<br/>contract · annex · relation] --> VAL
    VAL -->|valid evidence| ST[Structure Engine<br/>Điều · Khoản · Điểm]
    VAL -->|missing/invalid evidence| EQ[Evidence Queue<br/>PARTIAL / QUARANTINED]

    ST --> TB[Table + Reading-order Binding]
    TB --> FX[Fact Extraction<br/>raw value · typed value]
    FX --> CTX[Normalizer + Context Gate<br/>subject · unit · currency · VAT · scope · validity]
    CTX --> CIT[Citation Builder<br/>raw span · line/word/table refs]
    CIT --> AL[Annex Link Candidate]
    AL --> PAIR[Deterministic Pair Generator]
    PAIR --> CMP[Structured Comparator]
    CMP --> SEM[Semantic Candidate<br/>approved-only · grounded]

    SEM --> D{Evidence + context valid?}
    D -->|two valid sides| CF[Conflict / Amendment Candidate]
    D -->|evidence missing| NE[Needs Evidence]
    D -->|context incompatible| NC[Not Comparable]

    CF --> RI[Review Item]
    NE --> RI
    NC --> RI
    RI --> REV[Append-only Review Revision<br/>confirm · correct · reject · request evidence]

    subgraph OPT["AI2 Optimization Loop — DEV only"]
        GOLD[Adjudicated DEV Gold<br/>facts · citations · dispositions]
        BASE[Baseline AI2 Config<br/>rules · normalizer · pair policy]
        RUN[Paired Evaluation]
        SCORE[Metric Engine<br/>fact/citation/context/F1]
        ERR[Redacted Error Slices]
        AGENT[Optimizer Sandbox<br/>typed candidate patch]
        CAND[Immutable Candidate Config]

        GOLD --> RUN
        BASE --> RUN
        RUN --> SCORE
        SCORE --> ERR
        ERR --> AGENT
        AGENT --> CAND
        CAND --> RUN
    end

    CAND -. only after sealed evaluation + approval .-> BASE

    style EQ fill:#fff1f1,stroke:#c34c4c
    style NE fill:#fff8e1,stroke:#c89820
    style NC fill:#f4f4f4,stroke:#777
    style OPT fill:#edf5ff,stroke:#4c81b8
```

## Nguyên tắc AI2

- `Conflict` chỉ xuất hiện khi hai phía có citation/evidence hợp lệ; thiếu evidence luôn vào `Needs Evidence`.
- Candidate amendment là cảnh báo kỹ thuật, không chọn văn bản có hiệu lực.
- Mọi `Fact`, `Citation`, `Finding` và run đều pin snapshot, manifest, rule/config version.
- Optimizer AI2 chỉ thay rules, normalization, pair policy hoặc prompt-template ID trong allowlist; không đọc raw holdout, không tự promotion và không thay đổi production config.
