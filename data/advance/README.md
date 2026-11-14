# Tài liệu phần nâng cao

Nguồn là **GPT-4 Technical Report, arXiv:2303.08774v6**, bản ngày 04/03/2024, 100 trang vật lý, bao gồm Technical Report, phụ lục và System Card. [Trang nguồn](https://arxiv.org/abs/2303.08774v6), [PDF đúng phiên bản](https://arxiv.org/pdf/2303.08774v6). SHA-256 của PDF do học viên cung cấp: `c33a66dadca2388d7b172d6293b00dc32b71110c6f38fafe0d41112e61be7774`.

## File hiện có

| Vị trí | Nội dung |
|---|---|
| `2303.08774v6.pdf` | PDF gốc do học viên cung cấp |
| `pages/page-001.jpg` đến `page-100.jpg` | Ảnh toàn trang 110 DPI từ Poppler; số trang vật lý từ 1 |
| `captions/001.json` đến `100.json` | Mô tả vision, vùng ước lượng, uncertainty, model/request ID và usage từng trang |
| `index.json` | Text layout từ PDF và mô tả trực quan cho toàn bộ 100 trang, giữ liên kết ảnh gốc |
| `vectors.json` | Vector store JSON local riêng, 100 vector thật 1536 chiều; tìm exact cosine |
| `manifest.json` | Phiên bản, nguồn, quyền, coverage, checksum, model và usage tạo mô tả |

Không chọn trang dựa trên benchmark. Cả trang ít text, trang chỉ có hình, mục lục, tài liệu tham khảo và bìa phụ lục đều nằm trong index. Mô tả ảnh được tạo trước benchmark; không chứa câu hỏi/đáp án benchmark. Bảng và biểu đồ được đọc trong ảnh toàn trang; bounding box vùng do model ước lượng, không phải segmentation đã xác nhận. Khi trả lời, ảnh PDF gốc có ưu tiên hơn text trích xuất/mô tả tự động.

Embedding dùng `text-embedding-3-small`, 1536 chiều, cả query/document cùng thay delimiter ChatML in trong tài liệu thành text thông thường rồi NFC + gộp whitespace. Text/bằng chứng gốc không bị sửa. Vector store này tách khỏi pgvector Day 6; không đưa vector model khác vào index cũ. `results/advanced/embedding-build.json` lưu checksum, số request/token và chi phí embedding.

## Quyền sử dụng và chia sẻ

Trang arXiv ghi [non-exclusive distribution license](https://arxiv.org/licenses/nonexclusive-distrib/1.0/license.html); không suy ra quyền tái phát hành toàn bộ tài liệu hoặc ảnh bên thứ ba. Giữ PDF và các bản sao toàn văn/ảnh/caption/vector cục bộ, đã thêm vào `.gitignore`. Repo có URL nguồn, checksum, metadata và code tái tạo; người chấm có thể tải bản gốc. Khi giao bản cache/trace có toàn văn, cần kênh chia sẻ được phép cho người chấm; không tự động đưa chúng lên repo công khai.

## Tái tạo

Từ root LAB07, đặt PDF tại đúng vị trí, cài dependencies đã có và cấu hình API key trong `.env` local. Cần Poppler `pdftoppm` trên PATH; trên máy hiện tại có `C:/poppler-24.08.0/Library/bin/pdftoppm.exe`.

```powershell
New-Item -ItemType Directory -Force data/advance/pages | Out-Null
pdftoppm -r 110 -jpeg -jpegopt quality=86 data/advance/2303.08774v6.pdf data/advance/pages/page
.venv/Scripts/python.exe -X utf8 -m src.advanced.prepare
.venv/Scripts/python.exe -X utf8 -m src.advanced.retrieval
.venv/Scripts/python.exe -X utf8 -m src.advanced.benchmark
```

`prepare` tái sử dụng caption có cùng PDF/image/model/prompt checksum. Tạo caption và embedding mới gọi API thật và phát sinh phí. Không ghi đè vector/index đã chốt khi tái lập benchmark; dùng bản sao thư mục cho một phiên bản mới. Model alias/caption generation có thể thay đổi theo thời gian; cache và checksum của lượt gốc là căn cứ đối chiếu. Có lỗi mạng trong các lượt chuẩn bị; usage trả về được lưu, retry không có usage không được giả thành chi phí bằng 0.
