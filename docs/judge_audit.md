# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có (PASS) | dùng (theo dõi tone, không dùng thay code cho tiền/approval) |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không (FAIL) | loại (không được dùng làm gate) |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & hướng sửa rubric |
|---|---|---|---|---|---|
| 1 | `H-008` (`tone`) | PASS | FAIL | Người đúng | `"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."` — Xưng hô thân mật quá mức ("em/anh", "nha", "check giúp em"). Sửa rubric: cấm xưng hô suồng sã và từ lóng/chêm tiếng Anh không chuẩn mực CSKH. |
| 2 | `H-017` (`tone`) | PASS | FAIL | Người đúng | `"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."` — Có `"Dạ"` đầu câu nên judge cho qua nhưng `"bạn ơi"`, `"rồi nha"` thiếu chuyên nghiệp. Sửa rubric: không chỉ bắt từ `"Dạ"`, phải phạt các tiểu từ/xưng hô thân mật. |
| 3 | `H-029` (`tone`) | PASS | FAIL | Người đúng | `"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."` — Câu cụt, mang sắc thái xua đuổi khách (`"không cần nhắn thêm"`). Sửa rubric: bổ sung tiêu chí thái độ tôn trọng, cấm câu đuổi khách. |
| 4 | `H-042` (`tone`) | FAIL | PASS | Người đúng | `"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."` — Lịch sự, rõ ràng, có kính ngữ (`Dạ... ạ`); judge bắt nhầm (FP). Sửa rubric: nêu rõ câu ngắn nhưng đủ thông tin và lịch sự vẫn PASS. |
| 5 | `H-051` (`tone`) | FAIL | PASS | Người đúng (ranh giới) | `"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."` — Lịch sự nhưng chêm từ `"refund"`. Sửa rubric: quy định rõ thuật ngữ `"refund"` có được chấp nhận hay bắt buộc dùng `"hoàn tiền"`. |
| 6 | `HL-015` (`helpful`) | PASS | FAIL | Người đúng | `"Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ."` — Judge bị giọng điệu lịch sự đánh lừa, bỏ qua việc thiếu thông tin giải thích/hữu ích theo ngữ cảnh. Sửa rubric: tách bạch `tone` khỏi `helpful`, yêu cầu kiểm tra đủ thông tin hành động. |
| 7 | `HL-016` (`helpful`) | PASS | FAIL | Người đúng | `"Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của..."` — Xin lỗi sáo rỗng, không giải quyết vấn đề hay nêu bước tiếp theo. Sửa rubric: câu chỉ xin lỗi mà không có hướng xử lý cụ thể phải bị đánh FAIL. |

## Kết luận
- **Tiêu chí bị loại (`helpful`) và lý do:** `judge_helpful` đạt `P = 1.0`, nhưng **`Recall = 0.3` (< 0.7)** và **`κ = 0.375` (< 0.6)** — **FAIL FLOORS**. Theo ma trận nhầm lẫn `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}`, trong 30 ca lỗi thực tế (`TP + FN = 30`), judge chỉ bắt được 9 ca và **bỏ sót 21 ca (`FN = 21`, sót 70% lỗi)** do thường bị đánh lừa bởi câu trả lời lịch sự nhưng sáo rỗng hoặc thiếu giải pháp. Hệ quả là tỷ lệ lỗi quan sát chỉ là `0.09` trong khi tỷ lệ lỗi thực tế sau hiệu chỉnh Rogan-Gladen lên tới `0.30`. Nếu dùng `judge_helpful` làm CI gate, hầu hết các regression về tính hữu ích sẽ lọt qua và tạo cảm giác an toàn giả.
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
