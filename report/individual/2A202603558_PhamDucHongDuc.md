# Báo cáo Day 7

**Phạm Đức Hồng Đức — 2A202603558 — L3A**

## Dữ liệu và benchmark

- **Nguồn, quyền sử dụng, số trang và số chunk:** kế thừa corpus Day 6 về an ninh mạng và bảo vệ dữ liệu cá nhân, gồm Luật 24/2018/QH14 (32 trang PDF) và Nghị định 13/2023/NĐ-CP (39 trang PDF), từ Cổng Thông tin điện tử Chính phủ. Dùng 60 trang nội dung: toàn bộ Luật và trang 1–28 Nghị định, loại 11 trang phụ lục khỏi index chính. Corpus có 115.159 ký tự; dùng cùng 336 chunk strategy C cho cả ba phương pháp, giữ nguyên ID, text, nguồn, trang và metadata. `page` là trang vật lý PDF từ 1. URL, checksum và căn cứ quyền sử dụng văn bản quy phạm pháp luật được lưu trong [manifest](../../data/manifest.json). Hai văn bản là snapshot gốc, không khẳng định hiệu lực hiện hành; OCR Nghị định chưa được hiệu đính toàn văn.
- **Vector store, embedding model, phiên bản và số chiều:** PostgreSQL 16.16, pgvector 0.8.7; exact cosine bằng `<=>`, bảng `day6_chunks`, strategy C, namespace `day6-v1:text-embedding-3-small:1536:nfc-ws-v1`. OpenAI `text-embedding-3-small`, 1536 chiều; query/document cùng NFC + gộp whitespace, không prefix. Embedding dùng alias, giữ cache vector thật và request metadata để truy vết. SDK OpenAI 2.54.0, psycopg 3.3.9, tiktoken 0.14.0; dependencies cố định trong [requirements-lock.txt](../../requirements-lock.txt). Kết nối qua `.env` local và Docker, cổng `127.0.0.1:55433`, project `day6_student_starter`; không đưa key vào Git.
- **Agent model, cách chạy và phân chia dev/test:** model `gpt-4.1-mini-2025-04-14`, native function calling, temperature 0. [Benchmark LAB07](../../benchmark/README.md) có 24 câu: dev 15 câu có đáp án + 2 thiếu evidence; test 5 câu có đáp án + 2 thiếu evidence. Dev kế thừa 15 câu Day 6 với sửa phạm vi một câu trước khi chạy LAB07; năm câu test có đáp án được soạn mới, không trùng cặp nguồn/Điều với dev hoặc test Day 6. Chạy bằng CLI Python tại root, lệnh cụ thể bên dưới.
- **Cách xác định câu có/thiếu evidence và tiêu chí chấm:** câu có đáp án có nguồn/trang, đáp án chuẩn và evidence nguyên văn nằm trọn trong chunk; đối chiếu ảnh PDF gốc. Câu thiếu evidence có lý do, quét đủ 60 trang và xem các phần liên quan, không dựa vào việc top-k tìm không thấy. Nhãn được tách khỏi input model tại `benchmark/inputs/`; retriever chỉ nhận query và filter người dùng cung cấp. Retrieval chấm Hit@1, Evidence Hit@3 và Context Evidence Rate trên câu có đáp án, báo `n/N` và tỷ lệ. Câu trả lời/context chấm 0/1/2; citation cần có trong context và thực sự hỗ trợ nội dung; chấm từ chối đúng và từ chối nhầm. Nhãn semantic do trợ lý AI đọc đối chiếu nguồn, không phải xác nhận độc lập của con người.

## Retrieval và thử nghiệm

Ba phương pháp chạy trên cùng corpus, chunk/index snapshot và 17 câu dev, query gốc; filter `doc_type/year` có sẵn trong input được áp dụng như nhau. BM25 tách âm tiết/số bằng NFC + casefold, giữ dấu, không stopword, k1=1,5 và b=0,75; thống kê corpus giữ cố định khi lọc. Hybrid hợp nhất thứ hạng Dense/BM25 bằng RRF hằng số 60, không cộng trực tiếp hai loại score. Lấy top-20 mỗi nhánh, xuất top-3, đóng gói chunk nguyên vẹn và nhãn nguồn trong budget 2000 ký tự.

| Cấu hình | Phương pháp, top-k, filter, rerank, context budget | Giả thuyết / thay đổi | Split | Hit@1 | Evidence Hit@3 | Context Evidence Rate | Thời gian / chi phí |
|---|---|---|---|---|---|---|---|
| Dense | pgvector cosine; top-3; filter input; không rerank; 2000 ký tự | Baseline ngữ nghĩa từ Day 6 | dev | 13/15 (86,67%) | 13/15 (86,67%) | 13/15 (86,67%) | Trung vị ghép bước 31,11 ms; embedding dùng chung với Hybrid |
| BM25 | k1=1,5; b=0,75; top-3; cùng filter; 2000 ký tự | Từ khóa/thuật ngữ/số có thể hỗ trợ tìm bằng chứng | dev | 8/15 (53,33%) | 12/15 (80,00%) | 12/15 (80,00%) | 4,95 ms; không có embedding API |
| Hybrid RRF | Dense + BM25; 20 candidate/nhánh; RRF 60; top-3; 2000 ký tự | Kết hợp các ranking để phục hồi evidence bị một nhánh bỏ lỡ | dev | 11/15 (73,33%) | 14/15 (93,33%) | 14/15 (93,33%) | 35,78 ms; embedding dùng chung với Dense |

Lượt này có 51 trace, không lỗi. Không chunk top-3 nào bị loại vì budget, nên Context Evidence Rate bằng Hit@3 trong cấu hình này. Thời gian bảng là tổng các thành phần đo được khi chia sẻ embedding/kết quả nhánh, không phải ba lượt standalone độc lập. Có 14 query cache hit và 3 request embedding thật, 215 token API; 958 token embedding logic cho mỗi pipeline Dense/Hybrid. Chi phí API dùng chung ước tính 0,0000043 USD theo đơn giá cấu hình 0,02 USD/triệu token, không phải hóa đơn; không cộng chi phí dùng chung hai lần. [Trace, metrics và cấu hình](../../results/retrieval/dev-v1/), [phân tích retrieval](../../docs/RETRIEVAL.md).

Hai lỗi dev đã đọc và phân tích:

1. `d7-dev-01`: Dense/BM25/Hybrid ưu tiên đoạn biện pháp, triển khai hoặc đấu tranh thay cho định nghĩa cần hỏi. Gold đúng ở hạng 14 Dense và ngoài top-20 BM25. Hybrid vẫn trượt top-3 vì ưu tiên các đoạn được cả hai nhánh đồng thuận. Đây là lỗi khớp ý định, không phải lỗi database.
2. `d7-dev-11`: quy tắc im lặng/không phản hồi ở hạng 5 Dense, hạng 4 BM25; Hybrid đưa lên hạng 3 và phục hồi context. Các đoạn sai nói về rút lại đồng ý, xóa dữ liệu hoặc người mất tích/đã chết. Hybrid tăng Hit@3 nhưng làm giảm Hit@1 so với Dense ở một số câu do hòa thứ hạng và phá hòa bằng ID.

Hai cấu hình cải thiện được đăng ký trước khi chạy tại [kế hoạch](../../configs/experiments.json). Cùng corpus, model, filter input và Hybrid RRF; E1 mở rộng candidate/context, E2 thêm chỉ dẫn chung kiểm tra ý định và phạm vi evidence. Bảng dưới dùng **query gốc**, một lượt Hybrid cố định. Thời gian/chi phí là **toàn lượt agent tương ứng**, không phải retrieval riêng.

| Cấu hình | Phương pháp, top-k, filter, rerank, context budget | Giả thuyết / thay đổi | Split | Hit@1 | Evidence Hit@3 | Context Evidence Rate | Thời gian / chi phí |
|---|---|---|---|---|---|---|---|
| Cải thiện 1 — Wide | Hybrid; 40 candidate/nhánh; top-15; filter input; không rerank; 10000 ký tự | Tăng độ sâu/context để giữ evidence dưới top-3 | dev | 11/15 (73,33%) | 14/15 (93,33%) | 15/15 (100%) | 2973,93 ms/câu; 0,04443180 USD/lượt 17 câu |
| Cải thiện 2 — Focused | Hybrid; 20 candidate/nhánh; top-3; filter input; không rerank; 2000 ký tự | Kiểm tra đúng ý định, tránh khái quát vượt điều kiện nguồn | dev | 11/15 (73,33%) | 14/15 (93,33%) | 14/15 (93,33%) | 2681,67 ms/câu; 0,02373044 USD/lượt 17 câu |
| Cấu hình đã chọn — Focused | Như E2; giữ nguyên sau khi chốt | Đánh giá sau chọn trên dev | test | 4/5 (80%) | 5/5 (100%) | 5/5 (100%) | 2805,38 ms/câu; 0,01009236 USD/lượt 7 câu |
| Baseline agent-v1.1 | Hybrid ban đầu; prompt gốc; 2000 ký tự | Đối chứng cùng test | test | 4/5 (80%) | 5/5 (100%) | 5/5 (100%) | 3215,09 ms/câu; 0,01015170 USD/lượt 7 câu |

[Query gốc dev](../../results/experiments/original-query-reference.json) và [query gốc test](../../results/experiments/original-query-test-reference.json) giữ ranking/context từng câu. Hit@3 luôn cắt ở hạng 3, kể cả Wide xuất top-15. Query gốc test dùng chung embedding cho hai cấu hình; usage/chi phí riêng lưu trong artifact, không tính lặp vào chi phí agent trong bảng.

Kết quả trước/sau trên lỗi dev:

- `d7-dev-01`: baseline answer/context 0/0. Wide đưa đủ gold vào context (mức 2), nhưng câu trả lời vẫn thiếu hoạt động “xử lý” và lẫn danh sách biện pháp nên answer chỉ tăng lên 1. Focused vẫn 0/0; chỉ dẫn chung chưa sửa được lỗi ý định.
- `d7-dev-10`: cả baseline, Wide và Focused đều answer 1/context 2. Cấm mua/bán được trả lời đúng nhưng phần thêm về sự đồng ý vẫn khái quát quá rộng; hai thử nghiệm không sửa được lỗi này.
- `d7-dev-06`: Wide giảm answer từ 2 xuống 1 vì phần thêm gán nghĩa vụ xử lý nghiêm cho phạm vi chủ thể rộng hơn nguồn hỗ trợ. Context lớn có đủ evidence nhưng tạo thêm nội dung ngoài câu hỏi.

Tiêu chí chọn đã công bố: grounded trung bình → citation hợp lệ → abstention → context evidence → Hit@3 rồi Hit@1 lượt retrieval đầu thực tế → thời gian → chi phí → độ đơn giản. Cả ba đạt 1,8/2; Wide có 20/22 citation hợp lệ (90,91%), thấp hơn baseline/Focused 16/17 (94,12%), nên bị loại trước khi xét lợi ích context 15/15. Focused hòa baseline ở các tiêu chí trước và thắng Hit@1 của **query đầu do model tạo**: 10/15 (66,67%) so với 9/15 (60%); Hit@3 đều 14/15 (93,33%). Wide cũng có Hit@1 thực tế 10/15. Query gốc baseline/Focused cùng 11/15; E2 không làm tăng số câu trả lời hoàn toàn đúng trên dev.

Đã chốt **Focused** lúc `2026-11-14T09:47:22.062262+00:00`, lưu checksum config/code/benchmark trong [selection.json](../../results/experiments/selection.json), trước lượt baseline test bắt đầu lúc `09:47:22.377815+00:00`. Runner test chỉ chấp nhận baseline/cấu hình đã chọn có checksum đúng. Không chỉnh cấu hình theo test. Hai cấu hình bằng nhau về chất lượng trên test nhỏ; thời gian là một lượt đo, cache embedding khác nhau nên không kết luận tốc độ tổng quát.

## Agent và đánh giá

- **Tool, số lượt gọi, điều kiện dừng, context và lỗi:** agent-v1.1 cung cấp `search_dense`, `search_bm25`, `search_hybrid`; model chọn tool/query, filter do ứng dụng giữ cố định. Tối đa 3 lượt retrieval, 6 lượt model, top-3 và budget context 2000 ký tự. Context ưu tiên kết quả mới, dedup ID, giữ chunk nguyên vẹn; mỗi request model chỉ có một snapshot context hiện tại, tránh cộng dồn các tool output cũ. Kết thúc khi model trả lời/từ chối, hết lượt hoặc lặp tool/query. Citation được chuẩn hóa định dạng và kiểm tra ID trong context cuối; hỗ trợ ngữ nghĩa được đọc riêng. Lỗi provider/store giữ `status=error`, không thay bằng mock hoặc coi là thiếu evidence.

| Cấu hình / split | Tool use | Số lượt gọi | Grounded answer 0/1/2 và trung bình | Citation hợp lệ | Câu có citation | Abstention đúng | Từ chối nhầm |
|---|---|---|---|---|---|---|---|
| Agent-v1.1 / dev | 17/17 | 37 model request; 20 retrieval: Hybrid 18, BM25 2; 15 câu tìm 1 lượt, 1 câu 3 lượt, 1 câu 2 lượt | 1 / 1 / 13; 1,8/2 | 16/17 (94,12%) | 15/15 | 2/2 | 0/15 |
| Wide / dev | 17/17 | 38 model; 21 retrieval (Hybrid 19, BM25 2); 15 câu 1 lượt, 2 câu 3 lượt | 0 / 3 / 12; 1,8/2 | 20/22 (90,91%) | 15/15 | 2/2 | 0/15 |
| Focused / dev | 17/17 | 38 model; 21 retrieval (Hybrid 19, BM25 2); 15 câu 1 lượt, 2 câu 3 lượt | 1 / 1 / 13; 1,8/2 | 16/17 (94,12%) | 15/15 | 2/2 | 0/15 |
| Baseline / test | 7/7 | 18 model; 11 retrieval (Hybrid 10, BM25 1); 5 câu 1 lượt, 2 câu 3 lượt | 0 / 0 / 5; 2/2 | 5/5 (100%) | 5/5 | 2/2 | 0/5 |
| Focused / test | 7/7 | 16 model; 9 retrieval (Hybrid 8, BM25 1); 6 câu 1 lượt, 1 câu 3 lượt | 0 / 0 / 5; 2/2 | 5/5 (100%) | 5/5 | 2/2 | 0/5 |

Với baseline dev, context có evidence nguyên văn 14/15; nhãn context: một mức 0, mười bốn mức 2. Có 15 answered, 2 abstain, không lỗi hạ tầng. Wide có context mức 2 ở 15/15 câu; Focused có một mức 0, mười bốn mức 2. Không diễn giải 15 answered thành 15 câu đúng hoặc điểm trung bình 1,8/2 thành tỷ lệ câu hoàn toàn đúng.

| Query ID | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do |
|---|---|---|---|---|
| `d7-dev-11` | Có đáp án | Hybrid, tìm được khoản 6 Điều 11 trang 9 Nghị định | Im lặng/không phản hồi không được coi là đồng ý; cite chunk `e1b1b447...` (ID đầy đủ trong trace) | Answer 2; context 2; nguồn hỗ trợ đầy đủ |
| `d7-dev-u01` | Thiếu evidence | 3 lượt Hybrid/BM25, không có số hồ sơ của sự cố giả định | Không đủ bằng chứng; không bịa số liệu, không citation | Từ chối đúng, model chủ động abstain |
| `d7-dev-u02` | Thiếu evidence | 2 lượt tìm về thông số AES, model định lặp query | Ứng dụng dừng lặp và xuất câu từ chối cố định | Từ chối đúng, do guard ứng dụng |
| `d7-dev-01` | Có đáp án | Hybrid trả các biện pháp Điều 5 trang 4 | Liệt kê biện pháp thay cho định nghĩa; cite nguồn có thật | Answer 0, context 0; citation hỗ trợ danh sách đã viết nhưng sai trọng tâm |
| `d7-dev-10` | Có đáp án | Hybrid có quy tắc tại Điều 3 và đoạn Điều 22 | Đúng nguyên tắc cấm mua/bán nhưng thêm khái quát consent quá rộng | Answer 1, context 2; một citation không đủ hỗ trợ phạm vi khẳng định thêm |

- **Trace, nhãn, thời gian và chi phí:** [run/config/usage](../../results/agent/dev-v2/run.json), [traces](../../results/agent/dev-v2/traces.jsonl), [nhãn có lý do từng câu/citation](../../results/agent/dev-v2/reviews.json), [evaluation](../../results/agent/dev-v2/evaluation.json). Trung vị end-to-end 2768,43 ms/câu; model input 39.106, output 2.574 token, cached input 0, chi phí ước tính 0,0197608 USD. Embedding có 14 request, 529 token, 4 cache hit, ước tính 0,00001058 USD. Tổng lượt đầy đủ 0,01977138 USD theo đơn giá ghi trong cấu hình; không gồm hạ tầng/thuế/retry chưa trả usage. Lượt pilot bị ngắt do định dạng citation được bảo toàn ở `results/agent/dev-v1/`; ước tính model thu hồi tối thiểu 0,0184028 USD, usage còn lại không xác định, không tính vào tổng dev-v2.
- **Đánh đổi và giới hạn:** corpus hai văn bản, test nhỏ, OCR có lỗi; BM25 chưa tách từ tiếng Việt theo từ điển; filter loại/năm tương quan trong corpus. Retrieval tốt chưa bảo đảm trả lời đúng: lỗi `d7-dev-10` có evidence nhưng model mở rộng phạm vi; `d7-dev-01` có citation thật nhưng sai ý hỏi. Review semantic do AI thực hiện nên cần công khai nguy cơ thiên lệch. 38 unit tests pass; benchmark thực tế dùng model/store thật, không suy chất lượng từ mock tests.

Đã đọc đối chiếu cả 5 câu có đáp án và 2 câu thiếu evidence của **mỗi cấu hình test**. Cả hai có context mức 0/1/2 = 0/0/5 trên câu có đáp án, CER 5/5 (100%); Hit@1/Hit@3 lượt tìm đầu thực tế là 4/5 (80%) và 5/5 (100%).

| Query ID | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do cho cả baseline và Focused |
|---|---|---|---|---|
| `d7-test-01` | Có đáp án | Hybrid, Luật Điều 32, trang 28 | Tiêu chuẩn công dân tham gia lực lượng; cite `694d2406...` | Answer/context 2/2; đủ phẩm chất, sức khỏe, kiến thức và tự nguyện |
| `d7-test-02` | Có đáp án | Hybrid, Luật Điều 34, trang 28 | Trách nhiệm UBND cấp tỉnh tại địa phương; cite `5c4323c5...` | 2/2; đúng chủ thể và phạm vi quản lý |
| `d7-test-03` | Có đáp án | Hybrid, Nghị định Điều 9, trang 7 | Cung cấp dữ liệu trong 72 giờ từ yêu cầu, giữ ngoại lệ luật; cite `93f1a19c...` | 2/2; đủ thời hạn, điều kiện và nguồn |
| `d7-test-04` | Có đáp án | Hybrid, Nghị định Điều 24, trang 19 | 01 bản chính Mẫu 04 gửi cơ quan quy định trong 60 ngày từ xử lý; cite `4ac08fda...` | 2/2; đúng nơi nhận, hồ sơ, hạn và mốc tính |
| `d7-test-05` | Có đáp án | Hybrid, Nghị định Điều 31, trang 24 | Tổ chức/doanh nghiệp tự bố trí kinh phí; cite `3b6e77c8...` | 2/2; nguồn hỗ trợ trực tiếp |
| `d7-test-u01` | Thiếu evidence | Tìm thêm, không có thống kê năm 2025 | Model abstain, không bịa số khiếu nại | Từ chối đúng |
| `d7-test-u02` | Thiếu evidence | Tìm yêu cầu về mã SQL | Model abstain, không tự viết mã thay evidence | Từ chối đúng |

ID đầy đủ, từng tool call, context, câu trả lời nguyên văn và lý do từng citation nằm trong [baseline test](../../results/experiments/baseline-test/) và [Focused test](../../results/experiments/focused-test/); mỗi thư mục có `traces.jsonl`, `reviews.json`, `evaluation.json`, `run.json`, `summary.json`. Dev tương ứng ở [Wide](../../results/experiments/wide-dev/) và [Focused](../../results/experiments/focused-dev/). Review do AI thực hiện sau chạy, không phải xác nhận độc lập của con người.

Token và chi phí các lượt mới (input cached đều 0; chi phí USD ước tính theo đơn giá cấu hình, không phải hóa đơn):

| Lượt | Input / output model | Model USD | Token embedding / USD | Tổng USD |
|---|---|---|---|---|
| Wide dev | 99356 / 2928 | 0,04442720 | 230 / 0,00000460 | 0,04443180 |
| Focused dev | 48974 / 2586 | 0,02372720 | 162 / 0,00000324 | 0,02373044 |
| Baseline test | 21043 / 1079 | 0,01014360 | 405 / 0,00000810 | 0,01015170 |
| Focused test | 21106 / 1028 | 0,01008720 | 258 / 0,00000516 | 0,01009236 |

Wide không tăng điểm grounded trung bình và làm giảm citation, với chi phí cao hơn baseline. Focused giữ 13/15 câu dev mức 2 và cũng có chi phí cao hơn baseline; lợi ích quyết định chọn chỉ nằm ở ranking lượt đầu thực tế theo tiêu chí đã công bố. Test chỉ có 5 câu có đáp án và 2 câu thiếu evidence, không đủ để khẳng định chất lượng trên mọi câu hỏi. Đã chạy 38 unit tests thành công.

Các lệnh đã dùng :

```powershell
.venv/Scripts/python.exe scripts/day6_setup.py check-store
.venv/Scripts/python.exe -X utf8 scripts/validate_benchmark.py
.venv/Scripts/python.exe -X utf8 -m src.retrieval_benchmark run --output results/retrieval/dev-v1
.venv/Scripts/python.exe -X utf8 -m src.retrieval_benchmark score --output results/retrieval/dev-v1
.venv/Scripts/python.exe -X utf8 -m src.agent_benchmark dev --output results/agent/dev-v2
.venv/Scripts/python.exe -X utf8 -m src.agent_review --run results/agent/dev-v2 --reviews results/agent/dev-v2/reviews.json
.venv/Scripts/python.exe -X utf8 -m src.agent_benchmark dev --config configs/agent-wide.json --output results/experiments/wide-dev
.venv/Scripts/python.exe -X utf8 -m src.agent_benchmark dev --config configs/agent-focused.json --output results/experiments/focused-dev
.venv/Scripts/python.exe -X utf8 -m src.agent_review --run results/experiments/wide-dev --reviews results/experiments/wide-dev/reviews.json
.venv/Scripts/python.exe -X utf8 -m src.agent_review --run results/experiments/focused-dev --reviews results/experiments/focused-dev/reviews.json
.venv/Scripts/python.exe -X utf8 scripts/original_query_reference.py
.venv/Scripts/python.exe -X utf8 scripts/select_agent.py
.venv/Scripts/python.exe -X utf8 -m src.agent_benchmark test --config configs/agent.json --output results/experiments/baseline-test
.venv/Scripts/python.exe -X utf8 -m src.agent_benchmark test --config configs/agent-focused.json --output results/experiments/focused-test
.venv/Scripts/python.exe -X utf8 -m src.agent_review --run results/experiments/baseline-test --reviews results/experiments/baseline-test/reviews.json
.venv/Scripts/python.exe -X utf8 -m src.agent_review --run results/experiments/focused-test --reviews results/experiments/focused-test/reviews.json
.venv/Scripts/python.exe -X utf8 scripts/original_query_test_reference.py
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v
```

Review tổng hợp nhãn đã đọc nguồn và lưu riêng, không tự tạo nhãn đúng/sai. Selection chỉ chốt một lần trước test và không được ghi đè. Runner từ chối output đã tồn tại; khi tái lập dùng thư mục mới. Xem thêm [hướng dẫn kết nối](../../docs/DAY6_HANDOFF.md) và [hướng dẫn agent](../../docs/AGENT.md).
