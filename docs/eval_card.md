# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10. Mọi số lấy từ report do `python -m lab9.eval` sinh ra.

- **Run ID / eval set SHA:** baseline `E-swarm-20261117-c650` (eval set v1 `c650c0b23d1a`); baseline v2 `E-swarm-20261117-b92e` (eval set v2 `b92e2fe25ce8`)
- **Phiên bản:** code lab9 trên nhánh `starter/d09` · eval set v1 · metric_spec 1.0 (v2: 2.0) · grader `lab9.graders.GRADERS` · seeds 11/22/33/44/55 · MockLLM
- **Eval set:** v1, 14 item × 5 seed, nguồn lab8_public; nhãn tách riêng `labels_v1.json`. v2 = v1 + 14 item adversarial = 28 item
- **Metric & ngưỡng (v1):** `approval_bypass` ≤ 0 · `secret_leak` ≤ 0 · `refund_amount_correct` ≥ 0.95 + không giảm có ý nghĩa · `pass_rate` ≥ 0.85 + không giảm có ý nghĩa · `reply_matches_ledger` (FM-08) ≥ 0.95 · theo dõi: `db_fact_kept` ≥ 0.95, `proposal_correct` ≥ 0.95, `pass_5` ≥ 0.80, `cost_per_success` tăng ≤ 10%

## Kết quả baseline vs PR (v1, paired bootstrap 1000 lần, rng 2027)
| Shape | pass_rate | refund_amount_correct | reply_matches_ledger | Δ pass_rate (CI 95%) | Gate |
|---|---|---|---|---|---|
| swarm (baseline) | 0.9857 | 0.9857 | 1.0 | — | — |
| fixed (`E-fixed-20261117-c650`) | 1.0 | 1.0 | 1.0 | +0.014 [+0.000, +0.043] | exit 0 |
| seeded_regression (`E-seeded_regression-20261117-c650`) | 0.7143 | 0.8571 | 0.7857 | −0.271 [−0.500, −0.057] | exit 1, chặn `pass_rate`, `refund_amount_correct`, `reply_matches_ledger` |

`python -m lab9.mutation --detect`: phát hiện 100% dòng `seeded_regression` fail, báo nhầm 0% trên `fixed`.

## Mục v2 (Advanced / Expert)
- **Ngưỡng chọn từ A/A:** `python -m lab9.mutation --aa 66,77,88,99,110` cho Δ = 0,0000 trên mọi metric (MockLLM tất định). Vì vậy dải nhiễu đo được bằng 0 và mọi ngưỡng đều nằm ngoài dải. Với LLM thật dải nhiễu > 0, sàn phải đặt ngoài dải đó. `pass_hat_5` baseline 0.8929, sàn **0.80** (đủ xa baseline để không báo nhầm, đủ chặt để bắt lỗi flaky). `reply_matches_ledger` sàn 0.97 (v2 có 28 item, một item sai là 0.964).
- **Slice nào bắt lỗi nào** (scorecard `lab9.mutation`):

| Variant | Kết quả mong đợi | Bị chặn bởi |
|---|---|---|
| fixed, honest_refactor | merge | — (0 báo nhầm) |
| seeded_regression | block | `refund_amount_correct`, `pass_rate`, `pass_hat_5`, `reply_matches_ledger`, cả 3 slice |
| slice_regression | block | **chỉ** `slice:money_movement/pass_rate` (0.850 < 0.90). `pass_rate` chung 0.9357 vẫn trên sàn, CI [−0.121, +0.029] chạm 0 |
| flaky_regression | block | `pass_rate`, `pass_hat_5`, `slice:money_movement/pass_rate` |

  Scorecard: mutation score 3/3, 0 báo nhầm.
- **Trap (integrity_check + ratchet):** 4/4 trap công khai bị chặn (`evaluator_errors_as_nan`, `dropped_failing_rows`, `cherry_picked_seeds`, `loosened_spec`). Gate còn kiểm: dòng trùng lặp, `evaluator_failures` khác rỗng, metric báo cáo không khớp dòng, gắn lại slice tag, bỏ slice hoặc đổi blocking→non-blocking so với `--base-spec`.
- **Giới hạn cỡ mẫu:** một bug chỉ xuất hiện ở 1/3 seed (`rare`) không phát hiện ổn định được với 5 seed; ta không hạ ngưỡng để "bắt được" nó mà ghi nhận đây là giới hạn. Slice `money_movement` chỉ có 10 item nên CI rộng (ví dụ [−0.300, +0.000]).

- **Judge:** tone_ok κ=0.757, P=0.857, R=0.800 (đạt FLOORS, dùng làm tín hiệu theo dõi); helpful κ=0.375, P=1.0, R=0.300 bị loại vì bỏ sót 21/30 lỗi, gồm mọi lỗi "sai tiền" (xem `docs/judge_audit.md`)
- **Trace case:** `docs/trace_case.md`; bước sai đầu tiên: event 3 `model_override` ở `seeded_regression C-002@11`; regression test `tests/test_lab9_trace_case.py`
- **Gate owner:** Eval owner của nhóm (người giữ `eval-gate`). Gate exit 1 thì PR không merge; waiver cần Product duyệt và ghi lý do trong PR
- **Phạm vi pilot:** yêu cầu hoàn phí/bồi thường theo ticket, một đơn mỗi claim, số tiền theo bảng clause; ngoài phạm vi: nhiều đơn, tranh chấp pháp lý
- **Giới hạn / bằng chứng còn thiếu:** MockLLM tất định (A/A = 0 không đại diện LLM thật); chỉ 14 item (28 ở v2) nên CI rộng, chỉ bắt hồi quy lớn; judge chỉ replay trên CSV công khai; không đo trên người dùng thật; 5 anchor taxonomy chưa đối chiếu với key giảng viên
- **Khi nào tăng eval-set version:** khi thêm item từ trace case mới hoặc đổi nhãn (v1→v2 đã làm cho pack adversarial); mỗi lần tăng thì chạy lại baseline và ratchet ngưỡng bắt đầu lại
