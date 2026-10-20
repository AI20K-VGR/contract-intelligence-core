# Gá»¡ nÃºt tháº¯t candidate retrieval: scale game

NgÃ y: 2026-10-11
Pháº¡m vi: replay tá»•ng há»£p cá»¥c bá»™, khÃ´ng gá»i model, khÃ´ng Ä‘á»c held-out, khÃ´ng sá»­a code.

## Loáº¡i nÃºt tháº¯t

ÄÃ£ thá»­ nhiá»u cÃ¡ch sá»­a nguá»“n vÃ  xáº¿p háº¡ng, nhÆ°ng chÆ°a cÃ¡ch nÃ o qua candidate target. CÃ²n hai cÃ¢u há»i bá»‹ gá»™p: liá»‡u cap 40 cÃ³ giá»›i háº¡n chi phÃ­ táº¡o á»©ng viÃªn khÃ´ng, vÃ  liá»‡u cÃ¡ch giáº£m chi phÃ­ cÃ³ tÄƒng recall khÃ´ng. DÃ¹ng ká»¹ thuáº­t scale game Ä‘á»ƒ kiá»ƒm tra cÃ¢u há»i Ä‘áº§u; káº¿t quáº£ khÃ´ng Ä‘Æ°á»£c diá»…n giáº£i thÃ nh báº±ng chá»©ng cáº£i thiá»‡n recall.

## Báº±ng chá»©ng á»Ÿ quy mÃ´ nhá» vÃ  lá»›n

Fixture tá»•ng há»£p táº¡o má»™t Ä‘iá»u khoáº£n cÃ³ `n` khoáº£n Ä‘á»§ Ä‘iá»u kiá»‡n, táº¥t cáº£ cÃ¹ng SAME_ARTICLE. Gá»i runtime generator vá»›i `top_k=40`, Ä‘o thá»i gian vÃ  peak allocation báº±ng `tracemalloc`.

| Khoáº£n Ä‘á»§ Ä‘iá»u kiá»‡n | á»¨ng viÃªn táº¡o trÆ°á»›c cap | Cáº·p giá»¯ láº¡i | Thá»i gian | Peak allocation |
|---:|---:|---:|---:|---:|
| 10 | 45 | 40 | 0,008 s | 0,07 MiB |
| 50 | 1.225 | 40 | 0,102 s | 1,12 MiB |
| 100 | 4.950 | 40 | 0,375 s | 4,09 MiB |
| 250 | 31.125 | 40 | 2,986 s | 26,54 MiB |
| 500 | 124.750 | 40 | 12,004 s | 105,38 MiB |

> ÄÃ¢y lÃ  fixture tá»•ng há»£p, khÃ´ng pháº£i phÃ¢n phá»‘i há»£p Ä‘á»“ng sáº£n pháº©m. CÃ¡c Ä‘iá»ƒm 1.000, 5.000 vÃ  10.000 khoáº£n khÃ´ng Ä‘Æ°á»£c cháº¡y; sá»‘ cáº·p tÆ°Æ¡ng á»©ng 499.500, 12.497.500 vÃ  49.995.000 chá»‰ lÃ  cÃ´ng thá»©c tá»• há»£p `n(n-1)/2`, khÃ´ng pháº£i sá»‘ Ä‘o thá»i gian/bá»™ nhá»›.

## CÆ¡ cháº¿ gÃ¢y tÄƒng báº­c hai

á»ž `ai-service/app/pipeline/contract_graph/pair_candidates.py:202-210`, SAME_ARTICLE duyá»‡t má»i cáº·p thÃ nh viÃªn trong má»—i nhÃ³m. CÃ¡c cáº·p Ä‘Æ°á»£c gom vÃ o `found` vÃ  chuyá»ƒn thÃ nh `PairCandidate` á»Ÿ `:257-270`; sau Ä‘Ã³ toÃ n danh sÃ¡ch Ä‘Æ°á»£c sáº¯p xáº¿p á»Ÿ `:271`. Cap chá»‰ Ä‘Æ°á»£c Ã¡p dá»¥ng tá»« `:272` trá»Ÿ Ä‘i, qua nhÃ¡nh core á»Ÿ `:273-294`. VÃ¬ váº­y `top_k=40` giá»›i háº¡n sá»‘ cáº·p tráº£ ra classifier, nhÆ°ng khÃ´ng giá»›i háº¡n sá»‘ cáº·p Ä‘Æ°á»£c táº¡o, cáº¥p phÃ¡t vÃ  sáº¯p xáº¿p.

ÄÃ¢y lÃ  **váº¥n Ä‘á» scale/performance xÃ¡c nháº­n Ä‘Æ°á»£c**, tÃ¡ch biá»‡t vá»›i recall: benchmark C/40 trÃªn frame dev sinh 1.000 á»©ng viÃªn cho 32 tÃ i liá»‡u; bá» cap sinh 11.143 nhÆ°ng chá»‰ tÄƒng candidate recall tá»« 11/37 lÃªn 29/37 vÃ  váº«n bá» tÃ¡m cáº·p do thiáº¿u source. Tá»‘i Æ°u sinh/cáº¯t danh sÃ¡ch tá»± nÃ³ khÃ´ng táº¡o ra cÃ¡c cáº·p bá»‹ thiáº¿u.

## PhÃ©p Ä‘áº£o giáº£ Ä‘á»‹nh

Giáº£ Ä‘á»‹nh máº·c Ä‘á»‹nh lÃ  má»i cáº·p cÃ¹ng Ä‘iá»u khoáº£n Ä‘Ã¡ng Ä‘Æ°a vÃ o candidate universe. Äáº£o thÃ nh â€œchá»‰ giá»¯ ká» cáº­nâ€ giáº£m táº¡o clique, nhÆ°ng khÃ´ng thá»ƒ dÃ¹ng lÃ m fix recall náº¿u chÆ°a Ä‘o: cÃ¡c cáº·p dÆ°Æ¡ng tÃ­nh bá»‹ cap hiá»‡n táº¡i pháº§n lá»›n lÃ  SAME_ARTICLE vÃ  cÃ³ rank 46â€“1.898; loáº¡i clique cÃ³ thá»ƒ lÃ m máº¥t thÃªm cáº·p Ä‘Ãºng. CÃ¡ch Ä‘áº£o cÃ³ thá»ƒ kiá»ƒm chá»©ng hÆ¡n lÃ  sinh candidate theo luá»“ng cÃ³ shortlist giá»›i háº¡n, Ä‘á»“ng thá»i giá»¯ cÃ¡c tÃ­n hiá»‡u cáº¥u trÃºc/explicit vÃ  má»™t kÃªnh liÃªn Ä‘iá»u khoáº£n riÃªng. Tuy nhiÃªn, shortlist váº«n pháº£i Ä‘Æ°á»£c Ä‘Ã¡nh giÃ¡ trÃªn frame phÃ¹ há»£p; scale test nÃ y chÆ°a xÃ¡c nháº­n recall cá»§a nÃ³.

## Káº¿t luáº­n vÃ  bÆ°á»›c káº¿ tiáº¿p

- Candidate recall váº«n chÆ°a Ä‘Æ°á»£c sá»­a: C/40 lÃ  11/37; 8 cáº·p thiáº¿u source vÃ  18 cáº·p bá»‹ loáº¡i bá»Ÿi cap.
- Bá»™ sinh hiá»‡n táº¡i cÃ³ thá»ƒ vÆ°á»£t thá»i gian/bá»™ nhá»› dÃ¹ output cap lÃ  40; khÃ´ng Ä‘Æ°á»£c tÄƒng K hoáº·c chuyá»ƒn sang uncapped theo suy luáº­n ráº±ng cap Ä‘Ã£ giá»›i háº¡n chi phÃ­.
- BÆ°á»›c ká»¹ thuáº­t káº¿ tiáº¿p lÃ  thiáº¿t káº¿ má»™t retriever hai táº§ng cÃ³ giá»›i háº¡n ngay trong khÃ¢u sinh: source chÃ­nh xÃ¡c; sau Ä‘Ã³ shortlist Ä‘a dáº¡ng theo Ä‘iá»u khoáº£n/topic/cross-article, khÃ´ng materialize clique Ä‘áº§y Ä‘á»§. Äo riÃªng chi phÃ­ vÃ  recall trÆ°á»›c khi thay runtime.
- Báº±ng chá»©ng dev hiá»‡n cÃ³ chÆ°a Ä‘á»§ Ä‘á»ƒ chá»n biáº¿n thá»ƒ má»›i: chá»‰ 37 positive (1 CONFLICT, 2 DUPLICATE, 27 GENERAL_SPECIFIC, 7 REFERENCE); hai tÃ i liá»‡u ngoÃ i frame bá»‹ Ä‘Ã¡nh dáº¥u contaminated. Cáº§n nguá»“n dev sáº¡ch Ä‘Ã£ duyá»‡t Ä‘á»ƒ xÃ¡c nháº­n rule má»›i. P4/P5 váº«n khÃ³a, held-out chÆ°a Ä‘á»c, runtime OFF.

KhÃ´ng sá»­a code hoáº·c thay candidate version trong láº§n kiá»ƒm tra nÃ y. KhÃ´ng cháº¡y test suite vÃ¬ khÃ´ng cÃ³ implementation thay Ä‘á»•i.

## Bá»• sung: Ä‘Ã£ thá»­ retriever dense Ä‘Ã£ huáº¥n luyá»‡n

Theo preregistration má»›i, BGE-M3 CLS dense retrieval cháº¡y trÃªn cÃ¹ng 32 tÃ i liá»‡u/37 positives. Semantic top-40 Ä‘áº¡t 8/37; blend C32+semantic fill Ä‘áº¡t 16/37 vá»›i 1.200 candidate, nhÆ°ng máº¥t 590,83 giÃ¢y vÃ  quan sÃ¡t working set khoáº£ng 2,1 GB. So vá»›i MiniLM blend 14/37, BGE-M3 chá»‰ tÄƒng thÃªm hai cáº·p, váº«n há»¥t 20 positives so vá»›i dev target 36/37. KhÃ´ng dÃ¹ng model trong runtime.

Káº¿t luáº­n cáº­p nháº­t: báº±ng chá»©ng hiá»‡n táº¡i xÃ¡c Ä‘á»‹nh rÃµ hai pháº§n lá»—i (8 source misses vÃ  18 cáº·p bá»‹ top-40 loáº¡i) vÃ  má»™t váº¥n Ä‘á» scale riÃªng (SAME_ARTICLE táº¡o clique trÆ°á»›c cap). CÃ¡c biáº¿n thá»ƒ proximity/model Ä‘Ã£ thá»­ khÃ´ng Ä‘áº¡t gate. Dá»¯ liá»‡u hiá»‡n khÃ³a chá»‰ 37 positives, trong Ä‘Ã³ nhÃ£n DUPLICATE/REFERENCE/CONFLICT láº§n lÆ°á»£t 2/7/1; hai tÃ i liá»‡u ngoÃ i frame bá»‹ Ä‘Ã¡nh dáº¥u contaminated, nÃªn khÃ´ng thá»ƒ dÃ¹ng chÃºng Ä‘á»ƒ tune hay xÃ¡c nháº­n. KhÃ´ng cÃ²n phÃ©p Ä‘á»•i model/ranking nÃ o Ä‘Æ°á»£c chá»©ng minh lÃ  fix. BÆ°á»›c cáº§n thiáº¿t Ä‘á»ƒ Ä‘i tiáº¿p lÃ  táº¡o tranche dev sáº¡ch má»›i, khÃ³a cluster/doc trÆ°á»›c khi xem nhÃ£n, review positives Ä‘á»§ cÃ¡c loáº¡i relation; sau Ä‘Ã³ thiáº¿t káº¿ bounded hybrid source+diversified ranker vÃ  Ä‘Ã¡nh giÃ¡ trÃªn pháº§n cluster giá»¯ riÃªng. Runtime OFF; P4/P5 vÃ  held-out khÃ´ng má»Ÿ.
