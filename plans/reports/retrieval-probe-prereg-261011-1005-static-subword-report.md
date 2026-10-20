# Preregistration: semantic retrieval probe from cached multilingual weights

Date: 2026-10-11

## Hypothesis

The current lexical rankers may miss semantic restatements across articles. A cheap offline proxy based on the cached multilingual MiniLM subword embedding table may retrieve complementary cross-article pairs. This is a diagnostic of a retrieval signal, not a SentenceTransformer inference result and not a runtime candidate.

## Frozen inputs and procedure

- Read only the existing 32-document approved development frame and its review labels; no held-out data.
- Use the locally cached `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` SentencePiece model and its input token embedding matrix. For each clause, average its subword input vectors and rank eligible, non-ancestor, non-Luong-1 cross-article pairs by cosine similarity.
- Compare exactly two outputs: (1) semantic cross-article top-40 per document; (2) a fixed cap blend retaining 32 current C/40 candidates, adding up to 8 semantic candidates, then backfilling C/40. No label-based parameter sweep.
- Report candidate recall by label, overlap with the reviewed frame, total emitted candidates, time and peak memory. The diagnostic must not be described as a complete fix even if it improves recall.

## Limits

The average of static input token vectors omits all Transformer context layers and SentenceTransformer pooling/normalization. A weak result would reject only this cheap proxy; a strong result would justify a separately budgeted full-encoder trial, not runtime integration. This experiment uses the existing 37-positive dev frame and is therefore selection evidence, not independent validation. Any eventual candidate version change invalidates the existing S4/HG-1/HG-2 universe locks.

## Kết quả: proxy tĩnh

Proxy trung bình các input subword vector đạt semantic top-40 7/37 (CONFLICT 1/1, DUPLICATE 0/2, GENERAL_SPECIFIC 4/27, REFERENCE 2/7), 1.197 candidates; reviewed-frame overlap: 40 dòng, trong đó 33 negatives. Blend C32+semantic fill đạt 14/37; 1.200 candidates; reviewed-frame overlap: 77 dòng, gồm 63 negatives. Thời gian 13,27 giây và peak allocation Python 5 MiB. Kết quả chỉ là proxy, không phải model inference.

## Kết quả bổ sung: full Transformer

Ngày 2026-10-11, chạy thêm bằng cache local `paraphrase-multilingual-MiniLM-L12-v2`, mean pooling theo attention mask và L2 normalization; không gọi endpoint/API, không đọc held-out. Đây là kiểm tra full encoder tiếp nối đã nêu trong phần Limits, trên đúng 32 tài liệu/37 positives dev.

- Semantic cross-article top-40/doc: 7/37 (CONFLICT 1/1, DUPLICATE 0/2, GENERAL_SPECIFIC 4/27, REFERENCE 2/7), 1.197 candidates; reviewed-frame overlap: 39 reviewed, 1.158 unreviewed.
- Blend cố định C32 + tối đa 8 semantic fill + backfill C40: 14/37; 1.200 candidates; reviewed-frame overlap: 77 reviewed, 1.123 unreviewed.
- Thời gian 59,58 giây CPU cho 32 tài liệu, bao gồm nạp model.

Kết quả full encoder trùng recall theo nhãn với proxy embedding tĩnh (7/37 và 14/37), nên ngữ cảnh Transformer ở model này chưa thể hiện cải thiện hữu ích tại quota cố định. Đây vẫn là phép chọn hướng trên cùng dev set, không phải independent validation. Không đủ căn cứ đưa semantic selector này vào runtime hoặc gọi đây là khắc phục recall.
