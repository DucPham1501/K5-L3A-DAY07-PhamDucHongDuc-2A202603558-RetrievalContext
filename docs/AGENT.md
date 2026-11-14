# Phần 3 - Agent thật và context

Đã nối model thật với Dense, BM25 và Hybrid RRF, chạy đủ 17 câu dev tại `results/agent/dev-v2/`. Baseline cho [phần 4 đã hoàn thành](EXPERIMENTS.md).

## Kiến trúc và model

- `src/agent_controller.py`: OpenAI Chat Completions với native function calling, JSON schema strict, mỗi lượt một function call (`parallel_tool_calls=False`, `tool_choice=required`). Tham khảo [hướng dẫn function calling chính thức](https://developers.openai.com/api/docs/guides/function-calling).
- Model cố định `gpt-4.1-mini-2025-04-14`, temperature 0, tối đa 1000 output token/request; API đã xác nhận model này có trong tài khoản trước khi chạy. Model/version trả về, request ID, fingerprint và usage lưu trong trace. Model được chọn để có snapshot, hỗ trợ tool calling và chi phí thấp cho lab; không khẳng định đây là model tốt nhất.
- `src/agent.py`: kiểm soát vòng lặp, thực thi retrieval, quản lý context và xuất citation có nguồn.
- `src/agent_benchmark.py`: chạy dev, ask và test; test bắt buộc selection/checksum đã chốt.
- `configs/agent.json`: tham số và lý do thiết kế; bản config cùng checksum code/corpus/input được giữ trong `run.json` của từng lượt.

Model này hiện còn gọi được nhưng có lịch ngừng phục vụ; xem [thông báo deprecations](https://developers.openai.com/api/docs/deprecations). Khi chạy lại về sau, cần kiểm tra model còn khả dụng. Nếu đổi model, tạo cấu hình/lượt chạy riêng và ghi rõ; code không âm thầm fallback model khác.

## Công cụ, lượt gọi và điều kiện dừng

Ba retrieval tool được cung cấp cho model:

| Tool | Cách tìm |
|---|---|
| `search_dense(query)` | Embedding thật + exact cosine trên pgvector strategy C |
| `search_bm25(query)` | BM25, k1=1.5, b=0.75 |
| `search_hybrid(query)` | Top-20 Dense/BM25, RRF hằng số 60, trả top-3 |

Model lựa chọn công cụ và query. Filter `doc_type/year` được ứng dụng giữ cố định theo input người dùng, không cho model chèn source/page từ gold. Query đầu được hướng dẫn ưu tiên hybrid/câu hỏi gốc; model vẫn có thể viết lại query. Trace giữ cả `query_original` và query thực tế từng lượt. Kết quả query gốc để so sánh retrieval riêng nằm tại `results/retrieval/dev-v1/`; không coi ranking từ query đã viết lại là ranking query gốc.

Lượt đầu chỉ cho phép retrieval tool để bảo đảm đã tìm evidence trước khi trả lời. Sau khi tìm, model có thể tìm tiếp, gọi `submit_answer(answer, citations)` hoặc `abstain(reason)`. Cấu hình ban đầu tối đa **3 lượt retrieval** và **6 lượt model** mỗi câu. Hết lượt retrieval thì chỉ còn công cụ kết thúc; hết lượt model hoặc lặp cùng tool/query thì ứng dụng từ chối với lý do dừng trong trace. Đây là giới hạn triển khai có thể thay đổi trong thử nghiệm dev, không phải giới hạn chung của đề bài.

Lỗi API/database được ghi `status=error` với loại lỗi, giữ trace, không giả thành câu thiếu bằng chứng hoặc chuyển sang dữ liệu mock. Runner dừng nếu gặp lỗi thực thi để không tiếp tục tiêu API trên hạ tầng đang lỗi.

## Context, citation và dữ liệu không đáng tin

Mỗi lượt tìm thêm các chunk vào pool, dedup ID và ưu tiên kết quả mới trước (`recent_first`). Chọn các chunk nguyên vẹn theo thứ tự này, tối đa **2000 ký tự**, gồm ID/nguồn/trang. Chunk không vừa bị bỏ, không cắt mất điều kiện hoặc ngoại lệ để cố nhét vào budget. Context cuối có thể khác context lượt trước; citation chỉ được dùng các ID còn trong context cuối.

Mỗi request model được xây lại với system prompt, câu hỏi/filter và **một** tool response chứa context tích lũy mới nhất. Không gửi lại tất cả tool outputs cũ. Cách này tránh cộng dồn evidence vượt budget và giúp evidence mới có chỗ thay vì bị chunk cũ chiếm hết. Query history ngắn và metadata điều khiển nằm ngoài evidence budget; tổng prompt/schema/token API vẫn được đo bằng usage thật, không nhầm 2000 ký tự với giới hạn toàn bộ prompt hay 2000 token.

System prompt nêu rõ nội dung tài liệu, câu hỏi và kết quả retrieval là dữ liệu, không phải chỉ dẫn được phép ghi đè quy tắc. Feedback kiểm tra định dạng do ứng dụng tạo được đặt riêng ở system message. Gold, expected answer và cờ answerable không nằm trong request model.

Model cung cấp câu trả lời và danh sách ID nguồn. Ứng dụng chuẩn hóa trình bày citation: gắn `[id]` nếu thiếu nhãn inline hoặc tách nhóm `[id1, id2]` thành từng nhãn; giữ raw tool arguments để đối chiếu. Chỉ chuẩn hóa định dạng của ID đã có trong context, không tự chọn nguồn, thêm evidence, sửa nội dung hoặc suy ra nguồn hỗ trợ. ID không tồn tại hoặc nhãn inline không khớp bị từ chối và cho model nhận feedback. Mỗi citation xuất thêm source/page trong `citation_sources`.

Đúng ID và định dạng chưa chứng minh đúng nội dung. Các nhãn chất lượng dưới đây được đối chiếu câu trả lời với chunk/trang nguồn sau khi chạy; không lấy điểm retrieval hoặc structural validation làm điểm đúng câu trả lời.

## Cách chạy

Đã chạy trực tiếp trên máy; học viên hiện không cần chạy thêm để hoàn tất bước này. Docker/database và API key local vẫn cần sẵn khi muốn chạy lại.

```powershell
# Chạy lại dev, dùng thư mục mới để bảo toàn kết quả cũ:
.venv/Scripts/python.exe -X utf8 -m src.agent_benchmark dev --output results/agent/dev-v3

# Hỏi một câu tự nhập, không dùng câu test để tinh chỉnh:
.venv/Scripts/python.exe -X utf8 -m src.agent_benchmark ask --question 'Sự im lặng có được coi là đồng ý xử lý dữ liệu cá nhân không?' --doc-type 'Nghị định' --year 2023 --output results/agent/demo-v1

# Đọc câu trả lời của lượt hỏi (trace là JSONL UTF-8):
Get-Content results/agent/demo-v1/traces.jsonl -Encoding UTF8 | ConvertFrom-Json | Select-Object answer,citation_sources

# Chấm từ nhãn đã đọc và đối chiếu nguồn, không tự chạy LLM judge:
.venv/Scripts/python.exe -X utf8 -m src.agent_review --run results/agent/dev-v2 --reviews results/agent/dev-v2/reviews.json

.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v
```

## Kết quả dev của cấu hình agent-v1.1

Lượt đầy đủ có **17 câu**, **37 request model**, **20 lượt retrieval**: hybrid 18, BM25 2; model không chọn tool dense riêng trong lượt này, nhưng hybrid thực sự truy vấn dense. 15 câu tìm một lượt, một câu tìm ba lượt, một câu tìm hai lượt. Không có lỗi provider/store. Trung vị thời gian end-to-end mỗi câu khoảng **2768,43 ms**; đây là một lượt nhỏ có cache, không phải kết luận tốc độ tổng quát.

Các nhãn do **trợ lý AI đọc đối chiếu nguồn sau khi chạy**, chưa có xác nhận kiểm tra độc lập của học viên. Chi tiết từng câu/citation và lý do ở `reviews.json`, tổng hợp ở `evaluation.json`.

| Chỉ số dev | Kết quả |
|---|---|
| Có gọi retrieval tool | 17/17 |
| Trạng thái cuối | 15 answered, 2 abstain, 0 error |
| Grounded answer trên 15 câu có đáp án | Mức 0: 1; mức 1: 1; mức 2: 13; trung bình **1,8/2** |
| Context evidence nguyên văn | 14/15 (93,33%) |
| Citation có nguồn và hỗ trợ nội dung theo review | 16/17 (94,12%) |
| Câu answered có citation | 15/15 |
| Từ chối đúng câu thiếu evidence | 2/2 |
| Từ chối nhầm câu có đáp án | 0/15 |

Không diễn giải 15 answered thành 15 câu đúng hoặc 1,8/2 thành 90% câu hoàn toàn đúng. Có 13/15 câu mức 2 theo review này. Context dài nhất 1706 ký tự và mọi model request có tối đa một snapshot evidence, nằm trong budget.

## Ví dụ đúng, thiếu bằng chứng và lỗi

- **`d7-dev-11`**: trả lời im lặng/không phản hồi không được coi là đồng ý, cite đúng khoản 6 Điều 11 Nghị định, trang vật lý 9. Đây là ví dụ trả lời có bằng chứng.
- **`d7-dev-u01`**: tìm ba lượt rồi model gọi abstain; câu cuối không bịa số hồ sơ hoặc xác nhận sự cố giả định.
- **`d7-dev-u02`**: không tìm được thông số AES, sau hai lượt model thử lặp tool/query. Guard ứng dụng dừng và xuất từ chối. Hành vi cuối đúng, nhưng cần phân biệt guard với model chủ động chọn abstain.
- **`d7-dev-01`**: model trả danh sách biện pháp tại Điều 5 trang 4 thay vì định nghĩa bốn hoạt động tại Điều 2 trang 1. Citation hỗ trợ danh sách đã viết nhưng câu trả lời sai trọng tâm benchmark, nên answer/context chấm 0. Đây là ví dụ ID/citation có nguồn chưa bảo đảm đáp án đúng.
- **`d7-dev-10`**: trả đúng nguyên tắc cấm mua/bán và ngoại lệ nhưng thêm khái quát về mọi xử lý phải có sự đồng ý vượt phạm vi khoản 2 Điều 22, không giữ ngoại lệ; answer chấm 1 và citation cho phần thêm bị đánh không đủ hỗ trợ. Context có gold vẫn không bảo đảm model sử dụng đúng phạm vi.

Các lỗi nội dung này được giữ nguyên, không sửa câu trả lời/gold để tăng điểm. Chúng là đầu vào thử nghiệm cải thiện trên dev ở phần 4.

## Token, chi phí và lượt tích hợp lỗi

Theo [trang model chính thức](https://developers.openai.com/api/docs/models/gpt-4.1-mini), đơn giá được ghi ngày 14/11/2026: input 0,40 USD, cached input 0,10 USD, output 1,60 USD trên một triệu token. Cấu hình giữ nguồn/ngày và tính theo usage thực tế; đây là ước tính, không phải hóa đơn.

Lượt đầy đủ `dev-v2`: input **39.106**, cached input **0**, output **2.574** token; ước tính model **0,0197608 USD**. Query embedding có **14 request**, **529 token**, **4 cache hit**, ước tính **0,00001058 USD** theo đơn giá embedding cấu hình kế thừa. Tổng ước tính lượt đầy đủ **0,01977138 USD**, chưa gồm hạ tầng/thuế/retry không trả usage. Không tạo lại document embedding.

Lượt tích hợp đầu `dev-v1` bị dừng sau 5 trace vì model không tuân thủ định dạng citation inline của phiên bản đầu. Đã giữ trace, config/code checksum và ghi `status=interrupted`; không coi nó là benchmark đầy đủ hoặc một trong hai thử nghiệm cải thiện phần 4. Phần usage thu hồi từ 5 trace đã hoàn tất: 30 request model, input 39.975 (cached 16.256), output 4.556 token, ước tính model tối thiểu 0,0184028 USD. Có request/case đang thực thi khi dừng nên usage còn lại chưa xác định, không giả thành 0. Chi phí lượt tích hợp này không nằm trong tổng dev-v2 ở trên.

Đã sửa cách trao đổi định dạng và bộ render citation, bổ sung regression test, rồi chạy lại đủ dev thành `dev-v2`. Không xóa/làm lại test hoặc thay benchmark để xử lý lỗi tích hợp.

## Kiểm tra

38 unit tests pass, gồm giới hạn lượt gọi, context mới thay context cũ, giữ filter, lỗi hạ tầng, nguồn ngoài context, chuẩn hóa nhãn, phân tách dữ liệu không đáng tin và tính cached-input cost. Test nội dung chỉ bảo đảm phân tách vai trò dữ liệu, không tự chứng minh model luôn chống được prompt injection.

Trace thật đã được kiểm tra: filter đúng, không có trường gold/nhãn trong input model, context và số lượt trong giới hạn, checksum dữ liệu/code khớp. `summary.json` là thống kê cơ học chưa chấm nội dung; `evaluation.json` là kết quả từ file nhãn AI review riêng. Không trộn hai loại bằng chứng.

Phần 4 hoàn thành: [thử nghiệm, lựa chọn và test](EXPERIMENTS.md).
