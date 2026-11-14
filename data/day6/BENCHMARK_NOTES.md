# Benchmark tiếng Việt v1

Chốt trước khi chạy retrieval: 13/11/2026. Chưa chạy embedding, truy xuất hoặc dùng kết quả dev/test để sửa câu hỏi. Phạm vi là hai văn bản gốc trong corpus, không đánh giá pháp luật hiện hành ngoài corpus.

## Bộ câu hỏi

`questions.jsonl` là bộ duy nhất dùng chung cho A/B/C, mỗi dòng là một câu hỏi có đáp án và bằng chứng.

| Tập | ID | Luật 2018 | Nghị định 2023 | Câu filter |
|---|---|---:|---:|---|
| Dev | q01–q15 | 8 | 7 | q04, q10, q14 |
| Test | q16–q20 | 2 | 3 | q19 |

Có câu trực tiếp, diễn đạt lại và điều kiện/ngoại lệ. Tất cả đều có đáp án trong nguồn. Không áp đặt tỷ lệ cố định giữa các loại. Khi chạy, đọc trường `split`, không chia ngẫu nhiên lại.

Trường bắt buộc: `id`, `split`, `question`, `expected_answer`, `gold_source_id`, `gold_page`, `evidence_quote`, `filter` (null khi không có). Bổ sung `type`, `gold_article`, `acceptable_evidence`, `verification` để giải thích và kiểm chứng. `gold_page` là trang vật lý PDF từ 1.

## Chia tập và nguy cơ rò rỉ

Chia theo nhóm Điều trong từng văn bản; không có cùng cặp (tài liệu, Điều gold) giữa dev và test. Cả hai văn bản xuất hiện trong mỗi tập để test vẫn có phạm vi nguồn và filter; không chia theo toàn bộ tài liệu vì corpus chỉ có hai văn bản. Các Điều vẫn chia sẻ thuật ngữ, chủ đề và dẫn chiếu (đặc biệt về trẻ em, sự đồng ý). Corpus có thể chứa quy định tương đương ở Điều khác nên đây không phải phân chia độc lập hoàn toàn theo chủ đề. Người soạn AI đã đọc test để thiết kế/kiểm chứng, chưa dùng test để tinh chỉnh retrieval; học viên tự chấm có nguy cơ thiên lệch.

Tập test chỉ có 5 câu, một câu đúng/sai làm thay đổi 20 điểm phần trăm; chỉ minh họa trên corpus này. Không thay test sau khi thấy điểm. Nếu test bị dùng để chỉnh, phải công khai và tạo phiên bản holdout mới trước lần đánh giá độc lập tiếp theo.

## Filter và chống lộ gold

Các câu filter ghi rõ loại văn bản và năm ngay trong câu hỏi; đây là ngữ cảnh đầu vào giả định được cung cấp trước truy xuất. Chỉ dùng `doc_type` và `year`, không dùng source ID, số trang, Điều hoặc đáp án làm filter. Với chỉ hai tài liệu, loại và năm tương quan hoàn toàn, có thể xác định một tài liệu; cần ghi hạn chế này khi phân tích.

Đầu vào retriever chỉ gồm `question` và `filter` đã cung cấp. Không nối `expected_answer`, `gold_source_id`, `gold_page`, `gold_article`, `evidence_quote`, `acceptable_evidence` hay `verification` vào query. A/B bỏ qua filter; C áp dụng filter khi khác null, nếu null thì truy xuất không lọc.

## Kiểm chứng evidence

Trợ lý AI đã đọc ảnh render của toàn bộ 20 trang gold (10 trang mỗi PDF), đối chiếu ý nghĩa, điều kiện và ngoại lệ với đáp án. Bằng chứng lấy nguyên đoạn từ corpus hiện tại, bao gồm xuống dòng và lỗi OCR có sẵn. Ví dụ `đữ liệu`, `đông ý`, `suôt` là lỗi trích xuất; không sửa thầm bằng chứng thành text khác corpus. Phần kiểm chứng này không phải nhãn grounding/coherence cho kết quả retrieval.

`node scripts/validate_benchmark.cjs` kiểm tra schema, ID, số lượng dev/test/filter, metadata filter tồn tại và khớp gold, không trùng Điều gold giữa hai tập và evidence có trong đúng trang sau NFC + gộp khoảng trắng. Cũng kiểm tra SHA-256 để phát hiện corpus/benchmark bị thay sau khi chốt. Kiểm tra chuỗi không tự chứng minh đáp án đúng; vẫn cần đối chiếu PDF như trên. Người học nên rà soát độc lập trước chạy lần đầu.

`acceptable_evidence` ghi các trang có nguyên đoạn evidence tương ứng tìm thấy trong corpus (và phù hợp filter nếu có). Đây là danh sách ban đầu, không khẳng định mọi cách diễn đạt tương đương đã được liệt kê. Chấp nhận bất kỳ mục hợp lệ nào; nếu retrieval đưa bằng chứng tương đương khác, người chấm đối chiếu PDF và ghi nhận alternative trong trace/audit, không sửa câu hỏi hoặc bỏ bằng chứng đúng vì khác trang gold ban đầu. Không dùng đáp án ngắn trùng từ khóa để suy ra hit.

Một Hit@1/Hit@3 cần một chunk đúng nguồn/trang hợp lệ và chứa đủ bằng chứng cho toàn bộ câu hỏi. Với câu nhiều điều kiện, thiếu ngoại lệ hoặc một phần đáp án là chưa đủ; evidence bị chia qua nhiều chunk được ghi là lỗi theo định nghĩa chính. Grounding top-3 được chấm thủ công riêng. Chọn mẫu/tiêu chí giống nhau cho A/B/C.

## Cố định phiên bản và tiêu chí chọn

- Corpus SHA-256: `23c285e55542ffe99fca7bbd484deb155a6bd031d941b09dad6ed1a0dc740add`
- Questions SHA-256: `6576730194fbdf4da2846c3dbcd671fa96d6fccad5eb83fdd164eb1e80a064ce`

Chọn cấu hình theo dev: ưu tiên Evidence Hit@3, sau đó Hit@1; nếu bằng nhau ưu tiên thời gian ingest thấp hơn đo trong cùng điều kiện; nếu vẫn bằng nhau ưu tiên số chunk ít hơn, cuối cùng theo thứ tự A/B/C. Chốt các tham số và lựa chọn trước chạy test. Chạy đủ ba cấu hình trên cùng bộ test để báo so sánh, không dùng điểm test chọn lại cấu hình. Báo riêng thời gian, chi phí, coherence, metadata, grounding và đánh đổi trong phân tích.
