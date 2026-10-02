# Candidate review worksheet

Review the cited fixture source independently. This worksheet intentionally omits previous labels and system output.

| ID | Source | Source SHA-256 | Title | Scenario / notes | Pages / nodes | Tags |
|---|---|---|---|---|---:|---|
| EC-001 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Hợp đồng 62 trang — scout, không dump PDF | 62 pages; only get_node on MST unit | 62 / 22 | edge, router |
| EC-002 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Điều khoản dài 4 trang, chunk theo bullet |  | 4 / 5 | edge, clause |
| EC-003 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Không đánh số — UNNUMBERED_BLOCK |  | 1 / 1 | edge, structure |
| EC-004 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Trùng số Điều 5 body vs annex |  | 2 / 4 | edge, structure |
| EC-005 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Nhảy số thiếu Điều 3 — không bịa clause |  | 1 / 3 | edge, structure |
| EC-006 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Numbering hỗn hợp Article/Điều/(a) |  | 1 / 3 | edge, structure |
| EC-007 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Header/footer xen — không nối mù |  | 3 / 2 | edge, reconstruction |
| EC-008 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Definition được tham chiếu |  | 2 / 3 | edge, retrieval |
| EC-009 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Tham chiếu phụ lục không có trong dossier |  | 1 / 1 | edge, retrieval |
| EC-010 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Bảng 300 dòng — codegen, không dump hết vào LLM |  | 1 / 2 | edge, table |
| EC-011 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Bảng hai trang continuation |  | 2 / 2 | edge, table |
| EC-012 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Subtotal/footnote — không tự cộng thiếu |  | 1 / 1 | edge, table |
| EC-013 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Merged cell trỏ cell nguồn |  | 1 / 1 | edge, table |
| EC-014 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Header hai tầng raw path |  | 1 / 2 | edge, table |
| EC-015 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Empty/dash/N/A/zero khác missing |  | 1 / 1 | edge, table |
| EC-016 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | 1.234 vs 1,234 vs ngoặc âm — giữ raw |  | 1 / 2 | edge, table |
| EC-017 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Hai bảng cùng số cột — không nối |  | 1 / 2 | edge, table |
| EC-018 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Cell OCR tách nhiều row |  | 1 / 1 | edge, table |
| EC-019 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Bảng xoay 90 — citation theo revision |  | 1 / 2 | edge, citation |
| EC-020 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | MST lặp/lệch cùng tên |  | 2 / 4 | edge, fact |
| EC-021 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Số bằng chữ khác/cần hai anchor |  | 1 / 2 | edge, fact |
| EC-022 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Ngày tương đối — không bịa mốc |  | 1 / 1 | edge, fact |
| EC-023 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Giá trị bậc thang giữ condition |  | 1 / 3 | edge, fact |
| EC-024 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | USD vs VND không quy đổi |  | 1 / 2 | edge, candidate |
| EC-025 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Alias chỉ từ profile pin v5 |  | 1 / 2 | edge, profile |
| EC-026 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Tên giống MST khác — link không merge |  | 1 / 4 | edge, entity |
| EC-027 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Body/table/annex mâu thuẫn — không chọn bản đúng |  | 3 / 3 | edge, candidate |
| EC-028 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Implicit amendment thiếu câu sửa rõ |  | 2 / 2 | edge, compare |
| EC-029 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Nhiều annex cùng sửa — không precedence |  | 2 / 3 | edge, compare |
| EC-030 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Khác scope NOT_COMPARABLE |  | 1 / 3 | edge, candidate |
| EC-031 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Song ngữ lệch nghĩa |  | 2 / 2 | edge, compare |
| EC-032 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Cosmetic vs substantive — align trước LLM |  | 1 / 3 | edge, compare |
| EC-033 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Defined-term cascade không legal winner |  | 2 / 2 | edge, compare |
| EC-034 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Aggregation thiếu một source |  | 1 / 1 | edge, retrieval |
| EC-035 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Prompt injection trong PDF — chỉ allowlist |  | 1 / 1 | edge, security |
| EC-036 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Index processing — dùng active idx_14 |  | 1 / 6 | edge, index |
| EC-037 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Query EN, doc VI |  | 1 / 6 | edge, retrieval |
| EC-038 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Overlap duplicate — dedupe source key |  | 2 / 3 | edge, dedupe |
| EC-039 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Confidence cao nhưng sai — grounding |  | 1 / 1 | edge, grounding |
| EC-040 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Boundary ambiguous |  | 1 / 1 | edge, router |
| EC-041 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Skew/watermark — không đoán |  | 1 / 1 | edge, scan |
| EC-042 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Chữ ký che số |  | 1 / 1 | edge, scan |
| EC-043 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Scan không đều — giữ denominator 3 trang |  | 3 / 1 | edge, scan |
| EC-044 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | OCR sai dấu tiếng Việt — raw riêng |  | 1 / 1 | edge, fact |
| EC-045 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Encrypted PDF |  | 1 / 0 | edge, intake |
| EC-046 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Trang trắng giữ inventory |  | 3 / 1 | edge, intake |
| EC-047 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | File vượt budget — partial |  | 20 / 20 | edge, orchestrator |
| EC-048 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Nhiều annex — queue/checkpoint |  | 16 / 16 | edge, queue |
| EC-049 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Rerun đồng thời — worker cũ không publish |  | 1 / 6 | edge, worker |
| EC-050 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Embedding cost gate |  | 1 / 6 | edge, cost |
| EC-051 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Profile đổi — run mới giữ result cũ |  | 1 / 2 | edge, versioning |
| EC-052 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Re-OCR page — citation revision mới, cũ stale |  | 1 / 1 | edge, lineage |
| EC-053 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Vector/query cross-tenant |  | 1 / 6 | edge, acl |
| EC-054 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Cache hit nhưng ACL revision cũ |  | 1 / 6 | edge, acl |
| EC-055 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Egress chưa approval |  | 1 / 6 | edge, policy |
| EC-056 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Legal hold / soft-delete — [đã ẩn nhãn] |  | 1 / 6 | edge, lifecycle |
| HAPPY-001 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Hợp đồng ngắn sạch, parties and value grounded |  | 1 / 6 | happy, fact |
| HAPPY-002 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Bảng đủ ô, không missing |  | 1 / 2 | happy, table |
| HAPPY-003 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | ACL READ_CONTENT cho phép |  | 1 / 6 | happy, acl |
| HAPPY-004 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Query tiếng Việt khớp structured key |  | 1 / 6 | happy, query |
| HAPPY-005 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Song ngữ cùng nghĩa 15 ngày |  | 2 / 5 | happy, compare |
| HAPPY-006 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | Actor không có ACL — [đã ẩn nhãn] (control) |  | 1 / 6 | happy, acl |
| HD-TONG-HOP | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | HĐ chính 50 trang + 15 phụ lục — phủ edge khó (tiếng Việt) | Human text: fixtures/contracts/HD-TONG-HOP.vi.md | 65 / 71 | full, vi, happy, edge |
| SALE-BRD-07 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | DOC-02 §7 SALE: sửa A, B không đổi, PL2 thiếu kỳ, thiếu PL9 |  | 3 / 8 | brd, compare, sale |
| SERVICE-BRD-08 | ai-service/fixtures/catalog.py | 55b37a10f799270cdee090f02d935b02adde85e9d1fcb34c11b6465e7129947b | DOC-02 §8 SERVICE: X 50/40 comparable; Y khác scope NOT_COMPARABLE |  | 3 / 6 | brd, compare, service |
| SYN-001 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | 100-page target-at-end | 50–100 trang; thông tin cần tìm chỉ nằm ở trang cuối. | 100 / 71 | synthetic, full_flow |
| SYN-002 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | distractor clauses | Nhiều điều khoản gần giống nhau; chỉ một node có điều kiện đúng. | 65 / 71 | synthetic, full_flow |
| SYN-003 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | duplicate body and annex | Cùng một câu xuất hiện ở thân và phụ lục, cần giữ hai nguồn. | 65 / 71 | synthetic, full_flow |
| SYN-004 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | gaps and mixed numbering | Điều 2 bị thiếu, thứ tự hiển thị không liên tục. | 65 / 71 | synthetic, full_flow |
| SYN-005 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | header footer noise | Header/footer lặp lại không được coi là điều khoản. | 65 / 71 | synthetic, full_flow |
| SYN-006 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | blank low rotation page | Trang rỗng, OCR thấp và xoay 90 độ phải hạ confidence. | 65 / 71 | synthetic, full_flow |
| SYN-007 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | duplicate OCR lineage | Hai bản OCR cùng nguồn; không được đếm thành hai sự thật. | 65 / 71 | synthetic, full_flow |
| SYN-008 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | many and missing annexes | Có nhiều phụ lục nhưng thiếu một phụ lục được dẫn chiếu. | 65 / 71 | synthetic, full_flow |
| SYN-009 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | explicit cross-document references | Dẫn chiếu rõ Điều 5 và Phụ lục 1. | 65 / 71 | synthetic, full_flow |
| SYN-010 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | multi-hop relationship | Điều khoản → định nghĩa → phụ lục → dòng bảng. | 65 / 71 | synthetic, full_flow |
| SYN-011 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | circular ambiguous references | Hai điều khoản dẫn chiếu vòng và một tham chiếu mơ hồ. | 65 / 71 | synthetic, full_flow |
| SYN-012 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | defined term three hops | Thuật ngữ được định nghĩa ở Điều 1, dùng ở Điều 8 và bảng. | 65 / 71 | synthetic, full_flow |
| SYN-013 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | amendment effective date | Phụ lục sửa đổi có ngày hiệu lực muộn hơn hợp đồng. | 65 / 71 | synthetic, full_flow |
| SYN-014 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | conflicting amendments | Hai phụ lục cùng sửa một trường với ngày hiệu lực chồng lấn. | 65 / 71 | synthetic, full_flow |
| SYN-015 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | implicit amendment | Ngôn ngữ sửa đổi không dùng từ khóa chuẩn; cần [đã ẩn nhãn]. | 65 / 71 | synthetic, full_flow |
| SYN-016 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | OCR digit and diacritic errors | MST và dấu tiếng Việt bị OCR sai một phần. | 65 / 71 | synthetic, full_flow |
| SYN-017 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | number formats | Số kiểu 1.234,56; 1,234.56 và khoảng trắng cần phân biệt locale. | 65 / 71 | synthetic, full_flow |
| SYN-018 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | currency unit VAT scope | Giá trị, đơn vị, tiền tệ, VAT và phạm vi áp dụng tách riêng. | 65 / 71 | synthetic, full_flow |
| SYN-019 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | dates and periods | Ngày ký, ngày hiệu lực và kỳ thanh toán khác nhau. | 65 / 71 | synthetic, full_flow |
| SYN-020 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | same name different tax id | Hai pháp nhân trùng tên nhưng MST khác; phải [đã ẩn nhãn] conflict. | 65 / 71 | synthetic, full_flow |
| SYN-021 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | table explicitly not present | AI1 xác nhận không có bảng; không được tự dựng bảng. | 65 / 71 | synthetic, full_flow |
| SYN-022 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | table without cells or geometry | Có bảng nhưng AI1 không có cells/bbox; chỉ giữ issue/evidence. | 65 / 71 | synthetic, full_flow |
| SYN-023 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | continued table repeated header | Bảng tiếp trang có header lặp, cần nối đúng dòng. | 65 / 71 | synthetic, full_flow |
| SYN-024 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | merged two-level table and footnote | Bảng merged cell, header hai tầng và footnote. | 65 / 71 | synthetic, full_flow |
| SYN-025 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | missing dash NA zero | Phân biệt thiếu dữ liệu, dấu gạch, N/A và số 0. | 65 / 71 | synthetic, full_flow |
| SYN-026 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | subtotal total evidence | Subtotal/total phải có citation và không cộng đúp. | 65 / 71 | synthetic, full_flow |
| SYN-027 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | split duplicate rows | Một dòng bị tách/nhân đôi qua OCR. | 65 / 71 | synthetic, full_flow |
| SYN-028 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | 1000-row table | Bảng 300–1000 dòng; xử lý theo batch và không đưa toàn bộ vào prompt. | 65 / 71 | synthetic, full_flow |
| SYN-029 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | prompt injection in evidence | Văn bản nguồn chứa instruction giả; chỉ coi là dữ liệu. | 65 / 71 | synthetic, full_flow |
| SYN-030 | ai-service/fixtures/eval_suite.py | fe4b456619e05f6135a963202f0652b3b3bf3e046b93640c5d47fd39622891cf | provider faults and stale vector | Malformed JSON, timeout/429, sai dimension, stale vector và budget guard đều phải fail safe. | 65 / 71 | synthetic, full_flow |
