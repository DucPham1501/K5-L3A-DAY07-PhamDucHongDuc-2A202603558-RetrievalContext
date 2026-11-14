# Kiểm thử code LAB07

Chạy từ thư mục gốc:

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v
```

| File | Phạm vi |
|---|---|
| `test_retrieval.py` | BM25, RRF, filter, context, lỗi và đối chiếu evidence |
| `test_benchmark.py` | Tách input khỏi gold và kiểm tra dữ liệu đầu vào |
| `test_real_agent.py` | Agent thực tế: tool, context, citation, điều kiện dừng, chi phí và khóa test |
| `test_agent_metrics.py` | Bộ tổng hợp điểm vẫn được `src/agent_review.py` sử dụng |
| `test_advanced.py` | Metadata ảnh đúng trang, context, input không gold, tokenizer và chấm từ chối theo nội dung |

Đã bỏ ba file chỉ kiểm tra starter/data mẫu: `test_baseline.py`, `test_agentic.py`, `test_fixture.py`. Code starter được giữ để tham khảo. Các con số 27/38/43 tests trong báo cáo cũ là số kiểm thử ở thời điểm các lượt đó được thực hiện; không sửa lại số liệu lịch sử khi dọn file.

Unit tests dùng mock/fixture để kiểm tra logic, không gọi API hoặc chứng minh chất lượng câu trả lời. Benchmark agent thật, trace, nhãn và chi phí nằm riêng trong `results/`; giữ cả các lượt lỗi để đối chiếu và tái lập.
