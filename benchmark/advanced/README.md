# Benchmark phần nâng cao — advanced-v1

Benchmark riêng cho toàn bộ 100 trang của GPT-4 Technical Report v6. Được tạo và chốt trước lượt agent dev đầu tiên, sau khi index toàn tài liệu và tạo embedding thật. Không dùng câu hỏi để chọn trang cần index.

| Nhóm chính | Dev | Test |
|---|---:|---:|
| Bảng | 4 | 6 |
| Ảnh/sơ đồ | 1 | 5 |
| Biểu đồ | 3 | 5 |
| Multi-hop | 4 | 4 |
| Text | 3 | 4 |
| Thiếu bằng chứng | 3 | 6 |
| Tổng | 18 | 30 |

Mỗi câu có đúng một nhóm chính. Câu hỏi dùng tiếng Việt, tài liệu tiếng Anh. Các mục đánh giá ảnh/sơ đồ là hình mang nội dung, không phải ảnh trang trí; ảnh bảng hay biểu đồ không tự được tính thành nhóm ảnh. Multi-hop yêu cầu bằng chứng từ ít nhất hai trang và citation cho tất cả phần kết hợp. Dev/test khác đích thông tin, không chỉ đổi cách diễn đạt cùng đáp án; có thể dùng chung trang nên vẫn có liên hệ chủ đề. Đây không phải holdout độc lập về toàn bộ trang hoặc tài liệu.

## Tách nhãn và input

`dev.json`, `test.json` dành cho evaluator, có expected answer, nhóm, source/page, vùng chuẩn hóa, mô tả evidence, checksum ảnh đã đọc và lý do thiếu bằng chứng. Bbox theo gốc trên trái, tọa độ 0..1. Mọi phần tử gold là điều kiện evidence cần có; không dùng quy tắc “một đoạn bất kỳ là đủ” cho multi-hop. Trợ lý AI đã đọc ảnh PDF gốc và đối chiếu các vùng này; không tuyên bố có xác nhận độc lập của con người.

`inputs/dev.json`, `inputs/test.json` chỉ gồm `id` và `question`. Runtime loader từ chối trường thừa, không mở file nhãn. Agent không nhận group, gold page/bbox, expected answer, answerable hoặc fact key. `open_pages` chỉ dùng số trang do model suy từ câu hỏi/kết quả tìm kiếm, không dùng vùng gold.

Các câu thiếu evidence được xác định bằng tìm trên toàn bộ text/index và kiểm tra phạm vi/vùng hình liên quan, không dựa trên việc top-k không có kết quả. Những con số kiến trúc/chi phí không công bố, ngôn ngữ không có trong biểu đồ và danh tính không ghi trong ảnh phải được từ chối; không điền bằng kiến thức ngoài báo cáo.

## Chốt và chấm

`manifest.json` đóng băng PDF, index, vector, metadata, toàn bộ 100 ảnh trang và cả nhãn/input hai split. `configs/advanced/experiments.json` công bố trước tiêu chí: strict pass rate dev, ít lỗi hơn, chi phí API đo được thấp hơn, thời gian trung vị thấp hơn. Chỉ chọn cấu hình bằng dev; `results/advanced/selection.json` được tạo một lần trước test và khóa config/code/benchmark.

Theo [ADVANCED.md](../../ADVANCED.md), chấm mỗi câu đạt/không đạt. Câu có đáp án phải đủ nội dung, số/đơn vị/điều kiện và citation hỗ trợ đúng trang/vùng. Câu thiếu evidence phải từ chối và không suy đoán. Lỗi, timeout, sai hoặc thiếu điều kiện đều không đạt, giữ mẫu số 30. Cần tối thiểu 27/30, không làm tròn qua ngưỡng và không chọn bỏ câu khó.

`reviews.json` lưu nhãn có lý do từng câu/citation, người chấm và xác nhận đối chiếu nguồn; `src.advanced.review` chỉ tổng hợp nhãn, không tự suy chất lượng từ ID/citation. AI review phải được công khai, không xem là giảng viên đã chấm đạt bonus.

```powershell
.venv/Scripts/python.exe -X utf8 -m src.advanced.benchmark
.venv/Scripts/python.exe -X utf8 -m src.advanced.runner dev --config configs/advanced/base.json --output results/advanced/base-dev-v2
.venv/Scripts/python.exe -X utf8 -m src.advanced.runner dev --config configs/advanced/wide.json --output results/advanced/wide-dev
```

Runner bảo toàn output cũ. Lượt `results/advanced/base-dev/` là tích hợp lỗi metadata ảnh, được giữ nguyên để kiểm tra chi phí/lỗi và không dùng làm baseline đã hoạt động.

## Kết quả đã hoàn thành

Base/Wide đạt 15/18 dev, Verify 14/18; chọn Base theo tiêu chí công bố trước. Test sau khi chốt đạt **23/30 (76,67%)**, không lỗi hạ tầng; chưa đạt ngưỡng bonus. Nhãn có lý do và kết quả từng nhóm tại [evaluation](../../results/advanced/selected-test/evaluation.json), [reviews](../../results/advanced/selected-test/reviews.json), [báo cáo pipeline](../../docs/ADVANCED_IMPLEMENTATION.md). Đánh giá dựa trên nội dung: `u04` nêu rõ không công bố danh sách nên là semantic abstention dù raw action là submit_answer; [bản ghi sửa evaluator](../../results/advanced/evaluation-correction.json) công khai thay đổi tổng hợp này, không sửa action/gold hoặc pipeline đã chạy.
