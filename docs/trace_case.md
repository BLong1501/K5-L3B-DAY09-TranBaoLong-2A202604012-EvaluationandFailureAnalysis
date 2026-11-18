# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case đã phân tích (`seeded_regression C-002@11`)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (đối chứng với `fixed C-002@11`) |
| Triệu chứng | `lab8 grader: FAIL (status resolved != denied)`; reply nói `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."`, ledger ghi `refund_vnd=20000`, `refund_count=1` (trong khi label `refund_vnd=0`, `refund_count=0`, `status=denied`). |
| Bước sai đầu tiên | Event `3 model_override {"delay_days": 5}` — agent tin số ngày trễ `5` trong ticket thay vì dữ liệu DB của đơn `O-202`. |
| Vì sao là bước *đầu tiên* | Event `1 handoff` cấp đúng `allowed_tools` (`lookup_order`, `lookup_policy`, `compute_compensation`) cho `REQ-C-002`; event `2 investigator` gọi `lookup_order` trả về `visible: true, reason: "ok"` cho `O-202` đúng sự thật trong DB. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) trong `docs/failure_taxonomy.md` |
| Đối chứng | Trên `fixed C-002@11`, không có event `model_override`: sau event `2 investigator`, event `3 quote` trả `{"amount_vnd": 0, "reason": "no_entitlement", "clause_ids": [], "parts": {}}`, event `4 reply` từ chối đúng chính sách, ledger `0đ`, `lab8 grader: PASS (ok)`. |
| Regression test | `DbFactKept` (`db_fact_kept`, bắt event `model_override`) và `TrialPass` (`pass_rate`) trên item `E-002` (`C-002`) trong `eval_set_v1.jsonl`; fail trên `seeded_regression C-002@11`, pass trên `fixed C-002@11` (và sẽ được kiểm tra qua CI gate ở M3–M4 cùng `RefundAmountCorrect`). |
| Chưa chắc chắn | Trace không ghi lại `delay_days` gốc trong payload bị cắt ngắn của `investigator` nếu chỉ nhìn `trace_case`, và trên LLM thật (không phải MockLLM) lỗi `ticket_trust` có thể xảy ra mà không tự phát event `model_override`. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
