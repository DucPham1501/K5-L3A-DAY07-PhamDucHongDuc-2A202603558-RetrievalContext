# Benchmark LAB07 - day7-v1

Bộ câu hỏi phần cơ bản, chốt trước khi chạy retrieval/agent LAB07 ngày 14/11/2026. Corpus là 60 trang từ hai văn bản gốc trong `data/manifest.json`, không phải bộ pháp luật cập nhật hiện hành. Không có đánh giá agent hoặc điểm retrieval nào được tạo trong bước chuẩn bị này.

| Split | Có đáp án | Thiếu bằng chứng | Tổng |
|---|---:|---:|---:|
| Dev | 15 | 2 | 17 |
| Test mới | 5 | 2 | 7 |
| Tổng | 20 | 4 | 24 |

## File và cách dùng

- `dev.json`, `test.json`: nhãn dành cho evaluator, bao gồm đáp án, evidence, nguồn/trang, Điều, ID chunk hỗ trợ hoặc lý do thiếu bằng chứng.
- `inputs/dev.json`, `inputs/test.json`: chỉ có `id`, `question`, `filter` nếu có. Đây là đầu vào duy nhất cho runner agent/retrieval; không có gold, đáp án, cờ answerable hay lý do từ chối.
- `manifest.json`: checksum corpus, chunk và benchmark, số lượng và tiêu chí chọn cấu hình trên dev. Không tự cập nhật checksum sau khi tinh chỉnh bằng test.
- `../results/benchmark_validation.json`: kiểm tra schema, evidence, split, checksum và quét toàn corpus cho câu thiếu bằng chứng; không phải kết quả đo chất lượng hệ thống.

Chạy tại thư mục gốc LAB07:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/validate_benchmark.py
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v
```

Runner sử dụng:

```python
from src.benchmark import load_inputs

for case in load_inputs("dev"):
    # Chỉ gửi question và filter người dùng cung cấp tới agent/retriever.
    question = case["question"]
    filters = case.get("filter")
```

Loader chỉ đọc file input của split được chỉ định; không mở nhãn hoặc split còn lại. Nó từ chối trường ngoài whitelist và filter sai kiểu. Việc tách file hỗ trợ chống rò rỉ; runner vẫn phải tuân thủ không đọc/đưa nhãn evaluator vào model. Nội dung câu hỏi bản thân được viết như câu hỏi người dùng, không nối đáp án vào query.

`starter/baseline.py` gốc chỉ nhận các câu có đáp án. Runner thực tế phần 2 ở `src/retrieval_benchmark.py` chạy Dense/BM25/Hybrid trên toàn bộ input dev; lệnh `score` riêng chỉ dùng câu có `answerable: true` cho Hit@1/Hit@3/Context Evidence Rate. Không truyền nguyên file nhãn cho agent. Xem [cách chạy và kết quả retrieval dev](../docs/RETRIEVAL.md); đánh giá câu trả lời agent vẫn thuộc phần tiếp theo.

## Nguồn câu hỏi và phân chia

Dev giữ 15 câu có đáp án từ Day 6, đổi ID sang `d7-dev-01` đến `d7-dev-15`. Câu `d7-dev-04` được thu gọn trước mọi lượt retrieval LAB07: hỏi các hậu quả nêu tại điểm d khoản 1 Điều 8 thay cho câu hỏi có/không về hành vi nghiêm cấm. Evidence mới chỉ lấy đúng điểm d; gold cũ dài 717 ký tự vượt chunk 500 được giữ nguyên trong snapshot lịch sử, không sửa corpus/chunk. Mỗi evidence của bộ LAB07 nằm trọn trong ít nhất một chunk strategy C.

Năm câu có đáp án test LAB07 được soạn mới, ở các Điều không xuất hiện trong gold dev và không trùng bất kỳ cặp nguồn/Điều của năm câu test LAB06. Không dùng lại test cũ đã được đánh giá để chọn pipeline LAB07. Split không được chia lại ngẫu nhiên trong mỗi lần chạy. Hai tài liệu vẫn xuất hiện ở cả dev/test nên còn chia sẻ thuật ngữ và chủ đề; test 7 câu có quy mô nhỏ. Người soạn AI đã xem test để tạo/kiểm chứng gold, không phải đánh giá độc lập của con người và không được dùng kết quả test sau này để tinh chỉnh.

Nhóm có đáp án gồm câu trực tiếp, diễn đạt lại, trách nhiệm, điều kiện/ngoại lệ và thời hạn. Có 4 câu dev và 1 câu test có filter; các giá trị loại văn bản/năm được nêu ngay trong câu hỏi, không suy ra từ gold. Số trang là trang vật lý PDF từ 1.

## Evidence và kiểm chứng

Mỗi câu có đáp án có `gold` là danh sách `{source_id, page, evidence}`. Các phần tử là bằng chứng thay thế, không phải các mảnh bắt buộc ghép lại. Phiên bản này không có câu multi-hop. `gold_chunk_ids` chỉ hỗ trợ audit trên snapshot C; không gửi trường này cho retrieval, không giới hạn hit vào đúng ID đó khi dùng chunk/index khác.

Đáp án, điều kiện, ngoại lệ và đơn vị đã được trợ lý AI đối chiếu ảnh render của 19 trang PDF nguồn cho 20 câu; hai câu test dùng cùng một trang Luật. Evidence giữ nguyên OCR/cách xuống dòng của corpus, còn đáp án chuẩn dùng tiếng Việt được sửa dấu theo bản gốc. Ghi reviewer ở từng câu; chưa có xác nhận kiểm tra độc lập của học viên. Khớp chuỗi/checksum không tự chứng minh câu trả lời đúng, và việc tạo gold không thay cho chấm câu trả lời agent sau khi chạy.

Các câu thiếu bằng chứng ở gần chủ đề bảo vệ dữ liệu/an ninh mạng, kiểm tra bốn dạng thông tin không được corpus cung cấp: số liệu sự cố riêng, thông số thuật toán, thống kê năm sau ban hành và đoạn mã triển khai. Tên công ty trong tình huống kiểm thử là giả định; không xác nhận có sự cố thật. Mỗi câu ghi hành vi mong đợi, lý do, thuật ngữ kiểm tra và trang liên quan. Validator quét đủ 60 trang sau khi chuẩn hóa dấu/chữ/whitespace, kết hợp việc xem nội dung và phạm vi tài liệu. Không gán nhãn thiếu chỉ vì top-k không tìm được, không suy ra số liệu bằng 0 và không biến kiến thức ngoài tài liệu thành evidence.

## Cách chấm và chốt cấu hình

Theo `../BENCHMARK.md`:

- Hit@1 và Evidence Hit@3: trên câu có đáp án, chunk đúng nguồn/trang và chứa đủ evidence hợp lệ. Kiểm tra bằng chứng tương đương thủ công nếu cần; lưu lý do, không sửa gold âm thầm để tăng điểm.
- Context Evidence Rate: đủ evidence trong context cuối / số câu có đáp án; chấm thêm mức 0/1/2 và lý do.
- Grounded answer: 0 sai/thiếu evidence hoặc từ chối nhầm, 1 đúng một phần, 2 đúng và đủ. Không chỉ so khớp đáp án ngắn.
- Citation: ở trong context và thực sự hỗ trợ câu trả lời; đọc đối chiếu nguồn. Báo tỷ lệ câu có citation; `0/0` là không áp dụng.
- Abstention: câu thiếu evidence phải từ chối/nêu rõ không đủ bằng chứng, không thêm suy đoán; báo cả từ chối nhầm câu có đáp án.
- Báo `n/N`, tỷ lệ, lỗi, số lượt tool, thời gian và chi phí. Lỗi provider/store phải có trace riêng.

Tiêu chí chọn được ghi trước trong manifest: ưu tiên grounded answer dev, citation hợp lệ, abstention đúng, context/retrieval; phá hòa bằng thời gian, chi phí được đo và độ đơn giản. Không coi tỷ lệ citation `0/0` là hoàn hảo, không dùng chi phí chưa biết để thắng cấu hình khác. Thử ít nhất 3 phương pháp và 2 cấu hình cải thiện trên dev, phân tích ít nhất 2 lỗi, ghi cấu hình đã chốt trước khi chạy baseline/cấu hình chọn trên cùng test. Nếu dùng test để chỉnh thì tạo phiên bản test mới và công khai thay đổi.
