# Code

Code triển khai LAB07 nằm tại đây; [starter](../starter/README.md) giữ khung mẫu gốc của đề.

`day6/` chứa pipeline và dense adapter thật kế thừa Day 6. Xem [cách kết nối, kiểm tra và khôi phục](../docs/DAY6_HANDOFF.md).

Phần 2: `retrieval.py` triển khai BM25 và Hybrid RRF; `retrieval_benchmark.py` chạy dev rồi chấm kết quả riêng. Cấu hình ở `configs/retrieval.json`, kết quả thật ở `results/retrieval/dev-v1/`. Xem [thuật toán, lệnh chạy và phân tích](../docs/RETRIEVAL.md).

Phần 3: `agent_controller.py` nối model thật, `agent.py` điều phối tool/context/citation, `agent_benchmark.py` chạy dev/câu tự nhập/test, `agent_review.py` tổng hợp nhãn đã đối chiếu nguồn. Test yêu cầu selection và checksum đã chốt. Cấu hình baseline ở `configs/agent.json`; xem [hướng dẫn agent](../docs/AGENT.md).

Phần 4: `configs/agent-wide.json` và `configs/agent-focused.json` là hai cấu hình cải thiện; `scripts/select_agent.py` chốt lựa chọn trên dev trước test. Xem [kết quả thử nghiệm](../docs/EXPERIMENTS.md).

Phần nâng cao: `advanced/` chứa index toàn bộ 100 trang, hybrid retrieval trên embedding thật và mô tả vision, agent đọc ảnh gốc, benchmark input tách gold, chốt cấu hình và tổng hợp review. Xem [pipeline và kết quả](../docs/ADVANCED_IMPLEMENTATION.md). Phần này dùng index/benchmark/selection riêng; không đổi kết quả cơ bản.
