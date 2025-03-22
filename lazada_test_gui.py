import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
import subprocess
import asyncio
import threading
import json
import time
import csv
import pandas as pd
from datetime import datetime
import logging
from PIL import Image, ImageTk
import glob
import matplotlib
matplotlib.use('Agg')  # Use Agg backend for saving plots without displaying
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Đường dẫn tới các thư mục
SCREENSHOTS_DIR = 'screenshots'
REPORTS_DIR = 'reports'
DATA_DIR = 'test_data'

# Đảm bảo các thư mục tồn tại
for dir_path in [SCREENSHOTS_DIR, REPORTS_DIR, DATA_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("lazada_test_gui.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

class LogHandler(logging.Handler):
    """Xử lý log để hiển thị trong GUI"""
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget
        
    def emit(self, record):
        msg = self.format(record)
        
        # Đảm bảo cập nhật GUI trong main thread
        if threading.current_thread() == threading.main_thread():
            self._insert_log(msg, record.levelno)
        else:
            # Sử dụng after để cập nhật từ các thread khác
            self.text_widget.after(0, lambda: self._insert_log(msg, record.levelno))
    
    def _insert_log(self, msg, levelno):
        self.text_widget.config(state=tk.NORMAL)
        
        # Thêm màu cho log dựa trên level
        tag = "info"
        if levelno >= logging.ERROR:
            tag = "error"
        elif levelno >= logging.WARNING:
            tag = "warning"
            
        self.text_widget.insert(tk.END, msg + '\n', tag)
        self.text_widget.see(tk.END)
        self.text_widget.config(state=tk.DISABLED)


class LazadaTestGUI:
    """GUI cho ứng dụng kiểm thử Lazada"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Lazada E-commerce Website Testing Tool")
        self.root.geometry("1280x800")
        self.root.minsize(1000, 700)
        
        # Biến theo dõi trạng thái
        self.testing_in_progress = False
        self.current_test = None
        self.test_results = {}
        self.start_time = None
        self.config = self.load_config()
        self.browser_process = None
        self.headless_mode = tk.BooleanVar(value=self.config.get('headless', False))
        self.show_browsers = tk.BooleanVar(value=self.config.get('show_browsers', True))
        self.auto_report = tk.BooleanVar(value=self.config.get('auto_report', True))
        self.test_url = tk.StringVar(value=self.config.get('test_url', 'https://www.lazada.vn/'))
        self.test_product = tk.StringVar(value=self.config.get('test_product', 'điện thoại Samsung'))
        
        # Thiết lập giao diện
        self.create_menu()
        self.create_widgets()
        self.configure_styles()
        
        # Lấy các ảnh chụp màn hình gần đây để hiển thị
        self.load_recent_screenshots()
        
        # Lịch sử kết quả kiểm thử
        self.load_test_history()
        
        # Tạo tab thống kê với biểu đồ trống ban đầu
        self.create_stats_charts()
        
        # Cập nhật trạng thái kiểm thử
        self.update_status("Sẵn sàng để thực hiện kiểm thử")
        
    def configure_styles(self):
        """Thiết lập style cho các widget"""
        style = ttk.Style()
        style.configure("TFrame", background="white")
        style.configure("TButton", font=("Arial", 10))
        style.configure("TLabel", font=("Arial", 10), background="white")
        style.configure("Header.TLabel", font=("Arial", 12, "bold"), background="white")
        style.configure("Title.TLabel", font=("Arial", 14, "bold"), background="white")
        style.configure("Status.TLabel", font=("Arial", 10, "italic"), background="white")
        style.configure("Pass.TLabel", foreground="green")
        style.configure("Fail.TLabel", foreground="red")
        style.configure("Running.TLabel", foreground="blue")
        style.configure("TNotebook", background="white") 
        style.configure("TNotebook.Tab", padding=[10, 2], font=('Arial', 10))

    def create_menu(self):
        """Tạo menu cho ứng dụng"""
        self.menu_bar = tk.Menu(self.root)
        
        # Menu File
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_menu.add_command(label="Mở báo cáo HTML", command=self.open_html_report)
        file_menu.add_command(label="Mở thư mục ảnh chụp màn hình", command=self.open_screenshots_folder)
        file_menu.add_command(label="Xuất kết quả ra Excel", command=self.export_to_excel)
        file_menu.add_separator()
        file_menu.add_command(label="Thoát", command=self.root.quit)
        self.menu_bar.add_cascade(label="File", menu=file_menu)
        
        # Menu Công cụ
        tools_menu = tk.Menu(self.menu_bar, tearoff=0)
        tools_menu.add_command(label="Cài đặt", command=self.show_settings)
        tools_menu.add_command(label="Xóa ảnh chụp màn hình cũ", command=self.clear_old_screenshots)
        tools_menu.add_command(label="Xóa lịch sử kiểm thử", command=self.clear_test_history)
        tools_menu.add_separator() 
        tools_menu.add_command(label="Lưu cấu hình", command=self.save_config)
        tools_menu.add_command(label="Khôi phục cấu hình mặc định", command=self.reset_config)
        self.menu_bar.add_cascade(label="Công cụ", menu=tools_menu)
        
        # Menu Báo cáo
        report_menu = tk.Menu(self.menu_bar, tearoff=0)
        report_menu.add_command(label="Tạo báo cáo đầy đủ", command=self.generate_full_report)
        report_menu.add_command(label="Tạo báo cáo tóm tắt", command=lambda: self.generate_full_report(summary=True))
        report_menu.add_command(label="Xem biểu đồ kết quả", command=self.show_result_charts)
        self.menu_bar.add_cascade(label="Báo cáo", menu=report_menu)
        
        # Menu Trợ giúp
        help_menu = tk.Menu(self.menu_bar, tearoff=0)
        help_menu.add_command(label="Hướng dẫn sử dụng", command=self.show_help)
        help_menu.add_command(label="Kiểm tra cập nhật", command=self.check_updates)
        help_menu.add_command(label="Giới thiệu", command=self.show_about)
        self.menu_bar.add_cascade(label="Trợ giúp", menu=help_menu)
        
        self.root.config(menu=self.menu_bar)
        
    def create_widgets(self):
        """Tạo các thành phần giao diện"""
        # Khung chính
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Label tiêu đề
        ttk.Label(self.main_frame, text="Công cụ Kiểm thử Tự động Trang Web Lazada", 
                  style="Title.TLabel").pack(pady=10)
        
        # Notebook để tạo tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab kiểm thử
        self.testing_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.testing_tab, text="Kiểm thử")
        
        # Tab thống kê
        self.stats_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_tab, text="Biểu đồ & Thống kê")
        
        # Tab cấu hình
        self.config_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.config_tab, text="Cấu hình")
        
        # Tab lịch sử
        self.history_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.history_tab, text="Lịch sử")
        
        # Tạo nội dung cho tab kiểm thử
        self.create_testing_tab()
        
        # Tạo nội dung cho tab cấu hình
        self.create_config_tab()
        
        # Tạo nội dung cho tab lịch sử
        self.create_history_tab()
        
    def create_testing_tab(self):
        """Tạo nội dung cho tab kiểm thử"""
        # Chia tab thành 3 phần: trái, giữa, phải
        self.testing_paned_window = ttk.PanedWindow(self.testing_tab, orient=tk.HORIZONTAL)
        self.testing_paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Frame bên trái (Danh sách test, kiểm soát)
        self.left_frame = ttk.Frame(self.testing_paned_window)
        self.testing_paned_window.add(self.left_frame, weight=1)
        
        # Frame cho trạng thái và điều khiển 
        control_frame = ttk.LabelFrame(self.left_frame, text="Điều khiển và trạng thái")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Thêm trạng thái
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(control_frame, textvariable=self.status_var, 
                                     style="Status.TLabel")
        self.status_label.pack(pady=5, padx=10, anchor=tk.W)
        
        # Thanh tiến trình  
        self.progress_var = tk.IntVar()
        self.progress = ttk.Progressbar(control_frame, variable=self.progress_var, 
                                        maximum=100, length=200)
        self.progress.pack(pady=5, padx=10, fill=tk.X)
        
        # Thời gian chạy
        self.time_var = tk.StringVar(value="Thời gian: 00:00")
        ttk.Label(control_frame, textvariable=self.time_var).pack(pady=5, padx=10, anchor=tk.W)
        
        # Frame cho checkbox và nút
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Checkbox cho các tùy chọn
        ttk.Checkbutton(button_frame, text="Chạy ẩn trình duyệt", 
                       variable=self.headless_mode).pack(side=tk.LEFT, padx=5)
        
        # Nút điều khiển
        self.run_button = ttk.Button(button_frame, text="Chạy tất cả",
                                    command=self.run_all_tests)
        self.run_button.pack(side=tk.RIGHT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Dừng", 
                                     command=self.stop_tests, state=tk.DISABLED)
        self.stop_button.pack(side=tk.RIGHT, padx=5)
        
        # Frame cho danh sách test
        test_frame = ttk.LabelFrame(self.left_frame, text="Danh sách Test")
        test_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=10)
        
        # Danh sách các test case
        self.test_list = ttk.Treeview(test_frame, columns=("name", "status", "time"), 
                                     show="headings", selectmode="browse")
        self.test_list.heading("name", text="Tên Test")
        self.test_list.heading("status", text="Trạng thái")
        self.test_list.heading("time", text="Thời gian (ms)")
        self.test_list.column("name", width=150)
        self.test_list.column("status", width=80)
        self.test_list.column("time", width=80)
        
        # Thêm scrollbar cho danh sách
        test_scrollbar = ttk.Scrollbar(test_frame, orient="vertical", 
                                      command=self.test_list.yview)
        self.test_list.configure(yscrollcommand=test_scrollbar.set)
        
        test_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.test_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Liên kết sự kiện chọn test
        self.test_list.bind("<<TreeviewSelect>>", self.on_test_selected)
        
        # Tạo danh sách các test
        self.populate_test_list()
        
        # Frame giữa (log)
        self.middle_frame = ttk.Frame(self.testing_paned_window)
        self.testing_paned_window.add(self.middle_frame, weight=2)
        
        # Frame cho log output
        log_frame = ttk.LabelFrame(self.middle_frame, text="Log Output")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Text widget cho log
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
        # Thiết lập tag cho level log khác nhau
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("warning", foreground="orange")
        self.log_text.tag_configure("info", foreground="blue")
        
        # Thêm handler log cho GUI
        log_handler = LogHandler(self.log_text)
        log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(log_handler)
        
        # Frame bên phải (ảnh chụp màn hình)
        self.right_frame = ttk.Frame(self.testing_paned_window)
        self.testing_paned_window.add(self.right_frame, weight=2)
        
        # Frame cho ảnh chụp màn hình
        screenshot_frame = ttk.LabelFrame(self.right_frame, text="Ảnh chụp màn hình")
        screenshot_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas để hiển thị ảnh
        self.screenshot_canvas = tk.Canvas(screenshot_frame, bg="white")
        self.screenshot_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Frame cho danh sách ảnh chụp màn hình
        thumbnail_frame = ttk.Frame(screenshot_frame)
        thumbnail_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # ScrolledFrame cho thumbnails
        self.thumbnail_canvas = tk.Canvas(thumbnail_frame, height=120, bg="white")
        thumbnail_scrollbar = ttk.Scrollbar(thumbnail_frame, orient="horizontal", 
                                           command=self.thumbnail_canvas.xview)
        self.thumbnail_canvas.configure(xscrollcommand=thumbnail_scrollbar.set)
        
        thumbnail_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.thumbnail_canvas.pack(side=tk.TOP, fill=tk.X, expand=True)
        
        # Frame bên trong canvas để chứa thumbnails
        self.thumbnail_frame = ttk.Frame(self.thumbnail_canvas, style="TFrame")
        self.thumbnail_canvas.create_window((0, 0), window=self.thumbnail_frame, anchor="nw")
        
        # Cập nhật kích thước của canvas khi kích thước của frame thay đổi
        self.thumbnail_frame.bind("<Configure>", self.on_thumbnail_frame_configure)
        
        # Hiển thị thông tin về ảnh chụp màn hình đang xem
        self.screenshot_info_var = tk.StringVar()
        self.screenshot_info = ttk.Label(screenshot_frame, textvariable=self.screenshot_info_var, 
                                         style="Status.TLabel")
        self.screenshot_info.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # Nút để mở ảnh chụp màn hình
        button_frame = ttk.Frame(screenshot_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_frame, text="Mở ảnh", command=self.open_current_screenshot).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Lưu ảnh", command=self.save_current_screenshot).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Làm mới", command=self.load_recent_screenshots).pack(side=tk.RIGHT, padx=5)
    
    def create_config_tab(self):
        """Tạo nội dung cho tab cấu hình"""
        config_frame = ttk.Frame(self.config_tab, padding=20)
        config_frame.pack(fill=tk.BOTH, expand=True)
        
        # Tiêu đề
        ttk.Label(config_frame, text="Cấu hình kiểm thử", 
                  style="Header.TLabel").grid(row=0, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        # URL kiểm thử
        ttk.Label(config_frame, text="URL trang web:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(config_frame, textvariable=self.test_url, width=50).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Từ khóa tìm kiếm
        ttk.Label(config_frame, text="Từ khóa tìm kiếm:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(config_frame, textvariable=self.test_product, width=50).grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Các tùy chọn
        ttk.Label(config_frame, text="Tùy chọn kiểm thử:", 
                 style="Header.TLabel").grid(row=3, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        ttk.Checkbutton(config_frame, text="Chạy ẩn trình duyệt", 
                       variable=self.headless_mode).grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        
        ttk.Checkbutton(config_frame, text="Hiển thị trình duyệt trong danh sách tác vụ", 
                       variable=self.show_browsers).grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        
        ttk.Checkbutton(config_frame, text="Tự động mở báo cáo sau khi kiểm thử hoàn tất", 
                       variable=self.auto_report).grid(row=6, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        
        # Thời gian chờ
        ttk.Label(config_frame, text="Thời gian chờ tối đa (giây):").grid(row=7, column=0, padx=5, pady=5, sticky=tk.W)
        self.timeout_var = tk.StringVar(value=self.config.get('timeout', '60'))
        ttk.Entry(config_frame, textvariable=self.timeout_var, width=10).grid(row=7, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Số lần thử lại
        ttk.Label(config_frame, text="Số lần thử lại:").grid(row=8, column=0, padx=5, pady=5, sticky=tk.W)
        self.retry_var = tk.StringVar(value=self.config.get('retry', '1'))
        ttk.Entry(config_frame, textvariable=self.retry_var, width=10).grid(row=8, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Nút lưu cấu hình
        button_frame = ttk.Frame(config_frame)
        button_frame.grid(row=9, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Lưu cấu hình", 
                  command=self.save_config).pack(side=tk.LEFT, padx=10)
                  
        ttk.Button(button_frame, text="Khôi phục mặc định", 
                  command=self.reset_config).pack(side=tk.LEFT, padx=10)
    
    def create_history_tab(self):
        """Tạo nội dung cho tab lịch sử"""
        history_frame = ttk.Frame(self.history_tab)
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tiêu đề
        ttk.Label(history_frame, text="Lịch sử kiểm thử", 
                 style="Header.TLabel").pack(pady=10, anchor=tk.W)
        
        # Frame cho bảng lịch sử
        table_frame = ttk.Frame(history_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Tạo bảng cho lịch sử kiểm thử
        self.history_table = ttk.Treeview(table_frame, 
                                         columns=("date", "passed", "failed", "total", "duration"),
                                         show="headings")
        
        self.history_table.heading("date", text="Ngày")
        self.history_table.heading("passed", text="Đạt")
        self.history_table.heading("failed", text="Lỗi") 
        self.history_table.heading("total", text="Tổng số")
        self.history_table.heading("duration", text="Thời gian (s)")
        
        self.history_table.column("date", width=150)
        self.history_table.column("passed", width=80)
        self.history_table.column("failed", width=80)
        self.history_table.column("total", width=80)
        self.history_table.column("duration", width=100)
        
        # Tạo scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", 
                                 command=self.history_table.yview)
        self.history_table.configure(yscrollcommand=scrollbar.set)
        
        # Pack các thành phần
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Frame cho nút điều khiển
        buttons_frame = ttk.Frame(history_frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        # Nút làm mới và xóa lịch sử
        ttk.Button(buttons_frame, text="Làm mới", 
                  command=self.load_test_history).pack(side=tk.LEFT, padx=5)
                  
        ttk.Button(buttons_frame, text="Xóa lịch sử", 
                  command=self.clear_test_history).pack(side=tk.LEFT, padx=5)
                  
        ttk.Button(buttons_frame, text="Xuất ra Excel", 
                  command=self.export_history_to_excel).pack(side=tk.LEFT, padx=5)
                  
        ttk.Button(buttons_frame, text="Biểu đồ", 
                  command=self.show_history_charts).pack(side=tk.RIGHT, padx=5)
        
    def create_stats_charts(self):
        """Tạo biểu đồ thống kê"""
        stats_frame = ttk.Frame(self.stats_tab)
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tiêu đề
        ttk.Label(stats_frame, text="Biểu đồ thống kê kết quả kiểm thử", 
                 style="Header.TLabel").pack(pady=10)
        
        # Tạo frame cho các biểu đồ
        charts_frame = ttk.Frame(stats_frame)
        charts_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Chia thành hai cột
        left_charts = ttk.Frame(charts_frame)
        left_charts.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        right_charts = ttk.Frame(charts_frame)
        right_charts.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        
        # Biểu đồ tròn kết quả
        pie_frame = ttk.LabelFrame(left_charts, text="Kết quả kiểm thử mới nhất")
        pie_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.pie_figure = plt.Figure(figsize=(5, 4), dpi=100)
        self.pie_canvas = FigureCanvasTkAgg(self.pie_figure, pie_frame)
        self.pie_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Biểu đồ cột thời gian thực hiện
        bar_frame = ttk.LabelFrame(right_charts, text="Thời gian thực hiện (ms)")
        bar_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.bar_figure = plt.Figure(figsize=(5, 4), dpi=100)
        self.bar_canvas = FigureCanvasTkAgg(self.bar_figure, bar_frame)
        self.bar_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Biểu đồ xu hướng theo thời gian
        trend_frame = ttk.LabelFrame(stats_frame, text="Xu hướng kết quả theo thời gian")
        trend_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.trend_figure = plt.Figure(figsize=(10, 4), dpi=100)
        self.trend_canvas = FigureCanvasTkAgg(self.trend_figure, trend_frame)
        self.trend_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Nút làm mới
        ttk.Button(stats_frame, text="Cập nhật biểu đồ", 
                  command=self.update_charts).pack(pady=10)

    def on_thumbnail_frame_configure(self, event):
        """Cập nhật kích thước canvas khi frame thay đổi"""
        self.thumbnail_canvas.configure(scrollregion=self.thumbnail_canvas.bbox("all"))
        
    def populate_test_list(self):
        """Tạo danh sách các test case"""
        # Xóa các item cũ
        for item in self.test_list.get_children():
            self.test_list.delete(item)
            
        # Danh sách các test
        test_cases = [
            ("test_01_homepage_load", "Kiểm tra trang chủ"),
            ("test_02_search_products", "Tìm kiếm sản phẩm"),
            ("test_03_product_details", "Chi tiết sản phẩm"),
            ("test_04_category_navigation", "Điều hướng danh mục"),
            ("test_05_add_to_cart_view_cart", "Thêm vào giỏ & xem giỏ hàng"),
            ("test_06_ui_elements", "Phần tử UI"),
            ("test_07_basic_performance", "Hiệu năng cơ bản"),
            ("test_08_content_validation", "Xác minh nội dung"),
            ("test_09_basic_security", "Bảo mật cơ bản"),
            ("test_10_image_loading", "Tải hình ảnh")
        ]
        
        # Thêm vào treeview
        for test_id, test_name in test_cases:
            self.test_list.insert("", "end", test_id, values=(test_name, "Chưa chạy", "N/A"))
            
    def load_recent_screenshots(self):
        """Tải các ảnh chụp màn hình gần đây"""
        # Xóa các thumbnail cũ
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()
            
        # Tìm các ảnh trong thư mục screenshots
        screenshot_files = sorted(
            glob.glob(os.path.join(SCREENSHOTS_DIR, "*.png")),
            key=os.path.getmtime, 
            reverse=True
        )[:20]  # Chỉ lấy 20 ảnh mới nhất
        
        if not screenshot_files:
            # Hiển thị thông báo nếu không có ảnh
            ttk.Label(self.thumbnail_frame, text="Không có ảnh chụp màn hình").pack(padx=10, pady=10)
            # Xóa ảnh hiện tại trên canvas
            self.screenshot_canvas.delete("all")
            self.screenshot_info_var.set("")
            return
        
        # Tạo và hiển thị thumbnails
        self.thumbnails = []  # Lưu trữ tham chiếu
        for i, filename in enumerate(screenshot_files):
            try:
                # Tạo thumbnail
                img = Image.open(filename)
                img.thumbnail((100, 100))
                photo = ImageTk.PhotoImage(img)
                
                # Tạo frame cho mỗi thumbnail
                thumb_frame = ttk.Frame(self.thumbnail_frame)
                thumb_frame.pack(side=tk.LEFT, padx=5, pady=5)
                
                # Tạo button chứa thumbnail
                btn = ttk.Button(thumb_frame, image=photo, 
                                command=lambda f=filename: self.show_screenshot(f))
                btn.pack()
                
                # Tạo label cho tên file
                base_name = os.path.basename(filename)
                if len(base_name) > 15:
                    base_name = base_name[:12] + "..."
                ttk.Label(thumb_frame, text=base_name).pack()
                
                # Lưu trữ tham chiếu để tránh garbage collection
                self.thumbnails.append(photo)
                
                # Hiển thị ảnh đầu tiên
                if i == 0:
                    self.show_screenshot(filename)
                    
            except Exception as e:
                logger.error(f"Lỗi khi tải thumbnail {filename}: {str(e)}")
                
    def show_screenshot(self, filename):
        """Hiển thị ảnh chụp màn hình được chọn"""
        try:
            # Xóa ảnh cũ
            self.screenshot_canvas.delete("all")
            
            # Lưu tên file hiện tại
            self.current_screenshot = filename
            
            # Tải ảnh mới
            img = Image.open(filename)
            
            # Scale ảnh để vừa với canvas
            canvas_width = self.screenshot_canvas.winfo_width()
            canvas_height = self.screenshot_canvas.winfo_height()
            
            # Tỉ lệ
            width, height = img.size
            ratio = min(canvas_width/width, canvas_height/height)
            
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            
            if new_width > 0 and new_height > 0:
                img = img.resize((new_width, new_height), Image.LANCZOS)
                
            photo = ImageTk.PhotoImage(img)
            
            # Hiển thị ảnh
            self.screenshot_canvas.create_image(
                canvas_width/2, canvas_height/2, 
                image=photo, anchor=tk.CENTER
            )
            
            # Lưu trữ tham chiếu
            self.current_photo = photo
            
            # Cập nhật thông tin ảnh
            base_name = os.path.basename(filename)
            file_size = os.path.getsize(filename) / 1024  # KB
            file_time = datetime.fromtimestamp(os.path.getmtime(filename))
            
            self.screenshot_info_var.set(
                f"{base_name} - {width}x{height} - {file_size:.1f}KB - {file_time:%d/%m/%Y %H:%M:%S}"
            )
            
        except Exception as e:
            logger.error(f"Lỗi khi hiển thị ảnh {filename}: {str(e)}")
            self.screenshot_info_var.set(f"Lỗi khi hiển thị ảnh: {str(e)}")
            
    def open_current_screenshot(self):
        """Mở ảnh chụp màn hình hiện tại trong trình xem ảnh mặc định"""
        if hasattr(self, 'current_screenshot') and os.path.exists(self.current_screenshot):
            if sys.platform == 'win32':
                os.startfile(self.current_screenshot)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open', self.current_screenshot])
            else:  # linux
                subprocess.call(['xdg-open', self.current_screenshot])
        else:
            messagebox.showinfo("Thông báo", "Không có ảnh nào được chọn")
            
    def save_current_screenshot(self):
        """Lưu ảnh chụp màn hình hiện tại vào vị trí khác"""
        if hasattr(self, 'current_screenshot') and os.path.exists(self.current_screenshot):
            base_name = os.path.basename(self.current_screenshot)
            save_path = filedialog.asksaveasfilename(
                initialfile=base_name,
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
            )
            
            if save_path:
                import shutil
                try:
                    shutil.copy2(self.current_screenshot, save_path)
                    messagebox.showinfo("Thành công", f"Ảnh đã được lưu tại:\n{save_path}")
                except Exception as e:
                    messagebox.showerror("Lỗi", f"Không thể lưu ảnh: {str(e)}")
        else:
            messagebox.showinfo("Thông báo", "Không có ảnh nào được chọn")
            
    def update_status(self, message, is_running=False, is_error=False):
        """Cập nhật thông báo trạng thái"""
        self.status_var.set(message)
        
        if is_running:
            self.status_label.configure(foreground="blue")
        elif is_error:
            self.status_label.configure(foreground="red")
        else:
            self.status_label.configure(foreground="black")
            
    def run_all_tests(self):
        """Chạy tất cả các test"""
        if self.testing_in_progress:
            messagebox.showwarning("Đang thực hiện kiểm thử", 
                                   "Đang có bộ kiểm thử đang chạy. Vui lòng chờ đợi!")
            return
            
        # Cập nhật UI trước khi bắt đầu
        self.testing_in_progress = True
        self.run_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Lưu thời gian bắt đầu
        self.start_time = time.time()
        
        # Bắt đầu timer để cập nhật thời gian
        self.update_timer()
        
        # Reset trạng thái các test
        for item in self.test_list.get_children():
            self.test_list.item(item, values=(self.test_list.item(item, "values")[0], "Đang chờ", "N/A"))
            
        # Reset progress bar
        self.progress_var.set(0)
        
        # Khởi tạo thread mới để chạy test
        threading.Thread(target=self.run_tests_in_thread, daemon=True).start()
        
    def update_timer(self):
        """Cập nhật thời gian chạy"""
        if not self.testing_in_progress or not self.start_time:
            return
            
        # Tính thời gian
        elapsed = time.time() - self.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        
        # Cập nhật label
        self.time_var.set(f"Thời gian: {minutes:02d}:{seconds:02d}")
        
        # Gọi lại sau 1 giây
        self.root.after(1000, self.update_timer)
        
    def run_tests_in_thread(self):
        """Chạy tests trong thread riêng biệt"""
        try:
            # Danh sách các test để chạy
            test_cases = self.test_list.get_children()
            total_tests = len(test_cases)
            
            # Lưu kết quả chi tiết của lần chạy test này
            session_results = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'passed': 0,
                'failed': 0,
                'total': total_tests,
                'duration': 0,
                'tests': {}
            }
            
            # Cấu hình chạy headless nếu được chọn
            headless_option = "--headless" if self.headless_mode.get() else ""
            
            # Thiết lập biến môi trường
            env_vars = os.environ.copy()
            env_vars["HEADLESS"] = str(self.headless_mode.get())
            env_vars["TEST_URL"] = self.test_url.get()
            env_vars["TEST_PRODUCT"] = self.test_product.get()
            
            # Chạy từng test một
            for i, test_id in enumerate(test_cases, 1):
                if not self.testing_in_progress:
                    logger.info("Đã dừng bộ kiểm thử theo yêu cầu")
                    break
                    
                # Cập nhật UI
                self.current_test = test_id
                test_name = self.test_list.item(test_id, "values")[0]
                self.update_status(f"Đang chạy: {test_name}", is_running=True)
                
                # Cập nhật trạng thái test
                self.root.after(0, lambda id=test_id, name=test_name: 
                                self.test_list.item(id, values=(name, "Đang chạy", "N/A")))
                
                # Gọi command để chạy test cụ thể
                logger.info(f"Bắt đầu test: {test_id}")
                start_time = time.time()
                
                # Tạo timeout từ cấu hình
                timeout = self.config.get('timeout', '60')
                
                command = [
                    sys.executable, "-m", "pytest", 
                    f"lazada_test.py::TestLazada::{test_id}", 
                    "-v", headless_option,
                    f"--timeout={timeout}",
                    "--html=reports/lazada_test_report.html",
                    "--self-contained-html"
                ]
                
                process = subprocess.Popen(
                    command, 
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    env=env_vars
                )
                
                # Đọc output và gửi đến log
                for line in process.stdout:
                    logger.info(line.strip())
                
                # Đợi tiến trình hoàn thành
                return_code = process.wait()
                
                # Tính thời gian
                elapsed_time = int((time.time() - start_time) * 1000)  # ms
                
                # Xác định trạng thái
                status = "Đạt" if return_code == 0 else "Lỗi"
                
                # Lưu kết quả test
                session_results['tests'][test_id] = {
                    'name': test_name,
                    'status': status,
                    'time': elapsed_time,
                    'return_code': return_code
                }
                
                if status == "Đạt":
                    session_results['passed'] += 1
                else:
                    session_results['failed'] += 1
                
                # Cập nhật UI
                self.root.after(0, lambda id=test_id, name=test_name, s=status, t=elapsed_time: 
                                self.test_list.item(id, values=(name, s, f"{t}")))
                
                # Lưu kết quả
                self.test_results[test_id] = {
                    'name': test_name,
                    'status': status,
                    'time': elapsed_time,
                    'return_code': return_code
                }
                
                # Cập nhật progress bar
                progress = int((i / total_tests) * 100)
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
                
                # Tải lại ảnh chụp màn hình nếu có ảnh mới
                if i % 1 == 0:  # Cập nhật sau mỗi test
                    self.root.after(0, self.load_recent_screenshots)
                    
            # Tổng thời gian chạy
            session_results['duration'] = time.time() - self.start_time
                    
            # Hoàn thành
            if self.testing_in_progress:
                # Đã chạy hết tất cả test
                self.root.after(0, lambda: self.progress_var.set(100))
                self.root.after(0, lambda: self.update_status("Hoàn thành kiểm thử"))
                
                # Lưu lịch sử
                self.save_test_history(session_results)
                
                # Tổng kết kết quả
                passed = session_results['passed']
                total = session_results['total']
                
                logger.info(f"--- Tổng kết kiểm thử: {passed}/{total} test đạt ---")
                
                # Cập nhật biểu đồ
                self.root.after(0, self.update_charts)
                
                # Tải lại ảnh chụp màn hình
                self.root.after(0, self.load_recent_screenshots)
                
                # Mở báo cáo HTML nếu có và được cấu hình
                if os.path.exists("reports/lazada_test_report.html") and self.auto_report.get():
                    if messagebox.askyesno("Kiểm thử hoàn thành", 
                                          f"{passed}/{total} test đạt. Bạn có muốn xem báo cáo HTML không?"):
                        self.open_html_report()
                        
        except Exception as e:
            logger.error(f"Lỗi khi chạy tests: {str(e)}")
            self.root.after(0, lambda: self.update_status(f"Lỗi: {str(e)}", is_error=True))
            
        finally:
            # Đặt lại trạng thái UI
            self.testing_in_progress = False
            self.current_test = None
            self.root.after(0, lambda: self.run_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
            
    def stop_tests(self):
        """Dừng quá trình kiểm thử"""
        if not self.testing_in_progress:
            return
            
        self.testing_in_progress = False
        self.update_status("Đang dừng kiểm thử...", is_running=True)
        
        # Nếu có process của browser đang chạy, kill nó
        if self.browser_process is not None:
            try:
                self.browser_process.terminate()
                logger.info("Đã dừng process browser")
            except Exception as e:
                logger.error(f"Lỗi khi dừng process browser: {str(e)}")
        
    def on_test_selected(self, event):
        """Xử lý khi một test được chọn trong danh sách"""
        selected_id = self.test_list.selection()
        if not selected_id:
            return
            
        test_id = selected_id[0]
        
        # Tìm ảnh chụp màn hình liên quan đến test
        test_name = test_id.split("_")[-1]  # Lấy phần cuối của test_id
        screenshot_files = sorted(
            glob.glob(os.path.join(SCREENSHOTS_DIR, f"*{test_name}*.png")),
            key=os.path.getmtime, 
            reverse=True
        )
        
        if screenshot_files:
            # Hiển thị ảnh đầu tiên
            self.show_screenshot(screenshot_files[0])
            
            # Hiển thị thông tin test
            test_info = self.test_list.item(test_id, "values")
            status = self.test_results.get(test_id, {}).get("status", "Chưa chạy")
            time_ms = self.test_results.get(test_id, {}).get("time", "N/A")
            
            logger.info(f"Đã chọn test: {test_id} - Trạng thái: {status} - Thời gian: {time_ms}ms")
            
    def open_html_report(self):
        """Mở báo cáo HTML trong trình duyệt"""
        report_path = os.path.join(os.getcwd(), "reports", "lazada_test_report.html")
        if os.path.exists(report_path):
            # Mở trong trình duyệt mặc định
            import webbrowser
            webbrowser.open(f"file://{report_path}")
        else:
            messagebox.showinfo("Thông báo", "Chưa có báo cáo HTML. Hãy chạy kiểm thử trước.")
            
    def open_screenshots_folder(self):
        """Mở thư mục ảnh chụp màn hình"""
        screenshots_path = os.path.join(os.getcwd(), SCREENSHOTS_DIR)
        if os.path.exists(screenshots_path):
            # Mở bằng lệnh hệ điều hành
            if sys.platform == 'win32':
                os.startfile(screenshots_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open', screenshots_path])
            else:  # linux
                subprocess.call(['xdg-open', screenshots_path])
                
    def clear_old_screenshots(self):
        """Xóa ảnh chụp màn hình cũ"""
        screenshots_path = os.path.join(os.getcwd(), SCREENSHOTS_DIR)
        if not os.path.exists(screenshots_path):
            return
            
        if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa tất cả ảnh chụp màn hình cũ?"):
            try:
                # Giữ lại 10 ảnh mới nhất
                screenshot_files = sorted(
                    glob.glob(os.path.join(screenshots_path, "*.png")),
                    key=os.path.getmtime, 
                    reverse=True
                )
                
                # Xóa các ảnh cũ
                for file in screenshot_files[10:]:
                    os.remove(file)
                    
                messagebox.showinfo("Thành công", "Đã xóa ảnh chụp màn hình cũ")
                
                # Tải lại ảnh
                self.load_recent_screenshots()
                
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi khi xóa ảnh: {str(e)}")
                
    def export_to_excel(self):
        """Xuất kết quả kiểm thử ra file Excel"""
        if not self.test_results:
            messagebox.showinfo("Thông báo", "Chưa có kết quả kiểm thử nào để xuất.")
            return
            
        try:
            # Tạo DataFrame
            data = []
            for test_id, result in self.test_results.items():
                # Đảm bảo các giá trị không phải None
                test_name = result.get('name', '') or ""
                test_status = result.get('status', '') or ""
                test_time = result.get('time', '') or 0
                
                data.append({
                    'Test ID': test_id,
                    'Tên Test': test_name,
                    'Trạng thái': test_status,
                    'Thời gian (ms)': test_time,
                    'Ngày chạy': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
            # Đảm bảo thư mục reports tồn tại
            if not os.path.exists(REPORTS_DIR):
                os.makedirs(REPORTS_DIR)
                
            # Tạo DataFrame
            df = pd.DataFrame(data)
            
            # Lưu vào Excel
            default_filename = f"lazada_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            default_path = os.path.join(REPORTS_DIR, default_filename)
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx", 
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                initialdir=REPORTS_DIR,
                initialfile=default_filename
            )
            
            if not file_path:
                return
                
            # Đảm bảo đuôi file là .xlsx
            if not file_path.lower().endswith('.xlsx'):
                file_path += '.xlsx'
                
            # Sử dụng try-except riêng cho việc ghi file Excel
            try:
                df.to_excel(file_path, index=False)
                messagebox.showinfo("Thành công", f"Đã xuất kết quả ra file:\n{file_path}")
                
                # Hỏi người dùng có muốn mở file Excel không
                if messagebox.askyesno("Mở file", "Bạn có muốn mở file Excel vừa tạo không?"):
                    if sys.platform == 'win32':
                        os.startfile(file_path)
                    elif sys.platform == 'darwin':  # macOS
                        subprocess.call(['open', file_path])
                    else:  # linux
                        subprocess.call(['xdg-open', file_path])
                        
            except Exception as excel_err:
                logger.error(f"Lỗi khi ghi file Excel: {str(excel_err)}")
                messagebox.showerror("Lỗi", f"Không thể ghi file Excel: {str(excel_err)}")
                
        except pd.errors.EmptyDataError:
            messagebox.showerror("Lỗi", "Không có dữ liệu để xuất")
        except Exception as e:
            logger.error(f"Lỗi khi xuất Excel: {str(e)}")
            messagebox.showerror("Lỗi", f"Không thể xuất kết quả: {str(e)}")
            
    def export_history_to_excel(self):
        """Xuất lịch sử kiểm thử ra file Excel"""
        # Lấy dữ liệu từ history_table
        try:
            data = []
            for item_id in self.history_table.get_children():
                values = self.history_table.item(item_id, "values")
                data.append({
                    'Ngày': values[0],
                    'Đạt': values[1],
                    'Lỗi': values[2],
                    'Tổng số': values[3],
                    'Thời gian (s)': values[4]
                })
                
            if not data:
                messagebox.showinfo("Thông báo", "Không có dữ liệu lịch sử để xuất.")
                return
                
            df = pd.DataFrame(data)
            
            # Lưu vào Excel
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx", 
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                initialdir=os.getcwd(),
                initialfile=f"lazada_test_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            
            if not file_path:
                return
                
            df.to_excel(file_path, index=False)
            messagebox.showinfo("Thành công", f"Đã xuất lịch sử ra file:\n{file_path}")
            
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể xuất lịch sử: {str(e)}")
            
    def update_charts(self):
        """Cập nhật biểu đồ thống kê"""
        try:
            # Biểu đồ tròn cho kết quả
            self.pie_figure.clear()
            if self.test_results:
                # Đếm số test đạt và không đạt
                pass_count = sum(1 for r in self.test_results.values() if r.get('status') == 'Đạt')
                fail_count = sum(1 for r in self.test_results.values() if r.get('status') == 'Lỗi')
                
                # Tạo biểu đồ
                ax = self.pie_figure.add_subplot(111)
                wedges, texts, autotexts = ax.pie(
                    [pass_count, fail_count], 
                    labels=['Đạt', 'Lỗi'], 
                    autopct='%1.1f%%',
                    colors=['#4CAF50', '#F44336']
                )
                
                # Thiết lập thuộc tính cho text
                for text in texts:
                    text.set_fontsize(10)
                for autotext in autotexts:
                    autotext.set_fontsize(10)
                    autotext.set_color('white')
                    
                ax.set_title(f'Kết quả: {pass_count}/{len(self.test_results)} đạt')
            else:
                ax = self.pie_figure.add_subplot(111)
                ax.text(0.5, 0.5, "Chưa có dữ liệu", ha='center', va='center')
                ax.axis('off')
            
            self.pie_canvas.draw()
            
            # Biểu đồ cột cho thời gian thực hiện
            self.bar_figure.clear()
            if self.test_results:
                # Lấy dữ liệu thời gian
                test_names = [r.get('name', tid) for tid, r in self.test_results.items()]
                times = [r.get('time', 0) for r in self.test_results.values()]
                statuses = [r.get('status', 'N/A') for r in self.test_results.values()]
                
                # Tạo biểu đồ
                ax = self.bar_figure.add_subplot(111)
                bars = ax.bar(test_names, times)
                
                # Màu cho từng cột
                for i, bar in enumerate(bars):
                    if statuses[i] == 'Đạt':
                        bar.set_color('#4CAF50')
                    else:
                        bar.set_color('#F44336')
                
                ax.set_title('Thời gian thực hiện (ms)')
                ax.set_ylabel('Thời gian (ms)')
                ax.tick_params(axis='x', rotation=45)
                
                # Đặt giá trị lên đầu mỗi cột
                for i, bar in enumerate(bars):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height + 5,
                            f'{int(height)}',
                            ha='center', va='bottom', rotation=0)
                
                self.bar_figure.tight_layout()
            else:
                ax = self.bar_figure.add_subplot(111)
                ax.text(0.5, 0.5, "Chưa có dữ liệu", ha='center', va='center')
                ax.axis('off')
            
            self.bar_canvas.draw()
            
            # Biểu đồ xu hướng qua thời gian
            self.trend_figure.clear()
            
            # Lấy dữ liệu lịch sử
            history_path = os.path.join(DATA_DIR, "test_history.json")
            if os.path.exists(history_path):
                with open(history_path, "r") as file:
                    history = json.load(file)
                    
                if history:
                    # Trích xuất dữ liệu
                    dates = [item['timestamp'] for item in history]
                    pass_rates = [item['passed'] / item['total'] * 100 for item in history]
                    durations = [item['duration'] for item in history]
                    
                    # Sắp xếp theo thời gian
                    sorted_data = sorted(zip(dates, pass_rates, durations), key=lambda x: x[0])
                    dates, pass_rates, durations = zip(*sorted_data)
                    
                    # Tạo biểu đồ
                    ax1 = self.trend_figure.add_subplot(111)
                    color = 'tab:blue'
                    ax1.set_xlabel('Ngày')
                    ax1.set_ylabel('Tỉ lệ đạt (%)', color=color)
                    ax1.plot(dates, pass_rates, color=color, marker='o')
                    ax1.tick_params(axis='y', labelcolor=color)
                    ax1.tick_params(axis='x', rotation=45)
                    
                    # Trục y thứ hai cho thời gian
                    ax2 = ax1.twinx()
                    color = 'tab:red'
                    ax2.set_ylabel('Thời gian chạy (s)', color=color)
                    ax2.plot(dates, durations, color=color, marker='s', linestyle='--')
                    ax2.tick_params(axis='y', labelcolor=color)
                    
                    self.trend_figure.suptitle('Xu hướng kết quả theo thời gian')
                    self.trend_figure.tight_layout()
                else:
                    ax = self.trend_figure.add_subplot(111)
                    ax.text(0.5, 0.5, "Chưa đủ dữ liệu lịch sử", ha='center', va='center')
                    ax.axis('off')
            else:
                ax = self.trend_figure.add_subplot(111)
                ax.text(0.5, 0.5, "Chưa có dữ liệu lịch sử", ha='center', va='center')
                ax.axis('off')
                
            self.trend_canvas.draw()
            
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật biểu đồ: {str(e)}")
            
    def load_config(self):
        """Tải cấu hình từ file"""
        config_path = os.path.join(DATA_DIR, "config.json")
        default_config = {
            'headless': False,
            'show_browsers': True,
            'auto_report': True,
            'test_url': 'https://www.lazada.vn/',
            'test_product': 'điện thoại Samsung',
            'timeout': '60',
            'retry': '1'
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as file:
                    config = json.load(file)
                return config
            except Exception as e:
                logger.error(f"Lỗi khi tải cấu hình: {str(e)}")
                return default_config
        else:
            # Tạo file cấu hình mặc định
            try:
                os.makedirs(DATA_DIR, exist_ok=True)  # Đảm bảo thư mục tồn tại
                with open(config_path, "w") as file:
                    json.dump(default_config, file, indent=4)
            except Exception as e:
                logger.error(f"Lỗi khi tạo file cấu hình: {str(e)}")
                
            return default_config
            
    def save_config(self):
        """Lưu cấu hình vào file"""
        config = {
            'headless': self.headless_mode.get(),
            'show_browsers': self.show_browsers.get(),
            'auto_report': self.auto_report.get(),
            'test_url': self.test_url.get(),
            'test_product': self.test_product.get(),
            'timeout': self.timeout_var.get(),
            'retry': self.retry_var.get()
        }
        
        config_path = os.path.join(DATA_DIR, "config.json")
        try:
            with open(config_path, "w") as file:
                json.dump(config, file, indent=4)
            self.config = config
            messagebox.showinfo("Thành công", "Đã lưu cấu hình thành công!")
        except Exception as e:
            logger.error(f"Lỗi khi lưu cấu hình: {str(e)}")
            messagebox.showerror("Lỗi", f"Không thể lưu cấu hình: {str(e)}")
            
    def reset_config(self):
        """Khôi phục cấu hình mặc định"""
        default_config = {
            'headless': False,
            'show_browsers': True,
            'auto_report': True,
            'test_url': 'https://www.lazada.vn/',
            'test_product': 'điện thoại Samsung',
            'timeout': '60',
            'retry': '1'
        }
        
        if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn khôi phục cấu hình mặc định?"):
            # Cập nhật biến
            self.headless_mode.set(default_config['headless'])
            self.show_browsers.set(default_config['show_browsers'])
            self.auto_report.set(default_config['auto_report'])
            self.test_url.set(default_config['test_url'])
            self.test_product.set(default_config['test_product'])
            self.timeout_var.set(default_config['timeout'])
            self.retry_var.set(default_config['retry'])
            
            # Lưu vào file
            config_path = os.path.join(DATA_DIR, "config.json")
            try:
                with open(config_path, "w") as file:
                    json.dump(default_config, file, indent=4)
                self.config = default_config
                messagebox.showinfo("Thành công", "Đã khôi phục cấu hình mặc định!")
            except Exception as e:
                logger.error(f"Lỗi khi khôi phục cấu hình: {str(e)}")
                messagebox.showerror("Lỗi", f"Không thể khôi phục cấu hình: {str(e)}")
    
    def load_test_history(self):
        """Tải lịch sử kiểm thử"""
        # Xóa các item cũ
        for item in self.history_table.get_children():
            self.history_table.delete(item)
            
        history_path = os.path.join(DATA_DIR, "test_history.json")
        if os.path.exists(history_path):
            try:
                with open(history_path, "r") as file:
                    history = json.load(file)
                    
                # Thêm vào bảng
                for i, item in enumerate(history):
                    self.history_table.insert(
                        "", "end", values=(
                            item['timestamp'],
                            item['passed'],
                            item['failed'],
                            item['total'],
                            f"{item['duration']:.2f}"
                        )
                    )
                    
            except Exception as e:
                logger.error(f"Lỗi khi tải lịch sử kiểm thử: {str(e)}")
                
    def save_test_history(self, session_results):
        """Lưu lịch sử kiểm thử"""
        history_path = os.path.join(DATA_DIR, "test_history.json")
        history = []
        
        # Tải lịch sử hiện tại nếu có
        if os.path.exists(history_path):
            try:
                with open(history_path, "r") as file:
                    history = json.load(file)
            except Exception as e:
                logger.error(f"Lỗi khi tải lịch sử kiểm thử: {str(e)}")
                
        # Chỉ lưu thông tin tổng hợp
        history_item = {
            'timestamp': session_results['timestamp'],
            'passed': session_results['passed'],
            'failed': session_results['failed'],
            'total': session_results['total'],
            'duration': session_results['duration']
        }
        
        # Thêm vào lịch sử
        history.append(history_item)
        
        # Lưu vào file
        try:
            # Đảm bảo thư mục tồn tại
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(history_path, "w") as file:
                json.dump(history, file, indent=4)
        except Exception as e:
            logger.error(f"Lỗi khi lưu lịch sử kiểm thử: {str(e)}")
            
        # Cập nhật bảng lịch sử
        self.load_test_history()
            
    def clear_test_history(self):
        """Xóa lịch sử kiểm thử"""
        if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa lịch sử kiểm thử?"):
            history_path = os.path.join(DATA_DIR, "test_history.json")
            
            try:
                # Tạo file mới với mảng rỗng
                with open(history_path, "w") as file:
                    json.dump([], file)
                    
                # Xóa các item trong bảng
                for item in self.history_table.get_children():
                    self.history_table.delete(item)
                    
                messagebox.showinfo("Thành công", "Đã xóa lịch sử kiểm thử")
                
                # Cập nhật biểu đồ
                self.update_charts()
                
            except Exception as e:
                logger.error(f"Lỗi khi xóa lịch sử kiểm thử: {str(e)}")
                messagebox.showerror("Lỗi", f"Không thể xóa lịch sử: {str(e)}")
                
    def generate_full_report(self, summary=False):
        """Tạo báo cáo đầy đủ"""
        if not self.test_results:
            messagebox.showinfo("Thông báo", "Chưa có kết quả kiểm thử để tạo báo cáo.")
            return
            
        try:
            # Tên báo cáo
            report_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_name = f"lazada_test_report_{'summary' if summary else 'full'}_{report_timestamp}"
            
            # Đảm bảo thư mục báo cáo tồn tại
            if not os.path.exists(REPORTS_DIR):
                os.makedirs(REPORTS_DIR)
                
            # Đường dẫn đầy đủ cho file báo cáo
            default_path = os.path.join(REPORTS_DIR, f"{report_name}.html")
            
            # Hỏi người dùng vị trí lưu báo cáo
            file_path = filedialog.asksaveasfilename(
                defaultextension=".html",
                filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
                initialdir=REPORTS_DIR,
                initialfile=f"{report_name}.html"
            )
            
            if not file_path:
                return
                
            # Lưu thư mục chứa báo cáo
            report_dir = os.path.dirname(file_path)
            
            # Tạo nội dung báo cáo
            html_content = self._generate_html_report(summary)
            
            # Lưu vào file
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(html_content)
                
            messagebox.showinfo("Thành công", f"Đã tạo báo cáo tại:\n{file_path}")
            
            # Mở báo cáo trong trình duyệt
            try:
                import webbrowser
                # Sử dụng file:/// để đảm bảo hoạt động trên mọi nền tảng
                file_url = "file:///" + os.path.abspath(file_path).replace("\\", "/")
                webbrowser.open(file_url)
            except Exception as browser_error:
                logger.warning(f"Không thể mở trình duyệt: {str(browser_error)}")
                # Thông báo cho người dùng vị trí file để họ có thể tự mở
                messagebox.showinfo("Thông báo", f"Có lỗi khi mở trình duyệt. Báo cáo đã được lưu tại:\n{file_path}")
        
        except Exception as e:
            logger.error(f"Lỗi khi tạo báo cáo: {str(e)}")
            messagebox.showerror("Lỗi", f"Không thể tạo báo cáo: {str(e)}")

    def _generate_html_report(self, summary=False):
        """Tạo nội dung HTML cho báo cáo"""
        try:
            # Đếm số test đạt và không đạt
            pass_count = sum(1 for r in self.test_results.values() if r.get('status') == 'Đạt')
            fail_count = sum(1 for r in self.test_results.values() if r.get('status') == 'Lỗi')
            total_count = len(self.test_results)
            
            # Tính tổng thời gian
            total_time = sum(r.get('time', 0) for r in self.test_results.values())
            
            # Tạo HTML
            html = f"""
            <!DOCTYPE html>
            <html lang="vi">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{'Tóm tắt' if summary else 'Báo cáo đầy đủ'} Kiểm thử Lazada</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        margin: 0;
                        padding: 20px;
                        color: #333;
                    }}
                    h1, h2, h3 {{
                        color: #2c3e50;
                    }}
                    .container {{
                        max-width: 1200px;
                        margin: 0 auto;
                    }}
                    .summary {{
                        background-color: #f8f9fa;
                        border-radius: 5px;
                        padding: 20px;
                        margin-bottom: 20px;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    }}
                    .stats {{
                        display: flex;
                        justify-content: space-around;
                        margin: 20px 0;
                    }}
                    .stat-item {{
                        text-align: center;
                        padding: 10px;
                        border-radius: 5px;
                    }}
                    .pass {{
                        background-color: #d4edda;
                        color: #155724;
                    }}
                    .fail {{
                        background-color: #f8d7da;
                        color: #721c24;
                    }}
                    .total {{
                        background-color: #cce5ff;
                        color: #004085;
                    }}
                    .time {{
                        background-color: #fff3cd;
                        color: #856404;
                    }}
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin: 20px 0;
                    }}
                    th, td {{
                        padding: 12px 15px;
                        text-align: left;
                        border-bottom: 1px solid #ddd;
                    }}
                    th {{
                        background-color: #f2f2f2;
                    }}
                    tr:hover {{
                        background-color: #f5f5f5;
                    }}
                    .status-pass {{
                        color: #28a745;
                        font-weight: bold;
                    }}
                    .status-fail {{
                        color: #dc3545;
                        font-weight: bold;
                    }}
                    .footer {{
                        margin-top: 30px;
                        text-align: center;
                        font-size: 0.9em;
                        color: #6c757d;
                    }}
                    .screenshot-container {{
                        display: grid;
                        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                        gap: 15px;
                        margin: 20px 0;
                    }}
                    .screenshot-item {{
                        border: 1px solid #ddd;
                        border-radius: 4px;
                        padding: 10px;
                        text-align: center;
                    }}
                    .screenshot-item img {{
                        max-width: 100%;
                        height: auto;
                        margin-bottom: 10px;
                    }}
                    .screenshot-item a {{
                        display: block;
                        color: #007bff;
                        text-decoration: none;
                        margin-top: 5px;
                    }}
                    .screenshot-item a:hover {{
                        text-decoration: underline;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>{'Tóm tắt' if summary else 'Báo cáo đầy đủ'} Kiểm thử Trang Web Lazada</h1>
                    <p>Ngày tạo báo cáo: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
                    
                    <div class="summary">
                        <h2>Tóm tắt kết quả</h2>
                        <div class="stats">
                            <div class="stat-item pass">
                                <h3>Đạt</h3>
                                <p>{pass_count}</p>
                            </div>
                            <div class="stat-item fail">
                                <h3>Lỗi</h3>
                                <p>{fail_count}</p>
                            </div>
                            <div class="stat-item total">
                                <h3>Tổng số</h3>
                                <p>{total_count}</p>
                            </div>
                            <div class="stat-item time">
                                <h3>Tổng thời gian</h3>
                                <p>{total_time/1000:.2f}s</p>
                            </div>
                        </div>
                    </div>
                    
                    <h2>Kết quả chi tiết</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>STT</th>
                                <th>Test ID</th>
                                <th>Tên Test</th>
                                <th>Trạng thái</th>
                                <th>Thời gian (ms)</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            
            # Thêm từng test
            for i, (test_id, result) in enumerate(self.test_results.items(), 1):
                status_class = "status-pass" if result.get('status') == 'Đạt' else "status-fail"
                # Escape các ký tự đặc biệt trong HTML
                test_name = result.get('name', '').replace('<', '&lt;').replace('>', '&gt;')
                test_status = result.get('status', '').replace('<', '&lt;').replace('>', '&gt;')
                
                html += f"""
                            <tr>
                                <td>{i}</td>
                                <td>{test_id}</td>
                                <td>{test_name}</td>
                                <td class="{status_class}">{test_status}</td>
                                <td>{result.get('time', '')}</td>
                            </tr>
                """
                
            html += """
                        </tbody>
                    </table>
            """
            
            # Nếu là báo cáo đầy đủ, thêm ảnh chụp màn hình
            if not summary:
                html += """
                    <h2>Ảnh chụp màn hình</h2>
                    <div class="screenshot-container">
                """
                
                # Tìm ảnh chụp màn hình
                try:
                    screenshot_files = sorted(
                        glob.glob(os.path.join(SCREENSHOTS_DIR, "*.png")),
                        key=os.path.getmtime, 
                        reverse=True
                    )[:8]  # Giới hạn chỉ 8 ảnh mới nhất để tránh báo cáo quá lớn
                    
                    # Tạo một thư mục riêng để sao chép các ảnh dùng trong báo cáo
                    report_name = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    report_img_dir = os.path.join(REPORTS_DIR, report_name)
                    os.makedirs(report_img_dir, exist_ok=True)
                    
                    # Thêm từng ảnh
                    for i, file in enumerate(screenshot_files):
                        try:
                            base_name = os.path.basename(file)
                            
                            # Sao chép ảnh vào thư mục báo cáo
                            import shutil
                            img_path = os.path.join(report_img_dir, base_name)
                            shutil.copy2(file, img_path)
                            
                            # Đường dẫn tương đối từ báo cáo HTML đến ảnh
                            relative_path = os.path.join(report_name, base_name).replace('\\', '/')
                            
                            # Thêm ảnh vào HTML với đường dẫn tương đối
                            html += f"""
                                <div class="screenshot-item">
                                    <img src="{relative_path}" alt="{base_name}" loading="lazy">
                                    <p>{base_name}</p>
                                    <a href="{relative_path}" target="_blank">Mở ảnh đầy đủ</a>
                                </div>
                            """
                        except Exception as img_err:
                            logger.warning(f"Lỗi khi xử lý ảnh {file}: {str(img_err)}")
                            continue
                            
                except Exception as e:
                    logger.warning(f"Lỗi khi tìm ảnh chụp màn hình: {str(e)}")
                    html += "<p>Không thể tải ảnh chụp màn hình: " + str(e).replace('<', '&lt;').replace('>', '&gt;') + "</p>"
                    
                html += """
                    </div>
                """
                
            html += """
                    <div class="footer">
                        <p>Báo cáo được tạo tự động bởi công cụ kiểm thử Lazada</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return html
            
        except Exception as e:
            logger.error(f"Lỗi khi tạo nội dung HTML: {str(e)}")
            # Trả về báo cáo đơn giản nếu có lỗi
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Báo cáo lỗi</title>
            </head>
            <body>
                <h1>Đã xảy ra lỗi khi tạo báo cáo</h1>
                <p>Chi tiết lỗi: {str(e).replace('<', '&lt;').replace('>', '&gt;')}</p>
            </body>
            </html>
            """
    
    def show_result_charts(self):
        """Hiển thị biểu đồ kết quả trong cửa sổ mới"""
        # Chuyển đến tab biểu đồ
        self.notebook.select(self.stats_tab)
        # Cập nhật biểu đồ
        self.update_charts()
        
    def show_history_charts(self):
        """Hiển thị biểu đồ lịch sử kiểm thử trong cửa sổ mới"""
        if not os.path.exists(os.path.join(DATA_DIR, "test_history.json")):
            messagebox.showinfo("Thông báo", "Chưa có dữ liệu lịch sử kiểm thử.")
            return
            
        try:
            # Tạo cửa sổ mới
            charts_window = tk.Toplevel(self.root)
            charts_window.title("Biểu đồ lịch sử kiểm thử")
            charts_window.geometry("800x600")
            charts_window.minsize(600, 400)
            
            # Tải dữ liệu lịch sử
            with open(os.path.join(DATA_DIR, "test_history.json"), "r") as file:
                history = json.load(file)
                
            if not history:
                ttk.Label(charts_window, text="Không có đủ dữ liệu lịch sử để hiển thị biểu đồ.",
                         font=("Arial", 12)).pack(pady=20)
                return
                
            # Tạo Frame cho biểu đồ
            charts_frame = ttk.Frame(charts_window)
            charts_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Biểu đồ tỉ lệ đạt theo thời gian
            fig = plt.Figure(figsize=(10, 8), dpi=100)
            
            # Trích xuất dữ liệu
            dates = [item['timestamp'] for item in history]
            pass_rates = [item['passed'] / item['total'] * 100 for item in history]
            durations = [item['duration'] for item in history]
            
            # Sắp xếp theo thời gian
            sorted_data = sorted(zip(dates, pass_rates, durations), key=lambda x: x[0])
            dates, pass_rates, durations = zip(*sorted_data)
            
# Biểu đồ đường tỉ lệ đạt
            ax1 = fig.add_subplot(211)
            ax1.set_title("Tỉ lệ đạt theo thời gian")
            ax1.set_xlabel("Ngày")
            ax1.set_ylabel("Tỉ lệ đạt (%)")
            ax1.plot(dates, pass_rates, marker='o', linestyle='-', color='blue')
            for i, txt in enumerate(pass_rates):
                ax1.annotate(f"{txt:.1f}%", (dates[i], pass_rates[i]), 
                            textcoords="offset points", xytext=(0,10), ha='center')
            ax1.grid(True, linestyle='--', alpha=0.7)
            ax1.tick_params(axis='x', rotation=45)
            
            # Biểu đồ cột thời gian chạy
            ax2 = fig.add_subplot(212)
            ax2.set_title("Thời gian chạy kiểm thử theo ngày")
            ax2.set_xlabel("Ngày")
            ax2.set_ylabel("Thời gian (giây)")
            bars = ax2.bar(dates, durations, color='orange')
            for bar in bars:
                height = bar.get_height()
                ax2.annotate(f"{height:.1f}s", xy=(bar.get_x() + bar.get_width()/2, height),
                            xytext=(0, 3), textcoords="offset points", ha='center', va='bottom')
            ax2.grid(True, linestyle='--', alpha=0.7, axis='y')
            ax2.tick_params(axis='x', rotation=45)
            
            fig.tight_layout()
            
            # Thêm biểu đồ vào giao diện
            canvas = FigureCanvasTkAgg(fig, charts_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Thêm toolbar
            from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
            toolbar = NavigationToolbar2Tk(canvas, charts_frame)
            toolbar.update()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
        except Exception as e:
            logger.error(f"Lỗi khi hiển thị biểu đồ lịch sử: {str(e)}")
            messagebox.showerror("Lỗi", f"Không thể hiển thị biểu đồ: {str(e)}")
    
    def show_settings(self):
        """Hiển thị cửa sổ cài đặt"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Cài đặt")
        settings_window.geometry("500x400")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        settings_frame = ttk.Frame(settings_window, padding=20)
        settings_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(settings_frame, text="Cài đặt", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        # Phần Hiển thị
        ttk.Label(settings_frame, text="Hiển thị", font=("Arial", 12, "bold")).grid(row=1, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        ttk.Label(settings_frame, text="Ngôn ngữ giao diện:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        lang_var = tk.StringVar(value="Tiếng Việt")
        ttk.Combobox(settings_frame, textvariable=lang_var, values=["Tiếng Việt", "English"], state="readonly").grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        
        ttk.Label(settings_frame, text="Giao diện:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        theme_var = tk.StringVar(value="Sáng")
        ttk.Combobox(settings_frame, textvariable=theme_var, values=["Sáng", "Tối", "Hệ thống"], state="readonly").grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Phần Thư mục
        ttk.Label(settings_frame, text="Thư mục", font=("Arial", 12, "bold")).grid(row=4, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        ttk.Label(settings_frame, text="Thư mục ảnh chụp:").grid(row=5, column=0, padx=5, pady=5, sticky=tk.W)
        screenshot_dir = tk.StringVar(value=SCREENSHOTS_DIR)
        dir_frame = ttk.Frame(settings_frame)
        dir_frame.grid(row=5, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(dir_frame, textvariable=screenshot_dir, width=30).pack(side=tk.LEFT)
        ttk.Button(dir_frame, text="...", width=3, 
                  command=lambda: screenshot_dir.set(filedialog.askdirectory(initialdir=screenshot_dir.get()))).pack(side=tk.LEFT, padx=5)
        
        # Phần Kiểm thử
        ttk.Label(settings_frame, text="Kiểm thử", font=("Arial", 12, "bold")).grid(row=6, column=0, columnspan=2, pady=10, sticky=tk.W)
        
        auto_save_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Tự động lưu báo cáo sau mỗi lần kiểm thử", 
                       variable=auto_save_var).grid(row=7, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        
        auto_clean_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text="Tự động xóa ảnh chụp màn hình cũ (>30 ngày)", 
                       variable=auto_clean_var).grid(row=8, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        
        # Nút điều khiển
        button_frame = ttk.Frame(settings_frame)
        button_frame.grid(row=9, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Lưu", command=settings_window.destroy).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Hủy", command=settings_window.destroy).pack(side=tk.LEFT, padx=10)
    
    def check_updates(self):
        """Kiểm tra bản cập nhật mới"""
        # Giả lập kiểm tra cập nhật
        import random
        
        update_window = tk.Toplevel(self.root)
        update_window.title("Kiểm tra cập nhật")
        update_window.geometry("400x200")
        update_window.transient(self.root)
        update_window.grab_set()
        
        update_frame = ttk.Frame(update_window, padding=20)
        update_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(update_frame, text="Đang kiểm tra cập nhật...", 
                 font=("Arial", 12)).pack(pady=10)
        
        progress = ttk.Progressbar(update_frame, mode="indeterminate", length=300)
        progress.pack(pady=10)
        progress.start()
        
        # Giả lập kiểm tra cập nhật sau 2 giây
        def check():
            progress.stop()
            progress.pack_forget()
            
            if random.random() > 0.5:  # Giả sử có cập nhật
                ttk.Label(update_frame, text="Đã tìm thấy bản cập nhật mới!", 
                         font=("Arial", 12, "bold"), foreground="green").pack(pady=10)
                ttk.Label(update_frame, text="Phiên bản: 2.0.0\nNgày phát hành: 01/03/2025").pack()
                ttk.Button(update_frame, text="Tải về", 
                          command=lambda: messagebox.showinfo("Thông báo", "Đã bắt đầu tải bản cập nhật.")).pack(pady=10)
            else:  # Không có cập nhật
                ttk.Label(update_frame, text="Bạn đang sử dụng phiên bản mới nhất!", 
                         font=("Arial", 12, "bold")).pack(pady=10)
                ttk.Label(update_frame, text="Phiên bản hiện tại: 1.0.0").pack()
                ttk.Button(update_frame, text="Đóng", 
                          command=update_window.destroy).pack(pady=10)
                
        update_frame.after(2000, check)
    
    def show_help(self):
        """Hiển thị hướng dẫn sử dụng"""
        help_window = tk.Toplevel(self.root)
        help_window.title("Hướng dẫn sử dụng")
        help_window.geometry("700x500")
        help_window.transient(self.root)
        
        help_frame = ttk.Frame(help_window, padding=20)
        help_frame.pack(fill=tk.BOTH, expand=True)
        
        # Tạo notebook để phân trang hướng dẫn
        help_notebook = ttk.Notebook(help_frame)
        help_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Trang tổng quan
        overview_frame = ttk.Frame(help_notebook, padding=10)
        help_notebook.add(overview_frame, text="Tổng quan")
        
        ttk.Label(overview_frame, text="Hướng dẫn sử dụng công cụ kiểm thử Lazada", 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        overview_text = tk.Text(overview_frame, wrap=tk.WORD, height=20)
        overview_text.pack(fill=tk.BOTH, expand=True)
        overview_text.insert(tk.END, """
Công cụ kiểm thử tự động Lazada là ứng dụng giúp bạn thực hiện kiểm thử tự động cho trang web Lazada.vn. 
Ứng dụng sử dụng Playwright để tự động hóa các thao tác trên trình duyệt.

Các tính năng chính:
- Kiểm thử tự động các chức năng chính của website: trang chủ, tìm kiếm, giỏ hàng, ...
- Xem kết quả kiểm thử và ảnh chụp màn hình
- Tạo báo cáo chi tiết
- Theo dõi lịch sử kiểm thử
- Biểu đồ trực quan hóa kết quả

Các tab chính:
1. Tab Kiểm thử: Thực hiện kiểm thử và xem kết quả
2. Tab Biểu đồ & Thống kê: Xem biểu đồ thống kê kết quả
3. Tab Cấu hình: Thiết lập cấu hình kiểm thử
4. Tab Lịch sử: Xem lịch sử các lần kiểm thử trước đó
        """)
        overview_text.config(state=tk.DISABLED)
        
        # Trang hướng dẫn kiểm thử
        testing_frame = ttk.Frame(help_notebook, padding=10)
        help_notebook.add(testing_frame, text="Kiểm thử")
        
        ttk.Label(testing_frame, text="Hướng dẫn thực hiện kiểm thử", 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        testing_text = tk.Text(testing_frame, wrap=tk.WORD, height=20)
        testing_text.pack(fill=tk.BOTH, expand=True)
        testing_text.insert(tk.END, """
Thực hiện kiểm thử:
1. Trong tab "Kiểm thử", nhấn nút "Chạy tất cả" để thực hiện toàn bộ các test case
2. Chọn "Chạy ẩn trình duyệt" để chạy kiểm thử mà không hiển thị trình duyệt
3. Nhấn "Dừng" để hủy quá trình kiểm thử

Xem kết quả:
1. Các test được hiển thị trong danh sách cùng với trạng thái và thời gian thực hiện
2. Nhấp vào một test để xem ảnh chụp màn hình liên quan
3. Sử dụng menu "File > Mở báo cáo HTML" để xem báo cáo chi tiết

Báo cáo và xuất kết quả:
1. Sử dụng menu "Báo cáo" để tạo báo cáo đầy đủ hoặc tóm tắt
2. Sử dụng menu "File > Xuất kết quả ra Excel" để xuất kết quả kiểm thử dạng Excel
        """)
        testing_text.config(state=tk.DISABLED)
        
        # Trang cấu hình
        config_frame = ttk.Frame(help_notebook, padding=10)
        help_notebook.add(config_frame, text="Cấu hình")
        
        ttk.Label(config_frame, text="Hướng dẫn cấu hình", 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        config_text = tk.Text(config_frame, wrap=tk.WORD, height=20)
        config_text.pack(fill=tk.BOTH, expand=True)
        config_text.insert(tk.END, """
Trong tab "Cấu hình", bạn có thể tùy chỉnh các thông số kiểm thử:

1. URL trang web: Địa chỉ trang web cần kiểm thử (mặc định là https://www.lazada.vn/)
2. Từ khóa tìm kiếm: Từ khóa dùng để tìm kiếm sản phẩm trong quá trình kiểm thử
3. Tùy chọn kiểm thử:
   - Chạy ẩn trình duyệt: Chạy kiểm thử mà không hiển thị giao diện trình duyệt
   - Hiển thị trình duyệt trong danh sách tác vụ: Cho phép thấy các trình duyệt đang chạy kiểm thử
   - Tự động mở báo cáo: Tự động mở báo cáo HTML sau khi kiểm thử hoàn tất
4. Thời gian chờ: Thời gian chờ tối đa cho mỗi thao tác (tính bằng giây)
5. Số lần thử lại: Số lần thử lại khi một test bị lỗi

Lưu ý:
- Nhấn "Lưu cấu hình" để lưu lại các thay đổi
- Nhấn "Khôi phục mặc định" để trở về cấu hình mặc định
- Cấu hình được lưu trong file config.json và sẽ được áp dụng cho các lần kiểm thử tiếp theo
        """)
        config_text.config(state=tk.DISABLED)
        
        # Nút đóng
        ttk.Button(help_frame, text="Đóng", 
                  command=help_window.destroy).pack(pady=10)
    
    def show_about(self):
        """Hiển thị thông tin về ứng dụng"""
        about_window = tk.Toplevel(self.root)
        about_window.title("Giới thiệu")
        about_window.geometry("400x300")
        about_window.transient(self.root)
        about_window.grab_set()
        
        about_frame = ttk.Frame(about_window, padding=20)
        about_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(about_frame, text="Công cụ kiểm thử tự động Lazada", 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        ttk.Label(about_frame, text="Phiên bản 1.0.0").pack()
        ttk.Label(about_frame, text="© 2025 Kiểm thử tự động").pack()
        
        ttk.Separator(about_frame, orient="horizontal").pack(fill="x", pady=10)
        
        ttk.Label(about_frame, text="""
Công cụ kiểm thử tự động sử dụng Playwright và Python 
để thực hiện kiểm thử các chức năng của trang web Lazada.

Công nghệ sử dụng:
- Python 3.8+
- Playwright
- Tkinter
- Pytest
- Matplotlib
        """, justify="center").pack(pady=10)
        
        ttk.Button(about_frame, text="Đóng", 
                  command=about_window.destroy).pack(pady=10)


# Hàm main để chạy ứng dụng
def main():
    root = tk.Tk()
    app = LazadaTestGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()