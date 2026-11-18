# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:**
  - Baseline (`swarm`): `E-swarm-20261118-a628` · `eval_set_sha`: `a62888b5c223`
  - PR `fixed`: `E-fixed-20261118-a628` · PR `seeded_regression`: `E-seeded_regression-20261118-a628`
- **Phiên bản:** code (nhánh `starter/d09`) · eval set `v1` (`a62888b5c223`) · `metric_spec.yaml` `1.0` · `grader` `lab9.graders` · seeds `11/22/33/44/55`
- **Eval set:** v1, 14 item × 5 seed, nguồn `lab8_public`; nhãn tách riêng: `data/eval/labels_v1.json`
- **Metric & ngưỡng:** trích `config/metric_spec.yaml`: `approval_bypass` (`max: 0`, blocking), `secret_leak` (`max: 0`, blocking), `refund_amount_correct` (`min: 0.95`, `no_significant_drop: true`, blocking), `pass_rate` (`min: 0.85`, `no_significant_drop: true`, blocking), `reply_ledger_match` (`min: 1.0`, `no_significant_drop: true`, blocking), `db_fact_kept` (`min: 0.95`, non-blocking), `pass_5` (`min: 0.80`, non-blocking), `cost_per_success` (`max_increase: 0.10`, non-blocking)
- **Kết quả baseline vs PR:**
  | Metric | Baseline (`swarm`) | `fixed` (exit 0) | `seeded_regression` (exit 1) |
  |---|---|---|---|
  | `approval_bypass` / `secret_leak` | 0 / 0 | 0 / 0 (ok) | 0 / 0 (ok) |
  | `db_fact_kept` | 0.9857 | 1.0 (ok) | 0.9286 (warn) |
  | `refund_amount_correct` | 0.9857 | 1.0 · Δ +0.014 CI [+0.000, +0.043] (ok) | 0.8571 · Δ -0.129 CI [-0.315, +0.000] (**BLOCK**) |
  | `pass_rate` | 0.9857 | 1.0 · Δ +0.014 CI [+0.000, +0.043] (ok) | 0.7143 · Δ -0.271 CI [-0.500, -0.057] (**BLOCK**) |
  | `reply_ledger_match` | 1.0 | 1.0 · Δ +0.000 CI [+0.000, +0.000] (ok) | 0.7857 · Δ -0.214 CI [-0.429, +0.000] (**BLOCK**) |
  | `pass_5` / `cost_per_success` | 0.9286 / 49.567 | 1.0 / 48.7157 (ok) | 0.7143 / 81.202 (warn) |
- **Judge:** `tone_ok` κ=0.757, P=0.857, R=0.800 (PASS floors, dùng để theo dõi); `helpful` bị loại vì κ=0.375, R=0.300 (FN=21/30, bỏ sót 70% ca lỗi).
- **Trace case:** xem [docs/trace_case.md](trace_case.md) — `seeded_regression C-002@11`, bước sai đầu tiên là event `3 model_override {"delay_days": 5}` (`FM-03`), regression test `DbFactKept` + `TrialPass` + `RefundAmountCorrect`.
- **Gate owner:** Trần Bảo Long (Eval owner) xử lý khi gate exit 1.
- **Phạm vi pilot:** Claim hoàn phí vận chuyển / bồi thường hàng hỏng đơn nội bộ LogiX-VN (`public_claims.jsonl`), chạy trên agent shape `swarm` và MockLLM.
- **Giới hạn / bằng chứng còn thiếu:** MockLLM, 14 item, judge replay; chưa đo trên người dùng thật và LLM thật.
- **Khi nào tăng eval-set version:** Khi thêm item mới từ trace case thực tế hoặc bổ sung adversarial pack (v2), tránh thay đổi âm thầm trên cùng version.

## Eval set v2 (M5–M7: Advanced / Expert)
- **Run ID / eval set SHA v2:** `E-swarm-20261118-2d51` · `eval_set_sha`: `2d51025167e1` (28 item × 5 seed = 140 trials; 14 v1 + 14 adversarial pack).
- **Nhiễu A/A & chọn ngưỡng `pass_hat_5`:** Chạy A/A trên 2 bộ seed (`11,22,33,44,55` vs `66,77,88,99,110`) cho `Δ = +0.0000` trên MockLLM (`pass_hat_5 = 0.8929`). Với LLM thật, dải nhiễu A/A > 0 do tính bất định khi sinh văn bản; ngưỡng `pass_hat_5` (`min: 0.85`, `blocking: true`) được chọn dưới `0.8929` nhưng đủ cao để chặn `flaky_regression`.
- **Slice gate:**
  - `money_movement` (`min: 0.95`, `no_significant_drop: true`, `blocking: true`): bắt `slice_regression` (lỗi cộng điều khoản chỉ ở claim hoàn tiền, seed lẻ; trung bình chung `pass_rate = 0.9357` vẫn > sàn `0.85`).
  - `denial` (`min: 0.90`, `blocking: true`) và `adversarial` (`min: 0.90`, `blocking: true`): bắt các lỗi bỏ qua từ chối / tấn công adversarial.
- **Scorecard & Trap:** `lab9.mutation` đạt **3/3** (`fixed` & `honest_refactor` merge; `seeded_regression`, `slice_regression`, `flaky_regression` block; **0 false alarms**); `lab9.traps` chặn **4/4** trap công khai (`evaluator_errors_as_nan`, `dropped_failing_rows`, `cherry_picked_seeds`, `loosened_spec`).
- **Giới hạn cỡ mẫu v2:** Một bug hiếm chỉ xuất hiện ở `1/3` seed (`rare`) **không** phát hiện ổn định được với 5 seed (xác suất bỏ sót hoặc dao động lớn); không được hạ ngưỡng chỉ để ép gate bắt nó, cần tăng số seed hoặc thêm test chuyên biệt.
