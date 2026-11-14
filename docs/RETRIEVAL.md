# Phần 2 - Dense, BM25 và Hybrid RRF

Đã triển khai và chạy ba phương pháp trên toàn bộ 17 câu dev, cùng 336 chunk strategy C kế thừa Day 6. Lượt retrieval riêng ngày 14/11/2026 ở `results/retrieval/dev-v1/` chỉ dùng dev, không đổi corpus/gold. Việc chọn cấu hình agent và đánh giá test được thực hiện riêng ở [phần 4](EXPERIMENTS.md).

## Cấu hình và thuật toán

`configs/retrieval.json` được ghi trước lượt chạy; bản cấu hình và checksum code/dữ liệu được lưu trong `run.json`.

| Thành phần | Cấu hình |
|---|---|
| Dense | OpenAI `text-embedding-3-small`, 1536 chiều; PostgreSQL/pgvector Day 6; exact cosine, strategy C |
| BM25 | Python standard library; `k1=1.5`, `b=0.75`, positive IDF; không dùng TF-IDF trong ba phương pháp được so sánh |
| Hybrid | RRF hai nhánh dense/BM25, trọng số bằng nhau, hằng số 60 |
| Candidates | Top-20 mỗi nhánh, lấy top-3 kết quả cuối để so sánh |
| Filter | Cùng `doc_type`, `year` do input người dùng cung cấp; không suy ra filter từ gold |
| Query | Query gốc, không viết lại/ghép đáp án |
| Context | Top-3 theo thứ hạng, loại trùng ID, giữ nguyên chunk và nguồn/trang; tối đa 2000 ký tự gồm nhãn nguồn |

Dense kiểm tra namespace, model/số chiều và toàn bộ ID/text/source/page/metadata so với corpus lexical trước khi embedding query. Không tạo embedding document mới. Query dùng đúng NFC + gộp whitespace như Day 6. Các kết quả có `id`, `text`, `source_id`, `source`, `page`, `metadata`, `score`, `rank`, `method`, `score_type`.

BM25 tách token bằng Unicode NFC + casefold, lấy các chuỗi chữ/số, giữ dấu, tách dấu câu/underscore, không bỏ stopword. Đây là tách âm tiết/số tiếng Việt, chưa phải tách từ theo từ điển; lỗi OCR và từ ghép có thể ảnh hưởng kết quả. IDF và độ dài trung bình tính trên cả 336 chunk, giữ cố định khi filter giới hạn tập ứng viên. Query term chỉ tính một lần. Score:

```text
idf(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))
score(d,q) = sum over unique t in q:
  idf(t) * tf(t,d) * (k1+1) / (tf(t,d) + k1*(1-b+b*len(d)/avgdl))
```

Nền tảng BM25 theo [Robertson và Zaragoza, BM25 and Beyond](https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf); biến thể IDF dương được mô tả trong [Apache Lucene BM25Similarity](https://lucene.apache.org/core/10_3_1/core/org/apache/lucene/search/similarities/BM25Similarity.html). Code này không dùng Lucene; các tham số và cách tính được khai báo riêng ở trên.

RRF cộng `1/(60 + rank)` từ mỗi nhánh có chứa chunk, rank bắt đầu từ 1; không có chunk trong nhánh thì không có đóng góp. Tham khảo [Cormack, Clarke và Büttcher, SIGIR 2009](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf). Không cộng trực tiếp cosine và BM25 score. Khi hòa score, dùng ID tăng dần để tái lập. Mỗi hit hybrid giữ `branch_ranks` và `branch_scores`; trace giữ cả hai danh sách candidates. Chunk trùng ID giữa hai nhánh phải có cùng text/nguồn/trang/metadata.

## Chạy và chấm riêng

Từ thư mục gốc LAB07, sau khi Docker/database hoạt động và `.env` đã cấu hình:

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v
.venv/Scripts/python.exe -X utf8 -m src.retrieval_benchmark run --output results/retrieval/dev-v2
.venv/Scripts/python.exe -X utf8 -m src.retrieval_benchmark score --output results/retrieval/dev-v2
```

`dev-v1` đã có kết quả thật; ví dụ dùng `dev-v2` để bảo toàn lượt chạy cũ. Runner từ chối thư mục output đã tồn tại. Lệnh `run` chỉ nhận input từ `benchmark/inputs/dev.json`, chỉ gửi query và filter tới retriever/provider. Gold được mở ở lệnh `score` riêng sau khi retrieval kết thúc. Runner phần 2 không hỗ trợ chạy test. Không cần chạy lại API để đọc các artifacts đã có.

Khi tích hợp agent:

```python
import json
from pathlib import Path
from src.day6.retrieval import DenseRetriever
from src.retrieval import BM25Retriever, HybridRetriever

chunks = json.loads(Path("data/chunks.json").read_text(encoding="utf-8"))
bm25 = BM25Retriever(chunks, k1=1.5, b=0.75)
with DenseRetriever() as dense:
    dense.verify_snapshot(chunks)
    hybrid = HybridRetriever(dense, bm25, candidate_k=20, rank_constant=60)
    hits = hybrid.search("Bảo vệ an ninh mạng bao gồm những hoạt động nào?", top_k=3)
```

Adapter của cả ba phương pháp có cùng `search(query, filters=None, top_k=...)`. Lỗi provider/store được ghi bằng loại lỗi, không ghi secret/DSN và không fallback mock. Hybrid không âm thầm thay bằng BM25 nếu dense lỗi.

## Kết quả dev thực tế

Định nghĩa hit tự động: đúng nguồn, đúng trang và chứa nguyên evidence hoàn chỉnh. Mẫu số là 15 câu có đáp án; hai câu thiếu evidence không được đưa vào mẫu số. Lỗi được báo riêng và tính là miss trong phép đo retrieval nếu có. Chỉ số này chưa thay thế việc đọc đối chiếu bằng chứng tương đương và chưa đánh giá câu trả lời/citation của agent.

| Phương pháp | Hit@1 | Evidence Hit@3 | Context Evidence Rate | Trung vị thời gian ghép các bước (ms) | Lỗi |
|---|---|---|---|---:|---:|
| Dense | 13/15 (86,67%) | 13/15 (86,67%) | 13/15 (86,67%) | 31,11 | 0 |
| BM25 | 8/15 (53,33%) | 12/15 (80,00%) | 12/15 (80,00%) | 4,95 | 0 |
| Hybrid RRF | 11/15 (73,33%) | 14/15 (93,33%) | 14/15 (93,33%) | 35,78 | 0 |

Tổng 51 trace (17 câu x 3 phương pháp), không có lỗi. Tất cả kết quả tuân thủ filter và ID duy nhất. Context dài nhất Dense/Hybrid 1705 ký tự, BM25 1730; không chunk top-3 nào bị bỏ vì budget 2000, nên Context Evidence Rate bằng Hit@3 trong lượt này. Đây là tính chất cấu hình đã chạy, không phải quan hệ luôn đúng giữa hai chỉ số.

Hai câu thiếu evidence vẫn trả về các đoạn có từ khóa/chủ đề liên quan. Không suy ra chúng trả lời được chỉ vì có kết quả hoặc score cao; việc từ chối sẽ được kiểm tra khi có agent thật ở phần 3.

## Thời gian, cache và chi phí

Lượt chạy dùng chung một embedding query thật cho Dense và Hybrid. BM25 build một lần khoảng 0,02424 giây. Với mỗi query, đo riêng embedding, cosine search, BM25, RRF và đóng gói context. Thời gian trong bảng là tổng các thành phần đo được để biểu diễn từng pipeline; không phải ba lượt gọi độc lập được đo từ đầu đến cuối. Hybrid tái sử dụng kết quả hai nhánh và không chạy lại API. Không dùng những số này để khẳng định tốc độ tổng quát hoặc tốc độ khi cache lạnh.

- 17 query: **14 cache hit**, **3 request OpenAI thật**, **215 token API**; request ID và model trả về trong `run.json`/trace.
- Tổng nhu cầu embedding logic của 17 query: **958 token** cho mỗi pipeline Dense hoặc Hybrid; BM25 không có embedding API. Không cộng 958 hai lần thành token API đã tính tiền.
- Đơn giá cấu hình local là 0,02 USD/triệu token, kế thừa cấu hình Day 6, chưa xác minh lại giá hiện hành trong lượt này. Chi phí API ghi nhận ước tính **0,0000043 USD** dùng chung một lần; nhu cầu logic nếu không có cache tương ứng **0,00001916 USD/pipeline**. Đây không phải hóa đơn; chưa gồm hạ tầng, thuế hay retry chưa được provider trả usage.
- Không gọi model sinh câu trả lời hoặc LLM judge ở phần 2; chưa có chi phí/metrics agent.

## Phân tích lỗi dev và đánh đổi

Đã đọc top-3 và context của ít nhất hai lỗi dev; sáu nhãn context có lý do nằm trong `dev_error_review.json`. Reviewer là trợ lý AI, chưa phải kiểm tra độc lập của học viên.

1. **`d7-dev-01` - nhầm định nghĩa với biện pháp/triển khai.** Câu hỏi cần bốn hoạt động trong định nghĩa ở Luật trang 1. Dense top-3 đưa về Điều 5, Điều 23, Điều 22; evidence đúng ở hạng 14 của dense. BM25 không có evidence trong top-20. Hybrid tiếp tục ưu tiên những đoạn cùng được cả hai nhánh xếp cao, nên cả ba trượt Hit@3/context. Context ở cả ba được chấm 0 cho evidence cần hỏi. Giả thuyết cho thử nghiệm tiếp: query transformation tổng quát để nhận diện câu hỏi định nghĩa, hoặc rerank candidate dựa trên độ khớp ý định. Chưa thực hiện, không thêm gold/đáp án vào query.

2. **`d7-dev-11` - nhầm im lặng với rút lại/thiếu sự đồng ý trong tình huống khác.** Gold ở Nghị định trang 9: im lặng hoặc không phản hồi không được coi là đồng ý. Dense xếp chunk đúng hạng 5, BM25 hạng 4; các đoạn top-3 từng nhánh nói về rút lại đồng ý, xóa dữ liệu, hạn chế xử lý hoặc người mất tích/đã chết. Context Dense/BM25 chấm 0; hybrid đưa đoạn đúng lên hạng 3 và context chấm 2. Với câu này, hợp nhất top-20 đã phục hồi evidence mà top-3 từng retriever bỏ lỡ.

3. **RRF có đánh đổi Hit@1.** Với `d7-dev-03`, dense đặt gold hạng 1, BM25 hạng 2; một chunk liên quan khác có thứ hạng ngược lại. Tổng RRF bằng nhau và ID phá hòa làm gold xuống hạng 2. Hybrid tăng Hit@3 trên dev nhưng Hit@1 giảm so với Dense. Không kết luận hybrid tốt hơn ở mọi tiêu chí.

BM25 trượt Hit@3 ở `d7-dev-01`, `d7-dev-10`, `d7-dev-11`; Dense trượt `01`, `11`; Hybrid trượt `01`. Đây là kết quả exact-evidence; không tự sửa gold hoặc metric sau khi xem ranking. Hướng tách từ tiếng Việt, độ dài candidate, tham số BM25, rerank hoặc query transformation có thể thử sau trên dev với giả thuyết và cấu hình riêng. Chưa tuyên bố hoàn thành hai thử nghiệm cải thiện có đo lại của phần 4.

## Artifacts

Trong `results/retrieval/dev-v1/`:

- `run.json`: cấu hình, model/store/version, checksum, thời gian build/setup và usage thật.
- `traces.jsonl`: từng query/method, filter, ranking/score, candidates hai nhánh, context, timing và cache.
- `summary.json`, `comparison.csv`: bảng metrics tự động và mẫu số.
- `evidence_audit.json`: kết quả exact-evidence từng câu do evaluator chấm sau retrieval.
- `dev_error_review.json`: sáu nhãn context ở hai lỗi dev, kèm lý do; không phải nhãn câu trả lời agent.

Đã chạy 27 unit tests, gồm tính BM25 theo ví dụ số, chuẩn hóa Unicode, filter, RRF theo rank, chống trùng/sai ID, budget có nguồn, truyền lỗi và chống đưa gold vào input. Kiểm tra thực tế database/API được chứng minh bằng artifacts riêng, không suy ra từ mock tests.

Phần 2 đã có đủ ba phương pháp và benchmark dev. Model thật điều phối tool/context đã được nối ở [phần 3](AGENT.md), có nhãn grounded answer/citation/abstention dev riêng. [Phần 4](EXPERIMENTS.md) đã thử Wide/Focused, chọn trên dev và chạy baseline/cấu hình chọn trên test sau khi chốt.
