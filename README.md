# Homework 1 - N-Queens

Bài tập lớn số 1, môn Các vấn đề hiện đại KHMT, học kỳ I 2026-2027.

Giải bài toán đặt `n` quân hậu trên bàn cờ `n × n`, không có hai quân hậu cùng hàng,
cột hoặc đường chéo. So sánh SAT với **CPLEX CP Optimizer, CPLEX MIP, Gurobi, OR-Tools CP-SAT**.

## Nội dung

- `nqueens/`: mô hình SAT/CP/ILP, kiểm tra nghiệm, xuất DIMACS và chạy thực nghiệm.
- `tests/`: kiểm tra đầy đủ nghiệm đến n=8; bảng chân trị AMO; kiểm tra các solver.
- Kiểm tra unit propagation riêng cho AMO đến 64 đầu vào, không gọi SAT search.
- `results/`: CSV, cấu hình thực nghiệm, JSONL lưu nghiệm thực và tổng hợp.
- `report/main.tex`, `report/main.pdf`: báo cáo theo mẫu Elsevier `cas-sc`.
- `report/tables/`, `report/figs/`: bảng và hình sinh trực tiếp từ kết quả.
- `reproduce.ps1`: chạy lại toàn bộ kiểm tra và thực nghiệm trên Windows.

## Cài đặt

Python 3.12 trở lên; môi trường thực nghiệm sử dụng Python 3.14.5 trên Windows 11.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Để khớp đúng phiên bản của thực nghiệm đã nộp, dùng `requirements-lock.txt`
thay cho `requirements.txt` (nếu các phiên bản này hỗ trợ Python của bạn).

CPLEX MIP cần gói `cplex` có quyền giải mô hình lớn; CPLEX CP cần cài **CPLEX
Optimization Studio**. Chương trình tự tìm CP Optimizer trong `C:/Program Files/IBM/ILOG`.
Nếu cài ở đường dẫn khác:

```powershell
$env:CPO_EXECUTABLE='C:\path\to\cpoptimizer.exe'
```

Gurobi tự tìm `gurobi.lic` trong thư mục project hoặc thư mục cha. Có thể chỉ định:

```powershell
$env:GRB_LICENSE_FILE='C:\path\to\gurobi.lic'
```

License WLS cần mạng. License không được lưu trong Git hoặc gói nộp bài.

## Giải một bàn cờ

Chạy các lệnh từ thư mục repository:

```powershell
python -m nqueens.run_one 8
python -m nqueens.run_one 128 sat:cadical195:commander:minimal --time-limit 60
python -m nqueens.run_one 64 cplex_cp --time-limit 60
python -m nqueens.run_one 64 cplex_mip --time-limit 60
python -m nqueens.run_one 64 gurobi --time-limit 60
python -m nqueens.run_one 64 cpsat --time-limit 60
python -m nqueens.run_one 8 sat:cadical195:product:extended --dimacs queens.cnf
```

Kết quả JSON chứa `status`, `solution`, kích thước mô hình và các thời gian.
`solution[r]` là **cột từ 0** của quân hậu ở hàng `r` (hàng cũng từ 0).
`valid=true` có nghĩa nghiệm đã được bộ kiểm tra độc lập chấp nhận.
`TIMEOUT` không có nghĩa vô nghiệm. Mọi lần giải qua CLI đều có giới hạn thời gian toàn
bộ tiến trình, gồm khởi động, nhập thư viện, lấy license, xây dựng mô hình và giải.

SAT có 5 mã hóa AMO: `pairwise`, `binary`, `commander`, `product`, `seqcounter`.
`minimal`: đúng một hậu mỗi hàng; nhiều nhất một hậu mỗi cột/đường chéo.
`extended`: thêm mệnh đề ít nhất một hậu mỗi cột. Hai cách có cùng tập nghiệm.

## Kiểm tra và tái lập kết quả

Kiểm tra lại số liệu đã nộp (không chạy lại benchmark):

```powershell
python -m unittest discover -v
$env:NQUEENS_INTEGRATION='1'
python -m unittest tests.test_models.ModelTests.test_exact_backends -v
python -m nqueens.analyze
python -m nqueens.report_details
```

Số liệu trong `results/` là một lần chạy rút gọn (124 lần, giới hạn 180 s, 1 lần lặp:
`python -m nqueens.benchmark --time-limit 180 --repeats 1`) trên máy dùng chung.

Chạy lại toàn bộ thực nghiệm (372 lần chạy, giới hạn 600 s mỗi lần; có thể mất
nhiều giờ vì các lần timeout chiếm trọn giới hạn):

```powershell
.\reproduce.ps1                      # ghi vào results-new\ và results-new\report\
.\reproduce.ps1 -Results results-pc2 # hoặc thư mục khác
```

`reproduce.ps1` không ghi đè `results/` và `report/` đã nộp.

| Thực nghiệm | Phương pháp | Kích thước n |
|---|---|---|
| `encodings` | CaDiCaL × 5 AMO × {minimal, extended} | 8, 16, 32, 64, 128, 256 |
| `solvers` | CaDiCaL, Glucose, MiniSat, MapleChrono với commander/minimal | 8, 16, 32, 64, 128, 256 |
| `exact` | SAT đối chiếu, CPLEX CP, CPLEX MIP, Gurobi, CP-SAT | 8, 16, 32, 64, 128, 256 |
| `scaling` | như `exact` | 512, 1024 |

Cấu hình SAT đối chiếu là `sat:cadical195:commander:minimal`.
Giới hạn thời gian có thể đổi bằng `python -m nqueens.benchmark --time-limit 60`.

Chạy tuần tự để các solver không tranh chấp CPU. Mỗi kích thước có 3 lần lặp;
các phương pháp CP/MIP dùng seed 1, 2, 3, một luồng. SAT dùng tham số mặc định
của backend và chạy lại trong tiến trình mới; các lần lặp chủ yếu đo biến động thời gian.
Không dùng phá đối xứng hoặc nghiệm gợi ý cho bất kỳ solver nào.

`nqueens.benchmark` ghi `source-sha256.json` (SHA-256 của các file mã đo đạc,
chuẩn hóa xuống dòng LF) cạnh kết quả, để đối chiếu số liệu với đúng phiên bản mã.
`nqueens.analyze` sinh bảng, hình, `summary.json` và `report/numbers.tex`
(mọi con số trong báo cáo được lấy qua macro `\res{...}` từ file này).
`nqueens.report_details` kiểm tra công thức đếm biến/mệnh đề theo cài đặt,
sinh hình kích thước CNF và bảng tách thời gian dựng/giải. Hai lệnh này
không chạy lại benchmark.

CSV cho phép tiếp tục lần chạy bị gián đoạn nếu cấu hình khớp. Để thực nghiệm khác,
dùng `--results results-new` (cho cả `nqueens.experiment` và `nqueens.benchmark`);
không ghi đè số liệu đã nộp. File `.lock` ngăn hai lần
chạy cùng thực nghiệm. Chỉ xóa lock nếu tiến trình được ghi trong file đã dừng.

Thời gian `process_time` đo toàn bộ tiến trình con. `total_time` là xây dựng cộng
giải mô hình; Gurobi tách lấy license vào `setup_time`. Báo cáo trình bày cả hai
để làm rõ ảnh hưởng khởi động và license. PAR-2 tính 2 lần giới hạn cho timeout/lỗi,
không bỏ các lần không giải được khỏi trung bình.

## Biên dịch báo cáo

Cần TeX có lớp Elsevier `cas-sc`, `natbib` và BibTeX:

```powershell
Set-Location report
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Phạm vi là N-queens tiêu chuẩn: tìm một nghiệm. Không phải bài toán đếm nghiệm
hoặc N-queens completion có các quân hậu đặt sẵn; không suy rộng các kết quả hiệu năng
ở đây thành kết luận cho các bài toán NP-complete nói chung.
