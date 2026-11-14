# Phần 4 — Đánh giá và cải thiện

Đã hoàn thành hai thử nghiệm dev, lựa chọn trước test và đánh giá baseline/cấu hình chọn trên cùng 7 câu test. Bảng đầy đủ, phân tích lỗi trước/sau, token, chi phí và lệnh chạy nằm trong [báo cáo cá nhân](../report/individual/MSSV_HoTen.md).

| Cấu hình dev | Thay đổi so với baseline | Grounded trung bình | Citation hợp lệ | Context evidence |
|---|---|---|---|---|
| Baseline | Top-3, 20 candidate/nhánh, context 2000 ký tự | 1,8/2 | 16/17 (94,12%) | 14/15 (93,33%) |
| Wide | Top-15, 40 candidate/nhánh, context 10000 ký tự | 1,8/2 | 20/22 (90,91%) | 15/15 (100%) |
| Focused | Giữ retrieval/context, thêm kiểm tra ý định và phạm vi evidence trong prompt | 1,8/2 | 16/17 (94,12%) | 14/15 (93,33%) |

Wide phục hồi context cho lỗi định nghĩa `d7-dev-01`, nhưng đáp án chỉ tăng 0→1 và câu `d7-dev-06` giảm 2→1 vì mở rộng phạm vi chủ thể vượt nguồn. Lỗi khái quát consent `d7-dev-10` còn ở cả ba cấu hình. Focused không tăng số câu hoàn toàn đúng trên dev; kết quả không cải thiện được giữ nguyên.

[Kế hoạch](../configs/experiments.json) được ghi trước các lượt thử. Thứ tự tiêu chí đã công bố: grounded → citation → abstention → context → Hit@3 → Hit@1 lượt tìm đầu thực tế → thời gian → chi phí → độ đơn giản. Wide thua ở citation. Focused hòa baseline ở các tiêu chí trước rồi thắng Hit@1 thực tế 10/15 so với 9/15. Query gốc của cả hai vẫn có Hit@1 11/15; không coi khác biệt query do model tạo là cải thiện ranking của retriever cố định.

[Selection](../results/experiments/selection.json) chốt Focused trước lượt test đầu tiên, kèm checksum code/config/benchmark. Lệnh test từ chối thay đổi các thành phần đã khóa và chỉ cho phép baseline/cấu hình chọn. Không sử dụng test để chỉnh prompt hoặc tham số.

Trên test, cả hai đạt grounded mức 2 ở 5/5 câu, citation 5/5, context mức 2 ở 5/5 và từ chối đúng 2/2 câu thiếu evidence; không lỗi provider/store. Đây là nhãn AI đọc đối chiếu nguồn, không phải kiểm tra độc lập của con người. Không suy rộng từ bộ test nhỏ; cache và một lượt chạy không đủ kết luận tốc độ tổng quát. Baseline dev được tái sử dụng từ lượt hoàn chỉnh trước đó, giữ nguyên prompt/hành vi mặc định; checksum lịch sử được bảo toàn.

Artifacts: [Wide dev](../results/experiments/wide-dev/), [Focused dev](../results/experiments/focused-dev/), [baseline test](../results/experiments/baseline-test/), [Focused test](../results/experiments/focused-test/). Mỗi lượt có trace, nhãn có lý do, evaluation, config/checksum và usage. `summary.json` chỉ đếm cơ học; nhãn nội dung ở `reviews.json` và kết quả chấm ở `evaluation.json`.

Đối chứng query gốc, với gold chỉ được đọc sau khi tạo toàn bộ ranking/context: [dev](../results/experiments/original-query-reference.json), [test](../results/experiments/original-query-test-reference.json). Giữ cutoff Hit@3 ngay cả khi Wide xuất top-15; CER xét context đã đóng gói. Embedding thật được chia sẻ giữa các cấu hình, không tạo lại document embedding. Agent traces giữ query gốc và từng query thực tế sau model viết lại.
