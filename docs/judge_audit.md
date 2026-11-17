# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5` (replay, n=100 mỗi tiêu chí; FAIL là lớp dương).

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt cả ba (TP 24, FP 4, FN 6, TN 66) | **dùng** |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt κ và recall (TP 9, FP 0, FN 21, TN 70) | **loại** |

Tỉ lệ lỗi tone: quan sát 0.28, hiệu chỉnh Rogan-Gladen 0.30. Tỉ lệ lỗi helpful: quan sát 0.09 nhưng hiệu chỉnh 0.30, tức judge bỏ sót hơn hai phần ba lỗi.

## ≥5 case audit thủ công (tone_ok)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / hành động sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha…" | PASS | FAIL | Người | Xưng "em" + "nha" quá suồng sã. Rubric thêm: cấm "nha/nhé" và đại từ thân mật khi khiếu nại |
| 2 | H-029 "…không cần nhắn thêm." | PASS | FAIL | Người | Giọng ra lệnh; judge chỉ thấy "Dạ, vui lòng". Rubric thêm: câu mệnh lệnh phủ định với khách là FAIL |
| 3 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ…" | FAIL | PASS | Người | Ngắn nhưng đủ ý; judge phạt "thiếu xin lỗi". Rubric: xin lỗi chỉ bắt buộc khi trả lời từ chối |
| 4 | H-051 "…đã refund 90.000đ…" | FAIL | PASS | Người | CS LogiX cho phép từ "refund". Rubric: thêm danh sách thuật ngữ được phép |
| 5 | H-063 "…và sẽ hoàn thêm cho anh/chị ạ." | PASS | FAIL | Người | Hứa ngoài kết quả hệ thống. Nên chuyển sang code grader kiểm so với ledger |
| 6 | H-081 "…chưa đủ điều kiện hoàn…" | FAIL | PASS | **Judge** | Nhãn người sai (đọc nhầm ticket); sửa nhãn trong tập calibration, không sửa judge |
| 7 | H-070 "…ạ 😂😂" | PASS | FAIL | Người | Emoji không hợp ngữ cảnh khiếu nại. Rubric thêm: cấm emoji |

Mẫu chung: judge dễ tha lỗi **thân mật / ra lệnh** (6 trong 10 bất đồng là FN) và hơi khắt khe về **hình thức** (typo, tiếng Anh).

## Kết luận
- **helpful bị loại**: recall 0.30 (<0.70) và κ 0.375 (<0.60). Confusion matrix cho thấy 21/30 lỗi bị bỏ sót, trong đó các lỗi "sai tiền" (reply nói 55.000đ trong khi ledger 40.000đ…) đều được judge cho PASS vì câu trả lời nghe lịch sự. Precision 1.0 đánh lừa: judge hiếm khi báo nhầm nhưng gần như không phát hiện lỗi. Làm gate sẽ bỏ lọt hầu hết regression. Số tiền phải do code chấm (`reply_matches_ledger`, FM-08), không do judge.
- **tone_ok dùng được** làm tín hiệu theo dõi, không phải gate tiền/approval. Sau khi sửa rubric theo bảng trên cần calibrate lại trên nhãn mới.
- Rủi ro còn lại: judge chỉ kiểm trên dữ liệu replay công khai; cần nhãn người mới để có held-out thật. Rogan-Gladen giả định sens/spec ổn định giữa các phân phối.
