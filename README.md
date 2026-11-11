# Vị Trà — Web đặt nước QR

## Chức năng
- Khách quét một QR chung, xem menu, thêm món vào giỏ, đặt nhận tại quán hoặc giao tận nơi.
- Thanh toán tiền mặt hoặc chuyển khoản (chỉ ghi nhận lựa chọn, **chưa tự xác minh thanh toán**).
- Trang nhân viên `/ ?page=admin` (bỏ dấu cách), đăng nhập bằng mật khẩu, xem và đổi trạng thái đơn.
- Dữ liệu đơn hàng lưu Google Sheets khi cấu hình; nếu không, lưu SQLite trên máy chạy để thử nghiệm. **SQLite trên Streamlit Cloud không bền vững**, không dùng cho đơn hàng thật.

## Bước 1 — Thiết lập menu
Mở `menu.csv`, nhập `price` (VND) cho từng món; món chưa có giá sẽ bị ẩn. `available=1` là bán, `0` là ẩn. Menu được lấy từ file công thức Vị Trà nhưng **không có giá bán**, nên chưa có món nào có thể đặt trước khi cập nhật giá.

## Bước 2 — Google Sheets
1. Tạo Google Sheet mới, sao chép ID trong URL.
2. Tạo Google Cloud service account, bật Google Sheets API và Google Drive API, tạo khóa JSON.
3. Chia sẻ Google Sheet với email `client_email` của service account, quyền Editor.
4. Điền `GOOGLE_SHEET_ID`, `ADMIN_PASSWORD` và các trường khóa JSON vào Streamlit Secrets theo mẫu `.streamlit/secrets.toml.example`.
5. Ứng dụng sẽ tự tạo tab `Orders` nếu chưa có.
**Không đưa khóa JSON hoặc mật khẩu lên GitHub.**

## Bước 3 — Chạy thử
```bash
pip install -r requirements.txt
streamlit run app.py
```
Trang khách: `http://localhost:8501`
Trang nhân viên: `http://localhost:8501/?page=admin`

## Bước 4 — Đưa lên internet
1. Tạo repo GitHub và upload `app.py`, `menu.csv`, `requirements.txt`, `.streamlit/secrets.toml.example`, `README.md`.
2. Vào https://share.streamlit.io/ và tạo ứng dụng từ repo, file chạy `app.py`.
3. Trong Advanced settings > Secrets, nhập cấu hình thực tế.
4. Lấy URL công khai (ví dụ `https://ten-app.streamlit.app/`), tạo mã QR trỏ tới URL đó và in dùng chung.
5. Trang quản trị dùng URL công khai cộng `?page=admin`; không in URL này lên QR khách.

## Lưu ý vận hành
- Đơn giao hàng hiện **chưa tính phí giao tự động**. Giá hiển thị là tạm tính, quán xác nhận phí giao.
- Chuyển khoản **chưa tích hợp VietQR/đối soát ngân hàng**; khách đợi quán xác nhận số tiền.
- Đơn mới chỉ xuất hiện khi nhân viên mở/làm mới trang quản trị, chưa có push notification.
- Đặt thử nhiều đơn trước khi mở cho khách thật; đảm bảo Google Sheet đã kết nối.
- Dữ liệu cá nhân khách (tên, SĐT, địa chỉ) cần giới hạn quyền truy cập vào Sheet.
