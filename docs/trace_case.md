# Trace case: từ trace tới quyết định sai đầu tiên

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, trong report `E-seeded_regression-20261117-c650` (`reports/eval_seeded_regression.json`) |
| Triệu chứng | Lab 8 grader FAIL (`status resolved != denied`). Ledger ghi 20.000đ, 1 refund; nhãn là 0đ, `denied`. Reply "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202." trôi chảy nên nhìn không ra lỗi |
| Bước sai đầu tiên | Event 3 `model_override {"delay_days": 5}`: agent ghi đè `delay_days` của DB bằng số ngày trong ticket |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` và event 2 `investigator` đúng: `lookup_order` trả đơn O-202 hiển thị được, DB ghi `delay_days = 2` (ticket nói 5) nên chưa đủ điều kiện. Từ event 3 trở đi mọi bước đều đúng trên dữ liệu đã bị ghi đè: event 4 `quote` ra 20.000đ (`SHIP-LATE-03`), rồi host hoàn tiền thật |
| Failure mode | FM-03 ticket_trust (`docs/failure_taxonomy.md`) |
| Đối chứng | `fixed C-002@11`: không có event `model_override`; event 3 `quote` ra `amount_vnd=0, reason=no_entitlement`; status `denied`, ledger 0 |
| Regression test | `tests/test_lab9_trace_case.py::test_seeded_regression_c002_is_caught_and_fixed_is_clean`: khẳng định `model_override` ở vị trí thứ 3, `RefundAmountCorrect` và `DbFactKept` fail trên `seeded_regression`, pass trên `fixed`. Đã thấy fail trên biến thể lỗi và pass trên `fixed` |
| Chưa chắc chắn | Trace không cho biết vì sao MockLLM chọn tin ticket (ở `swarm` đó là điểm yếu cố định `seed % 5 == 0`); chưa kiểm tra trên LLM thật |
