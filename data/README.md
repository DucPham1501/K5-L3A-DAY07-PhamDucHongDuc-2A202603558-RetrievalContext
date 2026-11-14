# Định dạng dữ liệu

Dữ liệu thật kế thừa Day 6 nằm tại `raw/`, `processed/`, `chunks/`, `manifest.json` và `chunks.json`. Xem [hướng dẫn kế thừa](../docs/DAY6_HANDOFF.md). `chunks.json` dùng schema Day 7 và giữ ID/nguồn của strategy C. Benchmark LAB07 đủ 24 câu nằm tại [benchmark/](../benchmark/README.md); `day6/` chỉ lưu đầu vào lịch sử. Agent chỉ dùng `benchmark/inputs/` qua `src.benchmark.load_inputs`.

Các file `example_*.json` chỉ minh họa định dạng, không đủ để nộp bài. Dữ liệu thật là JSON array UTF-8; nếu dùng định dạng khác, ghi cách chuyển trong README.

- **Chunk:** `id`, `text`, `source_id`, `source`, `page`, `metadata`. ID phải duy nhất; giữ phiên bản hoặc ngày nếu có.
- **Câu có đáp án:** `id`, `split` (`dev` hoặc `test`), `question`, `expected_answer`, `gold`: danh sách `{source_id, page, evidence}`. Với schema mẫu, mỗi evidence phải nằm trọn trong một chunk đúng nguồn và trang; các phần tử `gold` là evidence thay thế. Với câu multi-hop cần nhiều đoạn, bạn có thể mở rộng schema, ghi rõ nhóm evidence bắt buộc và cách chấm. Có thể thêm `filter` do người dùng cung cấp trước.
- **Câu thiếu evidence:** `id`, `split`, `question`, `answerable: false`, `expected_behavior: "search_and_abstain"`, `absence_reason`. Xem `agent_cases_example.json`.

Không đưa `gold` hoặc nhãn đáp án vào model và retrieval tool. Ghi nguồn dữ liệu và quyền sử dụng. Cách chuyển một số định dạng Day 6: [starter/README.md](../starter/README.md).
