# P3 â€” GÃ³i duyá»‡t corpus development v2

**Tráº¡ng thÃ¡i:** `BLOCKED_REVIEW_PENDING`
**Dataset:** `quality-recovery-dev-20261011-v2`
**Frame:** `contract-graph-quality-frame/2`
**Káº¿ thá»«a:** giá»¯ nguyÃªn v1; SHA-256 manifest predecessor `4f4f51d89dfad7f9c95169287106595150584a031dda1ade90760ed335d270ab`.

## Corpus vÃ  máº«u

- CÃ³ 34 tÃ i liá»‡u dÃ¹ng Ä‘Æ°á»£c. Loáº¡i 2 tÃ i liá»‡u/cá»¥m cÃ³ dáº¥u váº¿t held-out hoáº·c template exposure; cÃ²n 32 tÃ i liá»‡u thuá»™c 31 cá»¥m fresh Ä‘á»™c láº­p.
- Pool fresh cÃ³ 4.834 cáº·p: S1 3.427, S2 200, S3 1.207.
- Phiáº¿u chÃ­nh mÃ¹ cÃ³ 600 cáº·p; phiáº¿u Ä‘á»™c láº­p mÃ¹ cÃ³ 150 cáº·p (25%). Cáº£ 31 cá»¥m fresh Ä‘á»u Ä‘Æ°á»£c Ä‘áº¡i diá»‡n.
- Máº«u Ä‘Æ°á»£c rÃºt khÃ´ng hoÃ n láº¡i theo Ã´ cá»¥m Ä‘á»™c láº­p Ã— pool stratum, cÃ³ Ã­t nháº¥t má»™t cáº·p trong má»—i Ã´ cÃ³ dá»¯ liá»‡u; pháº§n cÃ²n láº¡i Ä‘Æ°á»£c phÃ¢n bá»• theo dung lÆ°á»£ng Ã´ báº±ng seed cá»‘ Ä‘á»‹nh.
- Cá»™t quyáº¿t Ä‘á»‹nh, nhÃ£n, hÆ°á»›ng vÃ  ghi chÃº trong cáº£ hai CSV váº«n Ä‘á»ƒ trá»‘ng. Clause text vÃ  membership á»Ÿ `.harness/state/quality-recovery-p3-dev-20261011-v2/`; Ä‘Æ°á»ng dáº«n Ä‘Ã£ Ä‘Æ°á»£c xÃ¡c nháº­n git-ignore.
- Precision frame hiá»‡n lÃ  seed cÃ¹ng membership recall. P4 pháº£i bá»• sung vÃ  review toÃ n bá»™ candidate union trÆ°á»›c khi cháº¥m precision.

## Review cáº§n lÃ m

1. NgÆ°á»i review chÃ­nh Ä‘iá»n `primary-blind-v2.csv` theo [rubric](../pairs/LABELING.vi.md). `GENERAL_SPECIFIC` vÃ  `REFERENCE` cáº§n hÆ°á»›ng A/B.
2. Má»™t ngÆ°á»i khÃ¡c Ä‘iá»n `independent-blind-v2.csv` mÃ  khÃ´ng xem quyáº¿t Ä‘á»‹nh cá»§a reviewer chÃ­nh. Gá»£i Ã½ AI cÃ³ thá»ƒ há»— trá»£ reviewer chÃ­nh riÃªng, nhÆ°ng khÃ´ng thay reviewer Ä‘á»™c láº­p vÃ  khÃ´ng Ä‘Æ°á»£c ghi lÃ  human review.
3. Sau import, kiá»ƒm tra agreement, yield theo nhÃ£n/cá»¥m, negatives vÃ  adjudication; má»Ÿ rá»™ng blind subset náº¿u thiáº¿u Ä‘á»™ phá»§.
4. NgÆ°á»i dÃ¹ng xÃ¡c nháº­n HG-QR1 cho hashes vÃ  scope v2; chá»‰ sau Ä‘Ã³ má»›i táº¡o approved gold vÃ  P2 review lock.

## Gate cÃ²n má»Ÿ

- ChÆ°a cÃ³ annotation, adjudication, reviewer Ä‘á»™c láº­p, HG-QR1 approval hoáº·c reviewed gold.
- Candidate union precision chÆ°a Ä‘Æ°á»£c dá»±ng (P4).
- P4/P5 váº«n khÃ³a Ä‘áº¿n khi P3 review evidence Ä‘áº¡t gate.

## Hashes

- Source inventory: `4c114ff7f0c72329d96162f33935028112b1557c1f04697b401fda2ff8227b12`
- Rubric: `7f01c0826f0b068127d49f5d0b44c7b06f04a326abcc37cffc222e9f92d19d55`
- Phiáº¿u chÃ­nh: `d813bc43edcdab271c65c541c37ca09102013681f83600d9eb88caa499ef7d3b`
- Phiáº¿u Ä‘á»™c láº­p: `018cec9801496cfb7dc2857eb021f8e1cf3ca23b710952dedf7662f66235a4d7`
- Recall membership: `53b124e0f5814d03f9c159a26f29e3dae7821e5b4ada1460faf8557abd320ddb`
- Independent membership: `8a74409b486097f113d0943870407d14f05fcd6750f634c99e280f780faad5ec`
- Precision seed: `0a446ac5fb94c62b861c72789320f5264874f9a37f335fceb1ce6346f72f197c`
- Fresh pool: `d989effb05941914b145046e1762f16aac20e91eb81deab08cf23505fbf48ef3`
