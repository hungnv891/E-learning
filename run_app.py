import os

# Tên file ứng dụng của bạn
app_file = "app.py"

# Kiểm tra và chạy Streamlit
if os.path.exists(app_file):
    os.system(f"streamlit run {app_file}")
else:
    print(f"⚠️ Không tìm thấy file {app_file}. Đảm bảo file nằm cùng thư mục với run_app.py")
