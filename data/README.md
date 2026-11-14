# Định dạng dữ liệu

Dữ liệu thật kế thừa Day 6 nằm tại `raw/`, `processed/`, `chunks/`, `manifest.json` và `chunks.json`. Xem [hướng dẫn kế thừa](../docs/DAY6_HANDOFF.md). `chunks.json` dùng schema Day 7 và giữ ID/nguồn của strategy C. Benchmark LAB07 đủ 24 câu nằm tại [benchmark/](../benchmark/README.md); `questions.jsonl` giữ 20 câu hỏi lịch sử Day 6 để đối chiếu nguồn gốc và kiểm tra không dùng lại test cũ. Agent chỉ dùng `benchmark/inputs/` qua `src.benchmark.load_inputs`.

Thư mục [example/](example/) chứa `example_chunks.json`, `example_questions.json` và `agent_cases_example.json`, chỉ minh họa định dạng, không đủ để nộp bài. `chunks.json` và benchmark LAB07 là JSON array UTF-8; corpus, chunk A/B/C và câu hỏi lịch sử dùng JSONL (mỗi dòng một đối tượng).

- **Chunk:** `id`, `text`, `source_id`, `source`, `page`, `metadata`. ID phải duy nhất; giữ phiên bản hoặc ngày nếu có.
- **Câu có đáp án:** `id`, `split` (`dev` hoặc `test`), `question`, `expected_answer`, `gold`: danh sách `{source_id, page, evidence}`. Với schema mẫu, mỗi evidence phải nằm trọn trong một chunk đúng nguồn và trang; các phần tử `gold` là evidence thay thế. Với câu multi-hop cần nhiều đoạn, bạn có thể mở rộng schema, ghi rõ nhóm evidence bắt buộc và cách chấm. Có thể thêm `filter` do người dùng cung cấp trước.
- **Câu thiếu evidence:** `id`, `split`, `question`, `answerable: false`, `expected_behavior: "search_and_abstain"`, `absence_reason`. Xem [example/agent_cases_example.json](example/agent_cases_example.json).

Không đưa `gold` hoặc nhãn đáp án vào model và retrieval tool. Ghi nguồn dữ liệu và quyền sử dụng. Cách chuyển một số định dạng Day 6: [starter/README.md](../starter/README.md).

Tài liệu phần nâng cao được giữ riêng tại [advance/](advance/README.md): PDF 100 trang, ảnh trang, caption vision, index và vector thật local. Benchmark nâng cao ở [benchmark/advanced/](../benchmark/advanced/README.md), không trộn với bộ câu hỏi cơ bản.
