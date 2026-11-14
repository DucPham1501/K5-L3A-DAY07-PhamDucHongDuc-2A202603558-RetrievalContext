# Day 7 — Agentic RAG

**Bài cá nhân · Python 3.11+ · tiếp nối Day 6**

> **Dữ liệu Day 6 đã chuyển vào LAB07:** xem [hướng dẫn kế thừa và kiểm tra](docs/DAY6_HANDOFF.md). Chạy `python scripts/day6_setup.py verify` để kiểm tra offline; code mới không phụ thuộc thư mục `LAB06/`.

> **Benchmark LAB07 đã chuẩn bị:** [24 câu dev/test và quy tắc sử dụng](benchmark/README.md). Chạy `python scripts/validate_benchmark.py` để kiểm tra dữ liệu, evidence và tách gold; chưa phải kết quả đánh giá agent.

> **Phần 2 đã chạy dev:** [Dense, BM25 và Hybrid RRF](docs/RETRIEVAL.md), có trace và bảng so sánh tại `results/retrieval/dev-v1/`.

> **Phần 3 đã chạy agent thật trên dev:** [Thiết kế, cách chạy và kết quả agent/context](docs/AGENT.md), trace và review tại `results/agent/dev-v2/`. [Phần 4 đã hoàn thành](docs/EXPERIMENTS.md): hai cấu hình dev, chốt Focused trước test, so sánh baseline/Focused.

> **Cấu trúc file đã được sắp xếp:** cấu hình kế thừa ở `configs/inherited.json`, câu hỏi lịch sử ở `data/questions.jsonl`, bằng chứng ingest ở `artifacts/ingestion.json`, dữ liệu mẫu ở `data/example/`. Xem [đường dẫn mới và cách đối chiếu kết quả lịch sử](docs/DAY6_HANDOFF.md#đường-dẫn-mới-và-kết-quả-lịch-sử); selection đã chốt được giữ nguyên.

> **Đã triển khai và đánh giá phần nâng cao:** [pipeline 100 trang, benchmark và kết quả](docs/ADVANCED_IMPLEMENTATION.md). Test đạt **23/30 (76,67%)** theo đối chiếu của AI, chưa đạt ngưỡng 90% để nhận bonus. Giữ đầy đủ các câu sai và kết quả gốc.

Dùng embedding và vector store từ Day 6 để xây một agent biết tìm bằng chứng, trả lời có nguồn và nhận biết khi không đủ thông tin. Bạn tự chọn kiến trúc, số tool và cách tổ chức retrieval.

> **Tùy chọn:** [Gợi ý dùng AI để lập trình](AGENT_SETUP.md) giúp bạn làm lab; phần này không bắt buộc và không tính điểm.

## Bài cần làm

![Agent tìm tài liệu trong kho Day 6 và trả lời có nguồn](assets/retrieval-pipeline.svg)

1. Kết nối dữ liệu, embedding và vector store Day 6.
2. Xây agent dùng model thật và ít nhất một khả năng truy xuất dữ liệu. Agent có thể dùng nhiều tool và nhiều lượt gọi.
3. Thử **ít nhất 3 phương pháp retrieval khác nhau**, trong đó có dense retrieval dùng vector store Day 6. Tự chọn các phương pháp còn lại; xem [gợi ý](GUIDE.md#2-thử-các-phương-pháp-retrieval).
4. Thử nhiều cấu hình, benchmark, phân tích lỗi và chọn cấu hình tốt trên **dev**; sau đó đánh giá trên **test**.

Benchmark tối thiểu có **24 câu**: dev gồm 15 câu có đáp án và 2 câu thiếu bằng chứng; test gồm 5 câu có đáp án và 2 câu thiếu bằng chứng. Xem [benchmark](BENCHMARK.md) và [rubric](RUBRIC.md).

## Thử thách nâng cao · +15 điểm

Index một tài liệu thực tế từ **100 trang** có bảng, ảnh và biểu đồ; xây agent truy xuất và trả lời các câu hỏi về nội dung đó. Hoàn thành [thử thách nâng cao](ADVANCED.md) và đạt **ít nhất 90% benchmark test** để nhận 15 điểm bonus. Phần cơ bản tối đa 85 điểm; toàn bài tối đa 100 điểm.

## Bắt đầu

1. Đọc [hướng dẫn](GUIDE.md), [rubric](RUBRIC.md) và [quy tắc](RULES.md).
2. Tạo repo cá nhân theo [cách nộp bài](SUBMISSION.md), chuẩn bị đầu ra Day 6 và model hỗ trợ tool calling.
3. Dùng hoặc thay thế [starter](starter/README.md); bạn cần kết nối model và vector store thật.
4. Chạy `python -m unittest discover -s tests -v`. Test mock chỉ kiểm tra code, không phải benchmark agent thật.

![Các bước thử nghiệm trên dev và đánh giá trên test](assets/experiment-loop.svg)

Nộp code, cách chạy, cấu hình, benchmark, trace và [báo cáo cá nhân](report/individual/2A202603558_PhamDucHongDuc.md). [MSSV_HoTen.md](report/individual/MSSV_HoTen.md) và [REPORT_TEMPLATE.md](REPORT_TEMPLATE.md) là mẫu. Thời gian ở [checkpoints](CHECKPOINTS.md) là gợi ý, có thể điều chỉnh theo lớp và phạm vi thử nghiệm.
