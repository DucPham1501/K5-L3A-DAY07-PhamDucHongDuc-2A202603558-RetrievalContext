# Phần nâng cao — pipeline đa phương thức

Đọc yêu cầu tại [ADVANCED.md](../ADVANCED.md). Phần này dùng corpus, benchmark, index và kết quả riêng; không thay gold, metric hoặc selection của bài cơ bản.

## Tài liệu và coverage

[GPT-4 Technical Report v6](https://arxiv.org/abs/2303.08774v6), ngày 04/03/2024, có đúng 100 trang vật lý. Học viên cung cấp PDF tại `data/advance/2303.08774v6.pdf`; SHA-256 `c33a66dadca2388d7b172d6293b00dc32b71110c6f38fafe0d41112e61be7774`. [Manifest](../data/advance/manifest.json) ghi nguồn, phiên bản, quyền, coverage và usage.

Đã render và index **100/100 trang**, không loại trang theo benchmark. Pypdf lấy text layout; model vision đọc từng ảnh toàn trang và mô tả text, bảng, trục/chú giải/số liệu, hình và quan hệ nhìn thấy. Trang ít text/ảnh-only, tài liệu tham khảo và bìa phụ lục vẫn có bản ghi. Có cảnh báo font/rotated text từ công cụ PDF, nên text layout không được xem là bản sao chính xác hoàn toàn; ảnh nguồn được gửi cho model trả lời để đối chiếu. Đã đọc trực quan các trang gold và các trang khác thực tế được viện dẫn khi chấm.

Vùng vision là bbox ước lượng theo tọa độ chuẩn hóa trên trái; không tuyên bố segmentation chính xác. Mỗi citation của agent có trang vật lý, tên vùng/bảng/hình/section và bbox toàn trang `[0,0,1,1]`. Tên vùng giúp định vị trong trang; gold có bbox hẹp hơn do evaluator kiểm tra riêng. Không gửi bbox gold vào agent. Hình/sơ đồ trong benchmark mang nội dung, không tính ảnh trang trí.

PDF, toàn văn, caption, ảnh trang, vector và trace có toàn văn giữ local theo [hướng dẫn dữ liệu/quyền](../data/advance/README.md). Code, nguồn tải, checksum, nhãn và số liệu tổng hợp phục vụ tái tạo; cần giao cache/trace qua kênh được phép khi người chấm cần bản gốc của lượt chạy.

## Index và agent

- `src/advanced/prepare.py`: caption vision toàn tài liệu, cache theo checksum PDF/image/model/prompt, xuất `index.json` và manifest; không đọc benchmark.
- `src/advanced/retrieval.py`: 100 embedding thật `text-embedding-3-small`, 1536 chiều, vector store JSON persistent local riêng, exact cosine kết hợp BM25 bằng RRF 60. Đây là text embedding trên text + mô tả vision, không gọi nó là native image embedding. Ảnh gốc được dùng ở bước trả lời.
- Tiền xử lý query/document giống nhau: các delimiter ChatML được in trong báo cáo chuyển sang text thông thường, rồi NFC + gộp whitespace. Không thay text evidence gốc. Không cần PostgreSQL cho phần nâng cao.
- `src/advanced/agent.py`: model `gpt-4.1-mini-2025-04-14`, native function calling, temperature 0. Model tự chọn `search`, `open_pages`, `submit_answer`, `abstain`. Search trước trả lời; giữ filter/nhãn evaluator ngoài runtime. Tài liệu là dữ liệu không đáng tin, không phải system instruction.
- Mỗi lượt xây lại một snapshot context, ưu tiên trang vừa tìm, dedup ID, giữ nguyên nội dung trang, giới hạn ký tự block text nguồn và số ảnh. JSON metadata vùng/ảnh, schema và system prompt nằm ngoài budget ký tự này; mô tả vùng đang lặp thông tin đã có trong text nên có overhead. Tổng prompt/image tokens được đo bằng usage API, không coi budget ký tự là tổng token model. Citation chỉ được dùng trang trong context cuối. Bước chấm riêng xác nhận nội dung/vùng thực sự hỗ trợ; ID đúng chưa đủ.
- `src/advanced/runner.py`: input chỉ ID/câu hỏi. Test kiểm tra selection và checksum code/config/benchmark trước khi load input hoặc gọi API. Trace lưu query, ranking/nhánh, tool args, context, ảnh được gửi, trả lời/citation, usage, lỗi và thời gian. Base64 không lặp trong trace; ảnh được định danh bằng đường dẫn/checksum đã đóng băng.

## Benchmark và thử dev

[Benchmark riêng](../benchmark/advanced/README.md) có 18 dev (15 có đáp án, 3 thiếu evidence), 30 test (24 có đáp án, 6 thiếu evidence). Nhóm test: 6 bảng, 5 ảnh/sơ đồ, 5 biểu đồ, 4 multi-hop, 4 text. Mọi gold được đối chiếu ảnh gốc trước chạy agent; nhãn semantic sau chạy do AI đọc nguồn, không phải xác nhận độc lập của con người.

| Cấu hình dev | Candidate/nhánh, top-k | Context / số ảnh / lượt tìm tối đa | Đạt | Model calls | Trung vị ms/câu | Tổng API USD ước tính |
|---|---|---|---|---:|---:|---:|
| Base | 15, 4 | 24000 ký tự / 4 ảnh / 3 lượt | 15/18 (83,33%) | 37 | 4198,84 | 0,09966782 |
| Wide | 25, 6 | 48000 ký tự / 6 ảnh / 4 lượt | 15/18 (83,33%) | 37 | 4700,69 | 0,15631726 |
| Verify | Như Base | Như Base; thêm prompt kiểm tra từng phần/điều kiện | 14/18 (77,78%) | 40 | 4431,86 | 0,11978600 |

Các lỗi dev đã đọc trước/sau:

1. `adv-dev-13`: Base lấy Table 10 contamination thay Table 8 base/RLHF. Wide đưa đúng Table 8 vào context và có số đúng trong thân bài, nhưng tóm tắt lại đổi thành hàng Average; vẫn không đạt. Verify tiếp tục nhầm điều kiện. Context có đúng bảng chưa bảo đảm câu trả lời đúng.
2. `adv-dev-11`: hỏi khuyến nghị đánh giá nguy cơ mới nổi, cần hướng thiết kế vừa nhắm năng lực nguy hiểm vừa mở cho nguy cơ chưa biết ở trang 69. Các cấu hình tìm/viện dẫn các đoạn mitigations hoặc ví dụ lạm dụng, không chứng minh được khuyến nghị cụ thể.
3. `adv-dev-14`: yêu cầu ghép Limitations của Technical Report và Abstract System Card. Agent lẫn section/trang hoặc chỉ trả lời chung từ System Card, nên chấm không đạt thay vì chấp nhận câu trả lời nghe hợp lý.
4. Verify làm câu `adv-dev-09` trượt thêm vì lấy đoạn mitigations/Privacy thay đúng Abstract. Giữ kết quả không cải thiện, không sửa gold/đáp án để tăng điểm.

Theo tiêu chí ghi trước, ưu tiên strict pass rate, ít lỗi, chi phí API, rồi thời gian. [Selection](../results/advanced/selection.json) chọn **Base**, khóa trước test: cùng điểm Wide và ít chi phí hơn; Verify có điểm thấp hơn. Base/Wide được tái sử dụng sau khi bổ sung prompt opt-in: prompt mặc định/hành vi retrieval giữ nguyên, mọi system prompt thực tế đã đối chiếu, checksum lịch sử không ghi lại. Selection ghi rõ hai file code thay đổi do bổ sung dispatch prompt và kiểm tra lựa chọn; các phần runtime/retriever/index khác phải khớp.

## Chi phí chuẩn bị và lỗi tích hợp

100 caption vision có chi phí model ghi nhận ước tính **0,16331040 USD**; document embedding **0,00158794 USD**. Các request có lỗi kết nối hoặc bị ngắt không có usage có thể tạo chi phí chưa xác định; không coi tổng này là hóa đơn hoặc toàn bộ chi phí tuyệt đối. Embedding/model cached input được tính theo usage, không cộng lại phần cache thành phí API mới.

Lượt `results/advanced/base-dev/` có 18 lỗi KeyError do schema RRF cơ bản làm mất metadata ảnh/vùng. Giữ trace/usage và đánh dấu integration failed; model 0,00344640 USD + embedding 0,00000470 USD. Sau sửa đã thêm regression test giữ ảnh khớp page ID rồi chạy Base đầy đủ thành `base-dev-v2`. Không coi lượt tích hợp lỗi là chất lượng agent đã hoạt động hoặc loại lỗi khỏi một lượt test.

Đơn giá model snapshot ghi trong config: input 0,40; cached input 0,10; output 1,60 USD/triệu token, theo [OpenAI Docs model](https://developers.openai.com/api/docs/models/gpt-4.1-mini). Embedding dùng mức ước tính cấu hình 0,02 USD/triệu token. Chưa gồm hạ tầng, thuế hoặc retry không có usage. Một lượt nhỏ và cache khác nhau không đủ kết luận tốc độ tổng quát.

## Lệnh chạy và đối chiếu

```powershell
.venv/Scripts/python.exe -X utf8 -m src.advanced.benchmark
.venv/Scripts/python.exe -X utf8 -m src.advanced.runner dev --config configs/advanced/base.json --output results/advanced/base-dev-v2
.venv/Scripts/python.exe -X utf8 -m src.advanced.runner dev --config configs/advanced/wide.json --output results/advanced/wide-dev
.venv/Scripts/python.exe -X utf8 -m src.advanced.runner dev --config configs/advanced/verify.json --output results/advanced/verify-dev
# Sau khi đọc nguồn và lưu reviews.json của mỗi lượt:
.venv/Scripts/python.exe -X utf8 -m src.advanced.review results/advanced/base-dev-v2
.venv/Scripts/python.exe -X utf8 -m src.advanced.review results/advanced/wide-dev
.venv/Scripts/python.exe -X utf8 -m src.advanced.review results/advanced/verify-dev
# Chốt một lần trước test:
.venv/Scripts/python.exe -X utf8 -m src.advanced.select
.venv/Scripts/python.exe -X utf8 -m src.advanced.runner test --config configs/advanced/base.json --output results/advanced/selected-test
.venv/Scripts/python.exe -X utf8 -m src.advanced.review results/advanced/selected-test
```

Các output đã có không được ghi đè; không chạy lại selection sau khi xem test. Chỉ đọc artifacts không cần gọi API. Định nghĩa ngưỡng và cách chấm vẫn theo đề bài, không suy điểm bonus từ mock tests hoặc chỉ số dev.

## Kết quả test đã chấm

Lượt [selected-test](../results/advanced/selected-test/) chạy sau khi chốt Base, đủ 30 câu, không lỗi hạ tầng. AI đã đọc từng câu trả lời/citation và đối chiếu PDF gốc; [reviews.json](../results/advanced/selected-test/reviews.json) giữ lý do từng câu/citation, [evaluation.json](../results/advanced/selected-test/evaluation.json) tổng hợp.

| Nhóm test | Đạt / tổng | Tỷ lệ | Lỗi |
|---|---:|---:|---|
| Bảng | 5/6 | 83,33% | `02`: lấy Table 11 thay Table 2, thiếu 10-shot |
| Ảnh/sơ đồ | 4/5 | 80% | `08`: thêm nhiệt độ thermostat T0, ảnh ghi Tb |
| Biểu đồ | 4/5 | 80% | `12`: bỏ dấu trừ của trục -Mean Log Pass Rate |
| Multi-hop | 2/4 | 50% | `18`: nhầm lý do thiếu nonholdout; `19`: không nêu BIG-bench bị loại |
| Text | 3/4 | 75% | `22`: thiếu mốc 09/2021 và ngoại lệ dữ liệu mới hơn |
| Thiếu bằng chứng | 5/6 | 83,33% | `u05`: gán 71,8% của Thai cho Vietnamese không có trong hình |
| **Toàn bộ** | **23/30** | **76,67%** | **Chưa đạt ngưỡng 27/30 cho 15 điểm bonus** |

Raw status là 26 answered, 4 abstain, 0 error; không diễn giải thành 26 câu đúng. `u04` dùng submit_answer nhưng nói rõ báo cáo không công bố danh sách dữ liệu, không bịa tên; được tính là từ chối theo nghĩa nội dung. Đã sửa điều kiện tổng hợp đánh giá để đúng quy tắc “từ chối hoặc nêu rõ không đủ bằng chứng”, thay vì bắt buộc tên tool abstain; [bản ghi sửa evaluator](../results/advanced/evaluation-correction.json) giữ hash trước/sau. Chỉ `src/advanced/review.py` thay đổi sau test; model, retrieval, input, gold, raw trace và selection không đổi. Guard checksum giữ nguyên, không ghi lại selection để chạy lại test.

Test có 62 model calls, model input 406550 / output 6877 token, cached input 0; embedding 421 token, 31 request. Model 0,17362320 USD, embedding 0,00000842 USD, tổng **0,17363162 USD**. Trung vị 4576,17 ms/câu. Tổng chi phí ghi nhận của chuẩn bị, lượt tích hợp lỗi, ba dev và test **0,71775214 USD**, không phải hóa đơn đầy đủ khi retry/lỗi không có usage. Không loại 7 câu sai khỏi mẫu số và không thay test sau khi xem điểm. Các lỗi cho thấy retrieval/citation đúng hình thức chưa đủ; cần đọc đúng điều kiện và toàn bộ nguồn của câu nhiều phần.
