# Chuẩn bị LAB07: kế thừa Day 6

Đã chuyển các tài sản cần thiết vào LAB07 và xóa thư mục nguồn `LAB06/`. Môi trường `.venv` đã được tạo trên máy hiện tại; máy mới cần cài lại theo hướng dẫn bên dưới. Báo cáo đã điền ở [2A202603558_PhamDucHongDuc.md](../report/individual/2A202603558_PhamDucHongDuc.md); `report/individual/MSSV_HoTen.md` và `REPORT_TEMPLATE.md` được giữ làm mẫu.

## Dữ liệu đã giữ nguyên

| Vị trí trong LAB07 | Nội dung |
|---|---|
| `data/raw/` | Hai PDF gốc, tổng 71 trang vật lý |
| `data/manifest.json` | URL nguồn, quyền sử dụng, SHA-256 và cách tính trang |
| `data/processed/corpus.pages.jsonl` | 60 trang nội dung, 115.159 ký tự |
| `data/chunks/A.jsonl`, `B.jsonl`, `C.jsonl` | Chunk gốc; A 275, B/C 336; giữ ID/text/source/page/metadata |
| `data/chunks.json` | 336 chunk C theo schema Day 7: `id`, `source_id`, `source`, `page`, `text`, `metadata` |
| `results/embedding_cache/` | Cache vector thật từ Day 6, bao gồm đủ embedding document để khôi phục store |
| `configs/inherited.json`, `configs/strategies.json` | Model/store/checksum kế thừa và cấu hình chunking A/B/C |
| `src/day6/` | Code ingestion, chunking, embedding, store và dense adapter |
| `data/questions.jsonl` | 20 câu hỏi lịch sử để đối chiếu nguồn gốc benchmark và kiểm tra không dùng lại test Day 6 |
| `artifacts/ingestion.json` | Bằng chứng ingest thật, phiên bản model/store và usage kế thừa |
| `data/example/` | Ba file dữ liệu mẫu của starter, tách khỏi dữ liệu thật |

Phạm vi corpus: Luật 24/2018/QH14 trang 1–32 và Nghị định 13/2023/NĐ-CP trang 1–28. Không tính 11 trang phụ lục của Nghị định. `page` là trang vật lý PDF từ 1. OCR chưa được hiệu đính toàn bộ; khi tạo evidence cần đối chiếu PDF. Đây là snapshot văn bản gốc, không khẳng định hiệu lực pháp luật hiện tại.

Các thư mục `configs/day6/`, `artifacts/day6/` và `data/day6/` đã được bỏ sau khi chuyển các file cần giữ về vị trí trong bảng. Hai file ghi chú nguồn/benchmark cũ đã được xóa; thông tin phục vụ LAB07 được ghi ở đây, trong `data/manifest.json` và `benchmark/README.md`. Kết quả retrieval/agent LAB07 lưu riêng trong `results/retrieval/`, `results/agent/` và `results/experiments/`.

## Model và vector store

- Provider OpenAI; embedding `text-embedding-3-small`, **1536 chiều**.
- Tiền xử lý cả query và document: Unicode NFC, gộp khoảng trắng, không prefix.
- SDK ghi nhận trong lần ingest: OpenAI 2.54.0; dependency đầy đủ trong `requirements-lock.txt` và `configs/inherited.json`.
- Model sử dụng alias, không có snapshot trọng số bất biến; giữ vector và request metadata để truy vết.
- PostgreSQL 16.16, pgvector 0.8.7 theo bản ghi ingest; phiên bản live cần kiểm tra lại.
- Bảng `day6_chunks`, cosine exact search bằng `<=>`; namespace `day6-v1:text-embedding-3-small:1536:nfc-ws-v1`.
- Dense adapter dùng strategy C (336 chunk), hỗ trợ filter `doc_type` và `year` do người dùng cung cấp. B/C có cùng chunk/vector; A/B/C không được tính là ba phương pháp retrieval khác nhau.
- Docker dùng cổng `127.0.0.1:55433`, database `day6_lab`. Giữ project name `day6_student_starter` để dùng lại Docker volume cũ. Volume không nằm trong thư mục LAB06.
- `.env` cục bộ đã được chuyển nếu có ở nguồn và chưa có ở LAB07; không hiển thị/commit nội dung. Cache vector cũng được gitignore; cần giữ cục bộ hoặc tái tạo bằng embedding API thật nếu chuyển sang máy khác.

Không đổi model/số chiều rồi truy vấn index cũ. Nếu đổi model, phải xây index/namespace tương ứng và ghi chi phí. Adapter hiện từ chối cấu hình không khớp.

## Kiểm tra độc lập, không gọi API

Chạy tại thư mục gốc LAB07 bằng Python 3.11+:

```powershell
python scripts/day6_setup.py verify
python -X utf8 -m unittest discover -s tests -v
```

`verify` chỉ dùng thư viện chuẩn, kiểm tra checksum PDF/corpus/chunk, tái tạo toàn bộ A/B/C để đối chiếu ID và nội dung, kiểm tra adapter Day 7, số chiều/tính hữu hạn và checksum vector cache. Kết quả ở `results/day6-verify.json`. Việc này không chứng minh database đang chạy hay đo chất lượng agent. `-X utf8` tránh lỗi đọc tiếng Việt theo encoding mặc định Windows trong tests gốc.

## Kết nối hoặc khôi phục database

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-lock.txt
# Chỉ tạo cấu hình mẫu nếu chưa có .env; điền key tại máy khi cần gọi API.
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose -p day6_student_starter up -d --wait
.venv/Scripts/python.exe scripts/day6_setup.py check-store
```

Mở Docker Desktop trước khi chạy Compose. `check-store` chỉ đọc database để so sánh toàn bộ ID, text, nguồn, trang, metadata và số chiều của ba strategy với snapshot đã chuyển; không gọi OpenAI.

Nếu volume mới hoặc thiếu index, khôi phục bằng **vector thật đã cache**, không cần gọi API:

```powershell
.venv/Scripts/python.exe scripts/day6_setup.py restore-store
```

Lệnh này thay snapshot A/B/C trong namespace kế thừa bằng dữ liệu gốc và kiểm tra lại. Không chạy nếu bạn đang dùng chính namespace này cho dữ liệu đã chỉnh sửa cần giữ. Muốn tạo embedding lại qua API thật, dùng `python -m src.day6.run ingest` sau khi cài dependencies/cấu hình; cache hiện có được tái sử dụng. Chi phí khôi phục từ cache không phát sinh embedding API; đây không phải chi phí tạo vector ban đầu. Chi phí/usage lịch sử nằm trong `artifacts/ingestion.json`.

## Dùng dense retrieval trong LAB07

```python
from src.day6.retrieval import DenseRetriever

with DenseRetriever() as retriever:
    hits = retriever.search("Bảo vệ an ninh mạng bao gồm những hoạt động nào?", top_k=3)
```

Đây là truy vấn thật: cần database hoạt động, SDK và API key. Adapter chỉ nhận query/filter/top-k; không đọc benchmark hoặc đưa gold vào embedding/model. Mỗi hit theo schema Day 7, có `score`.

## Benchmark LAB07 đã chuẩn bị

Benchmark chính thức ở `benchmark/`: 17 dev (15 có đáp án + 2 thiếu evidence), 7 test mới (5 có đáp án + 2 thiếu evidence). Nhãn và input model nằm ở file riêng; nguồn, evidence, cách chia, tiêu chí chọn và lệnh kiểm tra được ghi trong `benchmark/README.md`. `data/questions.jsonl` giữ snapshot câu hỏi Day 6; agent không đọc file này. Kết quả đánh giá đã hoàn thành ở [phần 2](RETRIEVAL.md), [phần 3](AGENT.md) và [phần 4](EXPERIMENTS.md). Các yêu cầu chấm chính thức vẫn theo `BENCHMARK.md`.

Ngày 14/11/2026 đã kết nối và kiểm tra PostgreSQL/pgvector thật: A/B/C khớp ID, text, nguồn, metadata, số chiều với dữ liệu kế thừa; xem `results/day6-check-store.json`. Kiểm tra cosine search bằng một vector document cache cũng thành công (`results/store_smoke.json`), không chạy câu hỏi benchmark và không gọi API trong hai bước kiểm tra này. Các lượt retrieval/agent sau đó đã gọi API thật, với usage riêng trong artifacts tương ứng.

## Tái tạo text/OCR từ PDF

Luật dùng Poppler `pdftotext -layout`; Nghị định dùng Tesseract 5.5.0, model `vie` từ tessdata_fast, 200 DPI, PSM 3. Chuẩn hóa Unicode NFC và khoảng trắng, giữ số Điều/Khoản; OCR chưa được hiệu đính toàn văn. PDF gốc, nguồn, quyền sử dụng và phạm vi trang được lưu trong `data/manifest.json`.

Script `scripts/prepare_corpus.cjs` cần Node.js, Poppler và Tesseract. Đặt `POPPLER_BIN` và `TESSERACT_EXE` nếu khác đường dẫn mặc định trong script. Đặt model `vie.traineddata` của [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) vào `tmp/corpus/tessdata/`, rồi chạy `node scripts/prepare_corpus.cjs` từ root. Script không tự tải model; file trung gian ở `tmp/` được gitignore. Không chạy lại OCR lên snapshot đã chốt trong lúc benchmark; output mới có thể thay checksum, chunk và evidence.

## Đường dẫn mới và kết quả lịch sử

Các file đã chuyển vị trí được cập nhật trong code và bảng checksum kế thừa; nội dung PDF/corpus/chunk và nhãn LAB07 được giữ nguyên. Các bản ghi trong `results/` là kết quả lịch sử, giữ nguyên đường dẫn/checksum tại thời điểm chạy. Đặc biệt, `selection.json` không được ghi lại sau khi xem test. Đổi đường dẫn trong `src/day6/retrieval.py` làm checksum code khác bản chốt, nên lệnh chạy test mới bị guard từ chối; không sửa checksum lịch sử để vượt qua guard. Muốn tái lập đúng lượt test đã báo cáo, dùng phiên bản Git trước lần sắp xếp này cùng cấu trúc file cũ; việc đọc/chấm lại trace đã lưu không cần gọi API.
