#!/usr/bin/env python3
import sys
import os
import subprocess
import argparse
import time
import io
import traceback

# Thiết lập môi trường Unicode cho Windows
if sys.platform == 'win32':
    # Thiết lập mã hóa cho stdout/stderr
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    # Thiết lập biến môi trường cho Python
    os.environ["PYTHONIOENCODING"] = "utf-8"
    # Thiết lập code page cho cmd
    os.system("chcp 65001 > nul")

# Đảm bảo các thư mục tồn tại
for dir_name in ['screenshots', 'reports', 'test_data']:
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

def install_dependencies():
    """Cài đặt các thư viện cần thiết"""
    try:
        # Kiểm tra các thư viện quan trọng
        import pytest
        import pytest_asyncio
        import pytest_html
        import playwright
        import tkinter
        import pandas as pd
        import matplotlib
        print("Các thư viện đã được cài đặt.")
        return True
    except ImportError as e:
        missing_lib = str(e).split("'")[1]
        print(f"Thiếu thư viện: {missing_lib}")
        print("Đang cài đặt các thư viện cần thiết...")
        
        try:
            # Cài đặt các thư viện cơ bản
            subprocess.call([
    sys.executable, "-m", "pytest", 
    "lazada_test.py::TestLazada", "-v",  # Chỉ định class TestLazada
    "--html=reports/lazada_test_report.html",
    "--self-contained-html"
            ])
            
            # Cài đặt Playwright browsers
            print("Cài đặt trình duyệt cho Playwright...")
            subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
            print("Đã cài đặt các thư viện cần thiết.")
            return True
        except Exception as e:
            print(f"Lỗi khi cài đặt thư viện: {str(e)}")
            return False

def start_splash_screen():
    """Hiển thị màn hình khởi động (chỉ cho Windows và hỗ trợ tkinter)"""
    try:
        import tkinter as tk
        from tkinter import ttk
        
        splash = tk.Tk()
        splash.overrideredirect(True)  # Không có khung cửa sổ
        
        # Đặt cửa sổ vào giữa màn hình
        width = 400
        height = 200
        screen_width = splash.winfo_screenwidth()
        screen_height = splash.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        splash.geometry(f"{width}x{height}+{x}+{y}")
        
        # Tạo frame chính
        frame = ttk.Frame(splash, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Tiêu đề
        ttk.Label(frame, text="Công cụ Kiểm thử Lazada", 
                 font=("Arial", 16, "bold")).pack(pady=(10, 20))
        
        # Thông báo
        ttk.Label(frame, text="Đang khởi động...").pack()
        
        # Thanh tiến trình
        progress = ttk.Progressbar(frame, mode="indeterminate", length=300)
        progress.pack(pady=20)
        progress.start()
        
        # Cập nhật giao diện và đợi 2 giây
        splash.update()
        return splash
    except Exception as e:
        print(f"Không thể tạo splash screen: {e}")
        return None

def close_splash_screen(splash):
    """Đóng màn hình khởi động"""
    if splash:
        try:
            splash.destroy()
        except:
            pass

def run_with_gui():
    """Chạy với giao diện GUI"""
    print("\n" + "="*80)
    print("KHỞI ĐỘNG CÔNG CỤ KIỂM THỬ LAZADA WEBSITE VỚI GUI")
    print("="*80 + "\n")
    
    # Hiển thị splash screen
    splash = start_splash_screen()
    
    try:
        print("Đang kiểm tra módule GUI...")
        # Kiểm tra module GUI
        try:
            from lazada_test_gui import main as gui_main
            print("Module GUI đã sẵn sàng.")
        except ImportError as e:
            print(f"Lỗi khi import module GUI: {str(e)}")
            if splash:
                close_splash_screen(splash)
            print("Chuyển sang chế độ dòng lệnh.")
            run_command_line()
            return
            
        # Đóng splash screen sau 2 giây và khởi chạy GUI
        if splash:
            def start_main():
                try:
                    close_splash_screen(splash)
                    gui_main()
                except Exception as e:
                    print(f"Lỗi khi chạy GUI: {str(e)}")
                    traceback.print_exc()
                    print("Chuyển sang chế độ dòng lệnh.")
                    run_command_line()
            
            splash.after(2000, start_main)
            splash.mainloop()
        else:
            # Chạy trực tiếp nếu không có splash
            gui_main()
    except Exception as e:
        # Đóng splash screen nếu có lỗi
        if splash:
            close_splash_screen(splash)
            
        print(f"Lỗi khi khởi động GUI: {str(e)}")
        traceback.print_exc()
        print("Chuyển sang chế độ dòng lệnh.")
        run_command_line()

def run_command_line():
    """Chạy trong chế độ dòng lệnh"""
    print("\n" + "="*80)
    print("CHẠY KIỂM THỬ TRONG CHẾ ĐỘ DÒNG LỆNH")
    print("="*80 + "\n")
    
    print("Các tùy chọn:")
    print("1. Chạy tất cả các test")
    print("2. Chọn các test cụ thể")
    print("3. Thoát")
    
    choice = input("Lựa chọn của bạn (1-3): ")
    
    if choice == "1":
        # Chạy tất cả
        subprocess.call([
            sys.executable, "-m", "pytest", 
            "lazada_test.py", "-v", 
            "--html=reports/lazada_test_report.html",
            "--self-contained-html"
        ])
        
    elif choice == "2":
        # Danh sách các test
        test_cases = [
            ("1", "test_01_homepage_load", "Kiểm tra trang chủ"),
            ("2", "test_02_search_products", "Tìm kiếm sản phẩm"),
            ("3", "test_03_product_details", "Chi tiết sản phẩm"),
            ("4", "test_04_category_navigation", "Điều hướng danh mục"),
            ("5", "test_05_add_to_cart_view_cart", "Thêm vào giỏ & xem giỏ hàng"),
            ("6", "test_06_ui_elements", "Phần tử UI"),
            ("7", "test_07_basic_performance", "Hiệu năng cơ bản"),
            ("8", "test_08_content_validation", "Xác minh nội dung"),
            ("9", "test_09_basic_security", "Bảo mật cơ bản"),
            ("10", "test_10_image_loading", "Tải hình ảnh")
        ]
        
        print("\nCác test có sẵn:")
        for num, test_id, test_name in test_cases:
            print(f"{num}. {test_name}")
            
        selection = input("\nNhập số của các test muốn chạy (phân cách bằng dấu phẩy): ")
        selected_nums = [s.strip() for s in selection.split(",")]
        
        # Tạo danh sách test
        test_ids = []
        for num in selected_nums:
            for test_num, test_id, _ in test_cases:
                if num == test_num:
                    test_ids.append(test_id)
                    
        if not test_ids:
            print("Không có test nào được chọn.")
            return
            
        # Chạy các test đã chọn
        test_expr = " or ".join(test_ids)
        
        subprocess.call([
            sys.executable, "-m", "pytest", 
            "lazada_test.py::TestLazada::" + test_ids[0],  # Cần ít nhất một test cụ thể
            "-v", "-k", test_expr,
            "--html=reports/lazada_test_report.html",
            "--self-contained-html"
        ])
        
    elif choice == "3":
        print("Thoát.")
        return
        
    else:
        print("Lựa chọn không hợp lệ.")
        
    print("\nKiểm thử hoàn tất. Báo cáo được lưu trong reports/lazada_test_report.html")
    print("Ảnh chụp màn hình được lưu trong thư mục screenshots\n")
    
    # Hỏi người dùng có muốn mở báo cáo không
    if os.path.exists("reports/lazada_test_report.html"):
        view_report = input("Bạn có muốn mở báo cáo HTML không? (y/n): ")
        if view_report.lower() == 'y':
            import webbrowser
            webbrowser.open("file://" + os.path.join(os.getcwd(), "reports/lazada_test_report.html"))

def parse_arguments():
    """Phân tích các tham số dòng lệnh"""
    parser = argparse.ArgumentParser(description='Công cụ kiểm thử tự động Lazada')
    parser.add_argument('--cli', action='store_true', help='Chạy trong chế độ dòng lệnh')
    parser.add_argument('--gui', action='store_true', help='Chạy với giao diện đồ họa')
    parser.add_argument('--headless', action='store_true', help='Chạy ẩn trình duyệt')
    parser.add_argument('--test', type=str, help='Chạy một test cụ thể (ví dụ: test_01_homepage_load)')
    
    args = parser.parse_args()
    
    # Nếu có tham số --test, chạy test đó
    if args.test:
        os.environ["HEADLESS"] = "True" if args.headless else "False"
        subprocess.call([
            sys.executable, "-m", "pytest", 
            f"lazada_test.py::TestLazada::{args.test}", 
            "-v", 
            "--html=reports/lazada_test_report.html",
            "--self-contained-html"
        ])
        return True
        
    # Nếu có tham số --cli, chạy chế độ dòng lệnh
    if args.cli:
        run_command_line()
        return True
        
    # Nếu có tham số --gui, chạy chế độ GUI
    if args.gui:
        run_with_gui()
        return True
        
    return False

if __name__ == "__main__":
    try:
        print("Kiểm tra và cài đặt các thư viện cần thiết...")
        if not install_dependencies():
            print("Không thể cài đặt đầy đủ các thư viện, nhưng vẫn tiếp tục...")
        
        # Kiểm tra xử lý tham số dòng lệnh
        if parse_arguments():
            sys.exit(0)
        
        # Kiểm tra có GUI hay không
        try:
            import tkinter as tk
            has_gui = True
            print("Tkinter đã sẵn sàng")
        except ImportError as e:
            has_gui = False
            print(f"Lỗi khi nạp Tkinter: {e}")
            print("Sẽ sử dụng chế độ dòng lệnh...")
        
        if has_gui:
            # Chạy chương trình với GUI
            print("Khởi động giao diện đồ họa...")
            run_with_gui()
        else:
            # Chạy trong chế độ dòng lệnh
            run_command_line()
    except Exception as e:
        print(f"LỖI CHƯƠNG TRÌNH: {str(e)}")
        traceback.print_exc()
        input("Nhấn Enter để thoát...")