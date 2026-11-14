# Dữ liệu: An ninh mạng và bảo vệ dữ liệu cá nhân

Nguồn: Cổng Thông tin điện tử Chính phủ (www.chinhphu.vn). Giữ nguyên hai PDF gốc; URL tải, quyền sử dụng, ngày tải, SHA-256 và số ký tự từng trang nằm trong `manifest.json`.

| Văn bản | Trang PDF | Trang dùng | Metadata |
|---|---:|---|---|
| Luật An ninh mạng 24/2018/QH14 | 32 | 1–32 | `doc_type="Luật"`, `year=2018` |
| Nghị định 13/2023/NĐ-CP | 39 | 1–28 | `doc_type="Nghị định"`, `year=2023` |

Corpus có **60 trang nội dung**, **115.159 ký tự sau chuẩn hóa**. Loại trang 29–39 của Nghị định (phụ lục/biểu mẫu) khỏi corpus chính, vẫn giữ trong PDF gốc. Trang 28 có Điều 44 nên được tính. Không nhân bản hoặc tái phân trang. `page` là trang vật lý PDF từ 1, khác số trang Công báo in trên bản Luật.

## Các file gồm có :

- `raw/24-2018-qh14.pdf`, `raw/13-2023-nd-cp.pdf`: hai PDF gốc.
- `manifest.json`: nguồn, quyền sử dụng, trang, cách tính và metadata.
- `processed/corpus.pages.jsonl`: đầu vào pipeline, mỗi dòng có `document_id`, `source`, `page`, `page_id`, `text`, `metadata`, `char_count`.

`doc_type` là chuỗi; `year` là số nguyên, phản ánh năm ban hành. Hai trường tương quan hoàn toàn trong corpus hai văn bản, không dùng để kết luận tác động độc lập từng trường. Filter phải đến từ câu hỏi/ngữ cảnh trước truy xuất.

## Phương pháp, kiểm tra và giới hạn

- Luật: Poppler `pdftotext -layout`; chuẩn hóa Unicode NFC, khoảng trắng; giữ xuống dòng và số Điều/Khoản, loại header Công báo và dấu ký điện tử đã nhận diện.
- Nghị định: PDF scan, OCR bằng Tesseract 5.5.0, model `vie` từ tessdata_fast, 200 DPI, PSM 3. Chưa hiệu đính toàn văn; còn lỗi dấu/chữ/dấu câu và nhiễu con dấu.
- Kiểm tra mẫu ngày 13/11/2026 bởi trợ lý AI: đọc text đầu/cuối Luật; xem ảnh trang 1, 28, 29, 30, 39 của Nghị định, đối chiếu OCR trang 1, 28, 29. Xác nhận ranh giới phần chính/phụ lục. Còn lỗi như `tô chức`, `cánhân`, `Án ninh`, `thành phô`; vùng bảng/con dấu có nhiễu. Chưa hiệu đính độc lập hoặc đo tỷ lệ lỗi ký tự.
- Kiểm tra tự động: đủ 60 page ID duy nhất, không trang rỗng, không ký tự thay thế U+FFFD; SHA-256 khớp PDF. Các kiểm tra này không chứng minh OCR chính xác.

Trước khi chọn gold evidence, đối chiếu đúng trang PDF, ghi nhận sửa đổi và cố định corpus trước benchmark. Hai văn bản là bản gốc theo năm ban hành; chưa đánh giá hiệu lực pháp lý hiện tại. `effective_date_as_issued` là ngày hiệu lực ghi khi ban hành.

Quyền sử dụng văn bản quy phạm pháp luật theo khoản 2 Điều 15 Luật Sở hữu trí tuệ; liên kết căn cứ trong manifest. Ghi nguồn Cổng TTĐT Chính phủ khi sử dụng lại; không mở rộng kết luận này sang nội dung biên tập/thiết kế website.

## Tái tạo

Giữ hai PDF theo đường dẫn trong manifest; tải lại bằng `Invoke-WebRequest` với `download_url` và kiểm tra SHA-256. Script chuẩn bị dùng Node.js; pipeline bài lab vẫn cần viết bằng Python theo đề.

1. Cài Node.js, Poppler và Tesseract. Đặt `POPPLER_BIN`, `TESSERACT_EXE` nếu khác đường dẫn Windows mặc định trong script.
2. Khi OCR lại, tải https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/vie.traineddata vào `tmp/corpus/tessdata/vie.traineddata`. Model thuộc dự án tessdata_fast, [Apache-2.0](https://github.com/tesseract-ocr/tessdata_fast/blob/main/LICENSE).
3. Chạy `node scripts/prepare_corpus.cjs` từ root. Chỉ xuất manifest và corpus trong `data/`; cache OCR và file trung gian nằm trong `tmp/` đã gitignore. Script dùng lại cache nếu có, không tự tải mạng.
