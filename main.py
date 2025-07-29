import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import os
import json
import hashlib
import datetime # For date stamping projects
import subprocess # For opening files cross-platform
import shutil # For file copying (for 'Upload' functionality)
import threading # For non-blocking operations
from PIL import Image, ImageTk # Import Pillow for image handling
import calendar # For calendar logic
import uuid # For generating unique IDs for requirement blocks

# --- NEW: Import your database module ---
from rings_database import RingspanDatabase, DATABASE_NAME # Import the class and the database name

# --- Encryption Imports ---
from cryptography.fernet import Fernet, InvalidToken

# --- ReportLab Imports for PDF Generation ---
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as ReportLabImage, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.colors import black, blue, red # Example colors, can be expanded

class DatePicker:
    """A simple date picker widget for Tkinter."""
    def __init__(self, master, date_entry_var, on_date_selected_callback=None): # Added callback
        self.master = master
        self.date_entry_var = date_entry_var # StringVar to update in the main app
        self.on_date_selected_callback = on_date_selected_callback # Store callback

        self.top = tk.Toplevel(master)
        self.top.title("Select Date")
        self.top.transient(master) # Make it appear on top of the main window
        self.top.grab_set() # Make it modal
        self.top.resizable(False, False)

        # Center the Toplevel window
        master_x = master.winfo_x()
        master_y = master.winfo_y()
        master_width = master.winfo_width()
        master_height = master.winfo_height()

        self.top.update_idletasks() # Ensure window dimensions are available
        top_width = self.top.winfo_width()
        top_height = self.top.winfo_height()

        x = master_x + (master_width // 2) - (top_width // 2)
        y = master_y + (master_height // 2) - (top_height // 2)
        self.top.geometry(f"+{x}+{y}")

        self.current_date = datetime.date.today()
        self.selected_day = tk.StringVar(value=str(self.current_date.day))
        self.selected_month = tk.StringVar(value=calendar.month_name[self.current_date.month])
        self.selected_year = tk.StringVar(value=str(self.current_date.year))

        self._build_calendar_ui()
        self._show_calendar()

    def _build_calendar_ui(self):
        """Builds the UI elements for the date picker."""
        # Month and Year selection
        control_frame = ttk.Frame(self.top, padding="10 10 10 0")
        control_frame.pack(fill=tk.X)

        # Month Combobox
        months = [calendar.month_name[i] for i in range(1, 13)]
        self.month_combobox = ttk.Combobox(control_frame, textvariable=self.selected_month, values=months, state="readonly", width=10)
        self.month_combobox.pack(side=tk.LEFT, padx=5, pady=5)
        self.month_combobox.bind("<<ComboboxSelected>>", self._on_month_year_change)

        # Year Combobox
        current_year = datetime.date.today().year
        years = [str(y) for y in range(current_year - 10, current_year + 11)] # +/- 10 years
        self.year_combobox = ttk.Combobox(control_frame, textvariable=self.selected_year, values=years, state="readonly", width=7)
        self.year_combobox.pack(side=tk.LEFT, padx=5, pady=5)
        self.year_combobox.bind("<<ComboboxSelected>>", self._on_month_year_change)

        # Navigation buttons
        ttk.Button(control_frame, text="<", command=self._prev_month, width=3).pack(side=tk.LEFT, padx=(10,0), pady=5)
        ttk.Button(control_frame, text=">", command=self._next_month, width=3).pack(side=tk.LEFT, padx=5, pady=5)

        # Day grid frame
        self.day_grid_frame = ttk.Frame(self.top, padding=10)
        self.day_grid_frame.pack()

        # Weekday labels
        for i, day in enumerate(calendar.day_abbr):
            ttk.Label(self.day_grid_frame, text=day, width=4, anchor="center", font=("Arial", 9, "bold")).grid(row=0, column=i, padx=1, pady=1)

        # OK/Cancel buttons
        button_frame = ttk.Frame(self.top, padding="0 0 0 10")
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="OK", command=self._confirm_selection).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.top.destroy).pack(side=tk.RIGHT)

    def _on_month_year_change(self, event=None):
        """Updates the calendar when month or year combobox changes."""
        try:
            month_num = list(calendar.month_name).index(self.selected_month.get())
            year_num = int(self.selected_year.get())
            self.current_date = datetime.date(year_num, month_num, 1) # Set to 1st of new month/year
            self._show_calendar()
        except ValueError:
            pass # Handle invalid selections if necessary

    def _prev_month(self):
        """Navigates to the previous month."""
        first_day_of_current_month = self.current_date.replace(day=1)
        prev_month_last_day = first_day_of_current_month - datetime.timedelta(days=1)
        self.current_date = prev_month_last_day.replace(day=1) # Set to 1st of previous month
        self.selected_month.set(calendar.month_name[self.current_date.month])
        self.selected_year.set(str(self.current_date.year))
        self._show_calendar()

    def _next_month(self):
        """Navigates to the next month."""
        days_in_current_month = calendar.monthrange(self.current_date.year, self.current_date.month)[1]
        last_day_of_current_month = self.current_date.replace(day=days_in_current_month)
        next_month_first_day = last_day_of_current_month + datetime.timedelta(days=1)
        self.current_date = next_month_first_day.replace(day=1) # Set to 1st of next month
        self.selected_month.set(calendar.month_name[self.current_date.month])
        self.selected_year.set(str(self.current_date.year))
        self._show_calendar()

    def _show_calendar(self):
        """Populates the day grid with dates for the current month."""
        # Clear existing day buttons
        for widget in self.day_grid_frame.winfo_children():
            if widget.grid_info()['row'] > 0: # Keep weekday labels
                widget.destroy()

        year = self.current_date.year
        month = self.current_date.month

        cal = calendar.Calendar()
        month_days = cal.monthdayscalendar(year, month)

        row_offset = 1 # Start days from row 1 (after weekday labels)
        for week in month_days:
            for col, day_num in enumerate(week):
                if day_num != 0: # 0 means day is not in this month
                    day_button = ttk.Button(self.day_grid_frame, text=str(day_num), width=4,
                                            command=lambda d=day_num: self._select_day(d))
                    day_button.grid(row=row_offset, column=col, padx=1, pady=1)
                    if day_num == int(self.selected_day.get()) and \
                       month == list(calendar.month_name).index(self.selected_month.get()) and \
                       year == int(self.selected_year.get()):
                        day_button.state(['pressed']) # Indicate selected day
                else:
                    # Place an empty label for padding for days outside the month
                    ttk.Label(self.day_grid_frame, text="", width=4).grid(row=row_offset, column=col, padx=1, pady=1)
            row_offset += 1

    def _select_day(self, day_num):
        """Sets the selected day and updates the current_date."""
        self.selected_day.set(str(day_num))
        month_num = list(calendar.month_name).index(self.selected_month.get())
        year_num = int(self.selected_year.get())
        self.current_date = datetime.date(year_num, month_num, day_num)

        # Visually update selected day (clear previous, highlight new)
        for widget in self.day_grid_frame.winfo_children():
            if isinstance(widget, ttk.Button):
                widget.state(['!pressed'])
                if widget['text'] == str(day_num):
                    widget.state(['pressed'])

    def _confirm_selection(self):
        """Confirms the selected date and updates the main application."""
        try:
            day = int(self.selected_day.get())
            month = list(calendar.month_name).index(self.selected_month.get())
            year = int(self.selected_year.get())
            selected_date_obj = datetime.date(year, month, day)
            self.date_entry_var.set(selected_date_obj.isoformat()) # Update StringVar in main app
            if self.on_date_selected_callback: # Call the callback
                self.on_date_selected_callback()
            self.top.destroy()
        except ValueError:
            messagebox.showerror("Invalid Date", "Please select a valid date.")


class CustomerRequirementBlock(tk.Frame):
    """
    A self-contained UI block for a single customer product requirement.
    Allows selecting a product type and filling in its specific parameters.
    """
    def __init__(self, master, app_instance, block_id, initial_data=None):
        super().__init__(master, bg="white", padx=15, pady=15, bd=1, relief=tk.SOLID)
        self.app = app_instance # Reference back to the main app instance
        self.block_id = block_id
        self.product_type_options = self.app.product_type_options
        self.product_parameters = self.app.product_parameters
        self.dynamic_entries = {} # Stores Entry widgets for this specific block
        
        # Determine initial product type
        if initial_data and "selected_product_type" in initial_data:
            initial_product_type = initial_data["selected_product_type"]
        elif self.product_type_options:
            initial_product_type = self.product_type_options[0] # Default to first option
        else:
            initial_product_type = "Choose part type" # Fallback if no options

        self.selected_product_type = tk.StringVar(self, value=initial_product_type)

        self._build_ui()
        if initial_data:
            self._load_initial_data(initial_data)
        
        # Bind the product type selection to update fields
        self.selected_product_type.trace_add("write", self._update_dynamic_fields)

    def _build_ui(self):
        """Builds the UI elements for this requirement block."""
        self.columnconfigure(0, weight=1) # For the title/dropdown row
        self.columnconfigure(1, weight=0) # For the delete button

        # Title and Delete button
        title_frame = tk.Frame(self, bg="white")
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        title_frame.columnconfigure(0, weight=1) # For the label
        title_frame.columnconfigure(1, weight=0) # For the dropdown

        self.block_title_label = tk.Label(title_frame, text=f"Customer Requirement {self.app._get_next_requirement_number()}",
                                          font=("Arial", 12, "bold"), bg="white", fg="black")
        self.block_title_label.grid(row=0, column=0, sticky="w")

        self.delete_button = tk.Button(self, text="Delete", command=self._delete_self, font=("Arial", 9))
        self.delete_button.grid(row=0, column=1, padx=5, sticky="ne")

        # Product Type Dropdown
        tk.Label(title_frame, text="Select Part Type:", font=("Arial", 10), bg="white", fg="black").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.product_type_dropdown = ttk.OptionMenu(title_frame, self.selected_product_type, self.selected_product_type.get(), *self.product_type_options)
        self.product_type_dropdown.config(width=30) # Adjust width as needed
        self.product_type_dropdown.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # Frame to hold dynamic input fields
        self.dynamic_fields_container = tk.Frame(self, bg="white")
        self.dynamic_fields_container.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.dynamic_fields_container.columnconfigure(1, weight=1) # Allow entry fields to expand

    def _load_initial_data(self, data):
        """Loads data into the block's UI fields."""
        if "selected_product_type" in data:
            self.selected_product_type.set(data["selected_product_type"])
            # _update_dynamic_fields will be called by the trace, populating fields
            # after the dropdown value is set.
        
        # If there are parameters, populate them after fields are created
        if "parameters" in data:
            # We need to ensure fields are created before populating
            # This is handled by _update_dynamic_fields being traced to selected_product_type.set()
            # So, after the trace fires, we can then populate the values.
            self.after(10, lambda: self._populate_fields_from_data(data["parameters"]))


    def _populate_fields_from_data(self, parameters):
        """Populates the dynamic entry fields with provided data."""
        for label, entry_widget in self.dynamic_entries.items():
            if label in parameters:
                entry_widget.delete(0, tk.END)
                entry_widget.insert(0, parameters[label])

    def _update_dynamic_fields(self, *args):
        """Dynamically creates/updates input fields based on selected product type."""
        # Clear existing dynamic fields
        for widget in self.dynamic_fields_container.winfo_children():
            widget.destroy()
        self.dynamic_entries = {} # Clear references

        selected_type = self.selected_product_type.get()
        if selected_type == "Choose part type":
            return # No product selected, no fields to show

        fields_to_create = self.product_parameters.get(selected_type, [])
        
        row_idx = 0
        for field_def in fields_to_create:
            label_text = field_def["label"]
            field_type = field_def["type"]
            validation_type = field_def.get("validation")

            row_frame = tk.Frame(self.dynamic_fields_container, bg="white")
            row_frame.grid(row=row_idx, column=0, sticky="ew", pady=2, columnspan=2)
            row_frame.columnconfigure(1, weight=1)

            tk.Label(row_frame, text=f"{label_text}:", font=("Arial", 10), bg="white", fg="black").grid(row=0, column=0, padx=5, sticky="w")
            
            if field_type == "entry":
                if validation_type == "numeric":
                    entry = tk.Entry(row_frame, width=50, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black",
                                     validate="key", validatecommand=(self.app.vcmd_numeric, '%P'))
                else:
                    entry = tk.Entry(row_frame, width=50, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black")
                
                entry.grid(row=0, column=1, padx=5, sticky="ew")
                self.dynamic_entries[label_text] = entry
                # Bind focus out to trigger auto-save for this entry
                entry.bind("<FocusOut>", lambda e: self.app._save_project())
            
            row_idx += 1

    def _delete_self(self):
        """Calls the main app to delete this block."""
        self.app._delete_customer_requirement_block(self.block_id)

    def get_data(self):
        """Returns the data collected in this block."""
        selected_type = self.selected_product_type.get()
        if selected_type == "Choose part type":
            return None # Don't save if no product type is selected

        parameters = {}
        for label, entry_widget in self.dynamic_entries.items():
            parameters[label] = entry_widget.get().strip()

        return {
            "id": self.block_id,
            "selected_product_type": selected_type,
            "parameters": parameters
        }
    
    def update_title(self, new_number):
        """Updates the title of the block (e.g., Customer Requirement 1, 2, etc.)."""
        self.block_title_label.config(text=f"Customer Requirement {new_number}")


class RingspanApp:
    def __init__(self, master):
        print("DEBUG: RingspanApp __init__ method started.")
        self.master = master
        self.master.title("Ringspan Quote Generator")
        self.master.geometry("1024x768") # Set initial window size
        self.master.resizable(True, True) # Allow window resizing
        self.master.config(bg="#F0F0F0") # Overall window background - very light grey

        # --- File Paths ---
        self.current_project_file_path = None
        self.script_dir = os.path.dirname(__file__)
        self.logo_path = os.path.join(self.script_dir, "ringspann_logo.png") # Path to your logo file
        self.ENCRYPTION_KEY_FILE = os.path.join(self.script_dir, "encryption.key") # Path for encryption key

        # --- NEW: Initialize Database Manager ---
        self.db_manager = RingspanDatabase(os.path.join(self.script_dir, DATABASE_NAME))
        if not self.db_manager.conn:
            messagebox.showerror("Database Error", "Could not connect to the database. Exiting.")
            self.master.destroy()
            return

        # --- Load logo image for Tkinter UI ---
        self.ringspann_logo_tk = None # Initialize to None first
        self._load_ringspann_logo() # Call this early to load the image

        # --- Initialize Fernet Cipher ---
        self.fernet_cipher = self._get_fernet_cipher()
        if self.fernet_cipher is None:
            messagebox.showerror("Encryption Error", "Could not initialize encryption. Exiting.")
            self.master.destroy()
            return

        # --- Internal Data Structures ---
        self.current_project_data = {} 
        self.current_user_email = None # Store email instead of full user dict
        self.current_user_recent_files = [] # This will still be a list of file paths
        self.RECENT_FILES_MAX = 5 # Maximum number of recent files to display
        self.recent_projects_visible = False # Track visibility of recent projects section
        self.customer_requirement_blocks = [] # List to hold CustomerRequirementBlock instances

        # --- Setup UI Frames ---
        self.auth_frame = tk.Frame(self.master, padx=30, pady=30, bg="#F0F0F0")
        self.project_selection_frame = tk.Frame(self.master, padx=30, pady=30, bg="#F0F0F0")
        self.quotation_setup_frame = tk.Frame(self.master, padx=30, pady=30, bg="#F0F0F0") # New frame for quotation number input
        self.main_app_frame = tk.Frame(self.master, padx=15, pady=15, bg="#F0F0F0") # This is now the Customer Requirements screen
        self.commercial_quote_frame = tk.Frame(self.master, padx=15, pady=15, bg="#F0F0F0") # New frame for commercial quote UI
        self.technical_quote_frame = tk.Frame(self.master, padx=15, pady=15, bg="#F0F0F0") # New frame for technical quote UI

        # --- Map Product Types to Actual File Names ---
        self.quotation_file_map = {
            "Backstop Quotation": "Backstop Quotation .xlsx - Backstop (2).csv",
            "Brake Quotation": "Brake Quotation .xlsx",
            "Coupling and Torque Limiter Quotation": "Coupling and Torque Limiter Quotation .xlsx"
        }
        self.product_type_options = list(self.quotation_file_map.keys())
        
        # Dictionary to hold references to the dynamically created product parameters
        # This is now used by CustomerRequirementBlock
        self.product_parameters = {
            "Coupling and Torque Limiter Quotation": [
                {"label": "SL No.", "type": "entry"},
                {"label": "Tag Number", "type": "entry"},
                {"label": "Application", "type": "entry"},
                {"label": "Motor KW", "type": "entry"},
                {"label": "Number of Drive", "type": "entry"},
                {"label": "Torque (Mn) Min (Nm)", "type": "entry"},
                {"label": "Torque (Mn) Max (Nm)", "type": "entry"},
                {"label": "Speed at Coupling Min (RPM)", "type": "entry"},
                {"label": "Speed at Coupling Rated (RPM)", "type": "entry"},
                {"label": "Speed at Coupling Max (RPM)", "type": "entry"},
                {"label": "Service Factor", "type": "entry"},
            ],
            "Backstop Quotation": [
                {"label": "SL No.", "type": "entry"},
                {"label": "Tag Number", "type": "entry"},
                {"label": "Application", "type": "entry"},
                {"label": "Shaft Diameter (mm)", "type": "entry"},
                {"label": "Torque (Mn) Min (Nm)", "type": "entry"},
                {"label": "Torque (Mn) Max (Nm)", "type": "entry"},
                {"label": "Speed Min (RPM)", "type": "entry"},
                {"label": "Speed Rated (RPM)", "type": "entry"},
                {"label": "Speed Max (RPM)", "type": "entry"},
                {"label": "Operating Hours (daily)", "type": "entry"},
                {"label": "Service Factor", "type": "entry"},
            ],
            "Brake Quotation": [ 
                {"label": "SL No.", "type": "entry"},
                {"label": "Tag Number", "type": "entry"},
                {"label": "Application", "type": "entry"},
                {"label": "Motor KW", "type": "entry"},
                {"label": "Number of Drive", "type": "entry"},
                {"label": "Stopping Torque (Mn) Min (Nm)", "type": "entry"},
                {"label": "Stopping Torque (Mn) Max (Nm)", "type": "entry"},
                {"label": "Speed at Brake Min (RPM)", "type": "entry"},
                {"label": "Speed at Brake Rated (RPM)", "type": "entry"},
                {"label": "Speed at Brake Max (RPM)", "type": "entry", "validation": "numeric"}, 
                {"label": "Number of Braking Per Second", "type": "entry", "validation": "numeric"}, 
                {"label": "Number of Braking Per Hour", "type": "entry", "validation": "numeric"},   
                {"label": "Number of Braking Per Day", "type": "entry", "validation": "numeric"},    
                {"label": "Service Factor", "type": "entry"},
            ]
        }
        
        self.commercial_quote_entries = {} # To store references to commercial quote Entry widgets
        self.commercial_quote_table_data = [] # To store table data

        # Technical quote data structures
        self.technical_quote_entries = {} # To store references to technical quote Entry widgets
        self.technical_quote_table_data = [] # To store technical table data

        # StringVar for the date entry in commercial quote UI
        self.commercial_quote_date_var = tk.StringVar(self.master, value=datetime.date.today().isoformat())
        # NEW: StringVar for the inquiry date entry in commercial quote UI
        self.commercial_quote_inquiry_date_var = tk.StringVar(self.master, value=datetime.date.today().isoformat())

        # StringVar for the date entry in technical quote UI
        self.technical_quote_date_var = tk.StringVar(self.master, value=datetime.date.today().isoformat())
        # StringVar for the inquiry date entry in technical quote UI
        self.technical_quote_inquiry_date_var = tk.StringVar(self.master, value=datetime.date.today().isoformat())

        # --- Configure ttk Styles for minimalist look ---
        self._configure_ttk_styles()

        # --- Build UI Components ---
        self._build_auth_ui()
        self._build_project_selection_ui()
        self._build_quotation_setup_ui() # New quotation setup UI
        self._build_main_app_ui() # This is now the Customer Requirements UI
        self._build_commercial_quote_ui() # Build the new commercial quote UI
        self._build_technical_quote_ui() # Build the new technical quote UI

        # Register validation command for numerical input
        self.vcmd_numeric = self.master.register(self._validate_numeric_input)
        
        # Pack the authentication frame initially
        self.auth_frame.pack(expand=True, fill='both', padx=50, pady=50) # Added padding for auth frame

        # Variables for in-cell editing
        self._edit_cell_entry = None
        self._edit_cell_item = None
        self._edit_cell_column = None
        
        # Variables for technical quote in-cell editing
        self._edit_tech_cell_entry = None
        self._edit_tech_cell_item = None
        self._edit_tech_cell_column = None
        print("DEBUG: RingspanApp __init__ method finished.")

    # Add all the existing methods here (truncated for brevity)
    # I'll add the key technical quotation methods

    def _build_technical_quote_ui(self):
        """Builds the UI for the Technical Quote screen."""
        self.technical_quote_frame.columnconfigure(0, weight=1)
        self.technical_quote_frame.rowconfigure(0, weight=0) # Header
        self.technical_quote_frame.rowconfigure(1, weight=0) # Top details
        self.technical_quote_frame.rowconfigure(2, weight=1) # Table
        self.technical_quote_frame.rowconfigure(3, weight=0) # Table buttons
        self.technical_quote_frame.rowconfigure(4, weight=0) # Bottom buttons

        # Header with Back button and Logo
        header_frame = tk.Frame(self.technical_quote_frame, bg="#F0F0F0")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.columnconfigure(0, weight=1)
        header_frame.columnconfigure(1, weight=1)
        header_frame.columnconfigure(2, weight=1)

        # Back button to go back to Customer Requirements screen
        self.btn_back_technical_quote = tk.Button(header_frame, text="< Back", command=self._show_main_app_screen, font=("Arial", 10))
        self.btn_back_technical_quote.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        tk.Label(header_frame, text="RINGSPANN Power Transmission India Pvt. Ltd.", font=("Arial", 14, "bold"), bg="#F0F0F0", fg="grey").grid(row=0, column=1, pady=5)
        
        # Replace [LOGO] with actual image if loaded
        if self.ringspann_logo_tk:
            self.tech_logo_label = tk.Label(header_frame, image=self.ringspann_logo_tk, bg="#F0F0F0")
            self.tech_logo_label.grid(row=0, column=2, padx=10, pady=5, sticky="e")
        else:
            self.tech_logo_label = tk.Label(header_frame, text="[LOGO]", font=("Arial", 12), bg="#F0F0F0", fg="grey")
            self.tech_logo_label.grid(row=0, column=2, padx=10, pady=5, sticky="e")

        tk.Label(self.technical_quote_frame, text="Technical Quotation", font=("Arial", 16, "bold"), bg="#F0F0F0", fg="black").grid(row=0, column=0, columnspan=2, pady=(40, 10), sticky="n")

        # Top Details Frame
        top_details_frame = tk.Frame(self.technical_quote_frame, bg="white", padx=20, pady=10, bd=1, relief=tk.SOLID)
        top_details_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        top_details_frame.columnconfigure(1, weight=1)
        top_details_frame.columnconfigure(3, weight=1)

        # Left Column
        tk.Label(top_details_frame, text="To:", font=("Arial", 10), bg="white", fg="black").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.technical_quote_entries["To"] = tk.Entry(top_details_frame, width=30, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black")
        self.technical_quote_entries["To"].grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.technical_quote_entries["To"].bind("<FocusOut>", lambda e: self._save_technical_quote_data_auto())

        tk.Label(top_details_frame, text="Attn.:", font=("Arial", 10), bg="white", fg="black").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.technical_quote_entries["Attn."] = tk.Entry(top_details_frame, width=30, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black")
        self.technical_quote_entries["Attn."].grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        self.technical_quote_entries["Attn."].bind("<FocusOut>", lambda e: self._save_technical_quote_data_auto())

        tk.Label(top_details_frame, text="E-mail (To):", font=("Arial", 10), bg="white", fg="black").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.technical_quote_entries["E-mail (To)"] = tk.Entry(top_details_frame, width=30, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black")
        self.technical_quote_entries["E-mail (To)"].grid(row=2, column=1, padx=5, pady=2, sticky="ew")
        self.technical_quote_entries["E-mail (To)"].bind("<FocusOut>", lambda e: self._save_technical_quote_data_auto())

        tk.Label(top_details_frame, text="Your Inquiry Ref.:", font=("Arial", 10), bg="white", fg="black").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        self.technical_quote_entries["Your Inquiry Ref."] = tk.Entry(top_details_frame, width=30, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black")
        self.technical_quote_entries["Your Inquiry Ref."].grid(row=3, column=1, padx=5, pady=2, sticky="ew")
        self.technical_quote_entries["Your Inquiry Ref."].bind("<FocusOut>", lambda e: self._save_technical_quote_data_auto())

        # Inquiry Date Entry with Select Date Button
        tk.Label(top_details_frame, text="Inquiry Date:", font=("Arial", 10), bg="white", fg="black").grid(row=4, column=0, padx=5, pady=2, sticky="w")
        inquiry_date_input_frame = tk.Frame(top_details_frame, bg="white")
        inquiry_date_input_frame.grid(row=4, column=1, padx=5, pady=2, sticky="ew")
        inquiry_date_input_frame.columnconfigure(0, weight=1)

        self.technical_quote_entries["Inquiry Date"] = tk.Entry(inquiry_date_input_frame, textvariable=self.technical_quote_inquiry_date_var, width=20, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black", state="readonly")
        self.technical_quote_entries["Inquiry Date"].grid(row=0, column=0, sticky="ew")
        self.btn_select_tech_inquiry_date = tk.Button(inquiry_date_input_frame, text="Select Date", command=lambda: self._open_date_picker(self.technical_quote_inquiry_date_var), font=("Arial", 9))
        self.btn_select_tech_inquiry_date.grid(row=0, column=1, padx=(5,0))

        tk.Label(top_details_frame, text="Quotation No.:", font=("Arial", 10), bg="white", fg="black").grid(row=5, column=0, padx=5, pady=2, sticky="w")
        self.technical_quote_entries["Quotation No."] = tk.Entry(top_details_frame, width=30, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black")
        self.technical_quote_entries["Quotation No."].grid(row=5, column=1, padx=5, pady=2, sticky="ew")
        self.technical_quote_entries["Quotation No."].bind("<FocusOut>", lambda e: self._save_technical_quote_data_auto())

        # Right Column
        tk.Label(top_details_frame, text="Page(s):", font=("Arial", 10), bg="white", fg="black").grid(row=0, column=2, padx=5, pady=2, sticky="w")
        self.technical_quote_entries["Page(s)"] = tk.Entry(top_details_frame, width=30, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black")
        self.technical_quote_entries["Page(s)"].grid(row=0, column=3, padx=5, pady=2, sticky="ew")
        self.technical_quote_entries["Page(s)"].bind("<FocusOut>", lambda e: self._save_technical_quote_data_auto())

        tk.Label(top_details_frame, text="Your Partner:", font=("Arial", 10), bg="white", fg="black").grid(row=1, column=2, padx=5, pady=2, sticky="w")
        self.technical_quote_entries["Your Partner"] = tk.Entry(top_details_frame, width=30, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black")
        self.technical_quote_entries["Your Partner"].grid(row=1, column=3, padx=5, pady=2, sticky="ew")
        self.technical_quote_entries["Your Partner"].bind("<FocusOut>", lambda e: self._save_technical_quote_data_auto())

        tk.Label(top_details_frame, text="Mobile No.:", font=("Arial", 10), bg="white", fg="black").grid(row=2, column=2, padx=5, pady=2, sticky="w")
        self.technical_quote_entries["Mobile No."] = tk.Entry(top_details_frame, width=30, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black")
        self.technical_quote_entries["Mobile No."].grid(row=2, column=3, padx=5, pady=2, sticky="ew")
        self.technical_quote_entries["Mobile No."].bind("<FocusOut>", lambda e: self._save_technical_quote_data_auto())

        tk.Label(top_details_frame, text="Fax No.:", font=("Arial", 10), bg="white", fg="black").grid(row=3, column=2, padx=5, pady=2, sticky="w")
        self.technical_quote_entries["Fax No."] = tk.Entry(top_details_frame, width=30, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black")
        self.technical_quote_entries["Fax No."].grid(row=3, column=3, padx=5, pady=2, sticky="ew")
        self.technical_quote_entries["Fax No"].bind("<FocusOut>", lambda e: self._save_technical_quote_data_auto())

        tk.Label(top_details_frame, text="E-mail (Partner):", font=("Arial", 10), bg="white", fg="black").grid(row=4, column=2, padx=5, pady=2, sticky="w")
        self.technical_quote_entries["E-mail (Partner)"] = tk.Entry(top_details_frame, width=30, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black")
        self.technical_quote_entries["E-mail (Partner)"].grid(row=4, column=3, padx=5, pady=2, sticky="ew")
        self.technical_quote_entries["E-mail (Partner)"].bind("<FocusOut>", lambda e: self._save_technical_quote_data_auto())

        # Date Entry with Select Date Button
        tk.Label(top_details_frame, text="Date:", font=("Arial", 10), bg="white", fg="black").grid(row=5, column=2, padx=5, pady=2, sticky="w")
        date_input_frame = tk.Frame(top_details_frame, bg="white")
        date_input_frame.grid(row=5, column=3, padx=5, pady=2, sticky="ew")
        date_input_frame.columnconfigure(0, weight=1)

        self.technical_quote_entries["Date"] = tk.Entry(date_input_frame, textvariable=self.technical_quote_date_var, width=20, font=("Arial", 10), bd=1, relief=tk.SOLID, bg="white", fg="black", state="readonly")
        self.technical_quote_entries["Date"].grid(row=0, column=0, sticky="ew")
        self.btn_select_tech_date = tk.Button(date_input_frame, text="Select Date", command=lambda: self._open_date_picker(self.technical_quote_date_var), font=("Arial", 9))
        self.btn_select_tech_date.grid(row=0, column=1, padx=(5,0))

        # Table Section
        table_frame = tk.Frame(self.technical_quote_frame, bg="white", padx=10, pady=10, bd=1, relief=tk.SOLID)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.technical_quote_table = ttk.Treeview(table_frame, columns=("Sr. No", "Description", "Technical Specs", "Unit Price INR", "Unit", "Total Price"), show="headings")
        self.technical_quote_table.heading("Sr. No", text="Sr. No")
        self.technical_quote_table.heading("Description", text="Description")
        self.technical_quote_table.heading("Technical Specs", text="Technical Specs")
        self.technical_quote_table.heading("Unit Price INR", text="Unit Price INR")
        self.technical_quote_table.heading("Unit", text="Unit")
        self.technical_quote_table.heading("Total Price", text="Total Price")

        self.technical_quote_table.column("Sr. No", width=50, anchor="center")
        self.technical_quote_table.column("Description", width=200, anchor="w")
        self.technical_quote_table.column("Technical Specs", width=200, anchor="w")
        self.technical_quote_table.column("Unit Price INR", width=120, anchor="e")
        self.technical_quote_table.column("Unit", width=80, anchor="center")
        self.technical_quote_table.column("Total Price", width=120, anchor="e")

        self.technical_quote_table.grid(row=0, column=0, sticky="nsew")

        tech_table_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.technical_quote_table.yview)
        self.technical_quote_table.configure(yscrollcommand=tech_table_scrollbar.set)
        tech_table_scrollbar.grid(row=0, column=1, sticky="ns")

        # Bind single-click event for in-cell editing
        self.technical_quote_table.bind("<Button-1>", self._on_tech_table_cell_click)

        # Table Action Buttons
        tech_table_buttons_frame = tk.Frame(self.technical_quote_frame, bg="#F0F0F0")
        tech_table_buttons_frame.grid(row=3, column=0, sticky="ew", pady=5, padx=20)
        tech_table_buttons_frame.columnconfigure(0, weight=1)
        tech_table_buttons_frame.columnconfigure(1, weight=1)

        tk.Button(tech_table_buttons_frame, text="Add Row", command=self._add_technical_quote_row, font=("Arial", 10)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        tk.Button(tech_table_buttons_frame, text="Delete Selected Row", command=self._delete_technical_quote_row, font=("Arial", 10)).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Generate PDF Button (at the bottom)
        bottom_buttons_frame = tk.Frame(self.technical_quote_frame, bg="#F0F0F0")
        bottom_buttons_frame.grid(row=4, column=0, sticky="ew", pady=10, padx=20)
        bottom_buttons_frame.columnconfigure(0, weight=1)
        
        tk.Button(bottom_buttons_frame, text="Generate Technical PDF", command=self._generate_technical_pdf, font=("Arial", 12)).grid(row=0, column=0, columnspan=2, padx=10, pady=10)

    def _show_technical_quote_screen(self):
        """
        Switches to the technical quote UI screen.
        Automatically saves project data and adds a new row if the table is empty.
        """
        self._disable_current_frame_buttons()
        self.status_bar.config(text="Loading Technical Quote UI...")
        self.master.update_idletasks()

        # 1. Auto-save current project data
        self._save_project() 

        # 2. Auto-populate technical quote table with customer/product details if it's a new entry
        if not self.current_project_data.get("technical_quote_data", {}).get("table_items"):
            customer_name = self.current_project_data["project_details"].get("customer_name", "N/A")
            
            # Get all selected product types from the saved product_requirements list
            selected_product_types_names = []
            for req in self.current_project_data.get("product_requirements", []):
                product_type = req.get("selected_product_type")
                if product_type and product_type != "Choose part type":
                    selected_product_types_names.append(product_type)
            
            product_types_str = ", ".join(selected_product_types_names) if selected_product_types_names else "No Product Selected"
            
            description_text = f"Customer: {customer_name} - Products: {product_types_str}"
            
            next_sr_no = 1
            new_row = {
                "Sr. No": next_sr_no,
                "Description": description_text,
                "Technical Specs": "Standard specifications as per product datasheet",
                "Unit Price INR": 0.0,
                "Unit": 0,
                "Total Price": 0.0
            }
            if "technical_quote_data" not in self.current_project_data:
                self.current_project_data["technical_quote_data"] = {"table_items": []}
            self.current_project_data["technical_quote_data"]["table_items"].append(new_row)
            self.technical_quote_table_data = self.current_project_data["technical_quote_data"]["table_items"]

        self.main_app_frame.pack_forget()
        self.quotation_setup_frame.pack_forget()
        self.project_selection_frame.pack_forget()
        self.commercial_quote_frame.pack_forget()
        self.master.update_idletasks()
        self.technical_quote_frame.pack(expand=True, fill='both')
        self.master.update_idletasks()
        self._populate_technical_quote_fields()
        self.status_bar.config(text="Technical Quote screen ready.")
        self._enable_current_frame_buttons()

    def _populate_technical_quote_fields(self):
        """Populates the technical quote UI fields from current_project_data."""
        technical_data = self.current_project_data.get("technical_quote_data", {})
        
        # Map internal keys to UI entry labels
        key_map = {
            "to": "To",
            "attn": "Attn.",
            "email_to": "E-mail (To)",
            "your_inquiry_ref": "Your Inquiry Ref.",
            "quotation_no_technical": "Quotation No.",
            "pages": "Page(s)",
            "your_partner": "Your Partner",
            "mobile_no": "Mobile No.",
            "fax_no": "Fax No.",
            "email_partner": "E-mail (Partner)",
        }

        for internal_key, ui_label in key_map.items():
            if ui_label in self.technical_quote_entries:
                entry_widget = self.technical_quote_entries[ui_label]
                entry_widget.delete(0, tk.END)
                value = technical_data.get(internal_key, "")
                if value:
                    entry_widget.insert(0, value)
        
        # Populate the date StringVars
        self.technical_quote_date_var.set(technical_data.get("date_technical", datetime.date.today().isoformat()))
        self.technical_quote_inquiry_date_var.set(technical_data.get("inquiry_date", datetime.date.today().isoformat()))

        self.technical_quote_table_data = technical_data.get("table_items", [])
        self._populate_technical_quote_table()

    def _populate_technical_quote_table(self):
        """Populates the Treeview table with data from self.technical_quote_table_data."""
        for item in self.technical_quote_table.get_children():
            self.technical_quote_table.delete(item)
        
        for item_data in self.technical_quote_table_data:
            self.technical_quote_table.insert("", "end", values=(
                item_data.get("Sr. No", ""),
                item_data.get("Description", ""),
                item_data.get("Technical Specs", ""),
                item_data.get("Unit Price INR", ""),
                item_data.get("Unit", ""),
                item_data.get("Total Price", "")
            ))

    def _add_technical_quote_row(self):
        """Adds a new empty row to the technical quote table."""
        next_sr_no = len(self.technical_quote_table_data) + 1
        new_row = {
            "Sr. No": next_sr_no,
            "Description": "",
            "Technical Specs": "",
            "Unit Price INR": 0.0,
            "Unit": 0,
            "Total Price": 0.0
        }
        self.technical_quote_table_data.append(new_row)
        self._populate_technical_quote_table()
        self._save_technical_quote_data_auto()

    def _delete_technical_quote_row(self):
        """Deletes the selected row from the technical quote table."""
        selected_item = self.technical_quote_table.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a row to delete.")
            return

        selected_index = -1
        for i, item_id in enumerate(self.technical_quote_table.get_children()):
            if item_id == selected_item[0]:
                selected_index = i
                break
        
        if selected_index != -1:
            del self.technical_quote_table_data[selected_index]
            # Re-number Sr. No after deletion
            for i, row in enumerate(self.technical_quote_table_data):
                row["Sr. No"] = i + 1
            self._populate_technical_quote_table()
            messagebox.showinfo("Row Deleted", "Selected row has been deleted.")
            self._save_technical_quote_data_auto()
        else:
            messagebox.showerror("Error", "Could not find selected row in data.")

    def _on_tech_table_cell_click(self, event):
        """Handles single-click on a Technical Treeview cell to enable editing."""
        # If an entry is already open, save it first
        if self._edit_tech_cell_entry:
            if self._edit_tech_cell_entry.winfo_containing(event.x_root, event.y_root) == self._edit_tech_cell_entry:
                return
            self._save_tech_table_cell_edit()

        region = self.technical_quote_table.identify_region(event.x, event.y)
        if region != "cell":
            return

        column = self.technical_quote_table.identify_column(event.x)
        item = self.technical_quote_table.identify_row(event.y)

        if not item or not column:
            return

        # Get column name from its identifier
        column_name = self.technical_quote_table.heading(column, "text")

        # Only allow editing for specific columns
        editable_columns = ["Description", "Technical Specs", "Unit Price INR", "Unit", "Total Price"]
        if column_name not in editable_columns:
            return

        # Get current value
        col_idx = int(column.replace('#', '')) - 1
        current_values = self.technical_quote_table.item(item, "values")
        current_value = current_values[col_idx] if col_idx < len(current_values) else ""

        # Get bounding box of the cell
        x, y, width, height = self.technical_quote_table.bbox(item, column)

        # Create a temporary Entry widget
        self._edit_tech_cell_entry = tk.Entry(self.technical_quote_table,
                                         font=("Arial", 10),
                                         bd=0, relief=tk.FLAT,
                                         bg="white", fg="black")
        
        # Store references for saving
        self._edit_tech_cell_item = item
        self._edit_tech_cell_column = column

        # Bind Enter key to save
        self._edit_tech_cell_entry.bind("<Return>", lambda e: self._save_tech_table_cell_edit())
        
        # Apply numeric validation if it's a numeric column
        if column_name in ["Unit Price INR", "Unit", "Total Price"]:
            self._edit_tech_cell_entry.config(validate="key", validatecommand=(self.vcmd_numeric, '%P'))

        # Place the entry and set focus
        self._edit_tech_cell_entry.place(x=x, y=y, width=width, height=height)
        self._edit_tech_cell_entry.insert(0, str(current_value))
        self._edit_tech_cell_entry.focus_set()

        # Bind FocusOut to save
        self.master.after_idle(self._bind_tech_focus_out_to_edit_entry)

    def _bind_tech_focus_out_to_edit_entry(self):
        """Helper to bind FocusOut to the active technical edit entry after it's fully ready."""
        if self._edit_tech_cell_entry and self._edit_tech_cell_entry.winfo_exists():
            self._edit_tech_cell_entry.bind("<FocusOut>", lambda e: self._save_tech_table_cell_edit())

    def _save_tech_table_cell_edit(self, event=None):
        """Saves the edited technical cell value back to the data and updates the Treeview."""
        if not self._edit_tech_cell_entry or not self._edit_tech_cell_entry.winfo_exists():
            return

        new_value = self._edit_tech_cell_entry.get().strip()
        item_id = self._edit_tech_cell_item
        column_id = self._edit_tech_cell_column
        
        # Destroy the entry widget
        self._edit_tech_cell_entry.destroy()
        self._edit_tech_cell_entry = None
        self._edit_tech_cell_item = None
        self._edit_tech_cell_column = None

        if not item_id or not column_id:
            return

        # Get column name from its identifier
        column_name = self.technical_quote_table.heading(column_id, "text")

        # Find the row index in our actual data list
        row_index = -1
        for i, tree_item_id in enumerate(self.technical_quote_table.get_children()):
            if tree_item_id == item_id:
                row_index = i
                break

        if row_index == -1:
            return

        # Update the data in self.technical_quote_table_data
        current_row_data = self.technical_quote_table_data[row_index]

        # Handle numeric columns and calculations
        if column_name in ["Unit Price INR", "Unit", "Total Price"]:
            try:
                if column_name == "Unit":
                    new_value = int(new_value) if new_value else 0
                else:
                    new_value = float(new_value) if new_value else 0.0
            except ValueError:
                messagebox.showerror("Input Error", f"Please enter a valid number for '{column_name}'.")
                new_value = current_row_data.get(column_name, 0 if column_name == "Unit" else 0.0)
        
        current_row_data[column_name] = new_value

        # Recalculate Total Price if Unit Price or Unit changed
        if column_name in ["Unit Price INR", "Unit"]:
            unit_price = current_row_data.get("Unit Price INR", 0.0)
            unit_quantity = current_row_data.get("Unit", 0)
            
            try:
                unit_price = float(unit_price)
            except ValueError:
                unit_price = 0.0
            try:
                unit_quantity = int(unit_quantity)
            except ValueError:
                unit_quantity = 0

            total_price = unit_price * unit_quantity
            current_row_data["Total Price"] = round(total_price, 2)

        # Update the Treeview display
        self.technical_quote_table.item(item_id, values=(
            current_row_data.get("Sr. No", ""),
            current_row_data.get("Description", ""),
            current_row_data.get("Technical Specs", ""),
            current_row_data.get("Unit Price INR", ""),
            current_row_data.get("Unit", ""),
            current_row_data.get("Total Price", "")
        ))
        
        self._save_technical_quote_data_auto()

    def _save_technical_quote_data_auto(self):
        """
        Automatically saves the current data from the technical quote UI and table
        to the project data. Called on various UI events.
        """
        # Collect data from entry fields
        technical_data_to_save = {}
        key_map = { 
            "To": "to",
            "Attn.": "attn",
            "E-mail (To)": "email_to",
            "Your Inquiry Ref.": "your_inquiry_ref",
            "Quotation No.": "quotation_no_technical",
            "Page(s)": "pages",
            "Your Partner": "your_partner",
            "Mobile No.": "mobile_no",
            "Fax No.": "fax_no",
            "E-mail (Partner)": "email_partner",
        }
        for ui_label, entry_widget in self.technical_quote_entries.items():
            if ui_label not in ["Date", "Inquiry Date"]:
                mapped_key = key_map.get(ui_label, ui_label.lower().replace(" ", "_").replace(".", ""))
                technical_data_to_save[mapped_key] = entry_widget.get().strip()
        
        # Add the dates from their StringVars
        technical_data_to_save["date_technical"] = self.technical_quote_date_var.get()
        technical_data_to_save["inquiry_date"] = self.technical_quote_inquiry_date_var.get()

        # Save table data
        technical_data_to_save["table_items"] = self.technical_quote_table_data
        self.current_project_data["technical_quote_data"] = technical_data_to_save
        self._save_project()

    def _generate_technical_pdf(self):
        """Generates the technical PDF based on current_project_data."""
        # Ensure any active cell edit is saved before generating PDF
        if self._edit_tech_cell_entry:
            self._save_tech_table_cell_edit()
            self._save_technical_quote_data_auto()

        self._disable_current_frame_buttons()
        self.status_bar.config(text="Generating Technical PDF...")
        self.master.update_idletasks()

        try:
            # Get data from your current_project_data
            technical_data = self.current_project_data.get("technical_quote_data", {})
            project_details = self.current_project_data.get("project_details", {})
            table_items = technical_data.get("table_items", [])

            # Define the PDF file name
            quotation_num = project_details.get("quotation_number", "NO_QUOTE")
            customer_name = project_details.get("customer_name", "Customer").replace(' ', '_')
            output_pdf_filename = f"Technical_Quotation_{quotation_num}_{customer_name}.pdf"
            script_dir = os.path.dirname(__file__)
            output_pdf_path = os.path.join(script_dir, output_pdf_filename)

            doc = SimpleDocTemplate(output_pdf_path, pagesize=A4,
                                    rightMargin=inch, leftMargin=inch,
                                    topMargin=inch, bottomMargin=inch)
            
            styles = getSampleStyleSheet()
            styles.add(ParagraphStyle(name='CustomHeading1', fontSize=18, leading=22, alignment=TA_CENTER, fontName='Helvetica-Bold'))
            styles.add(ParagraphStyle(name='NormalLeft', fontSize=10, leading=12, alignment=TA_LEFT))
            styles.add(ParagraphStyle(name='BoldLeft', fontSize=10, leading=12, alignment=TA_LEFT, fontName='Helvetica-Bold'))
            styles.add(ParagraphStyle(name='TableDescription', fontSize=10, leading=12, alignment=TA_LEFT, wordWrap='CJK'))

            Story = []

            # --- HEADER ---
            header_elements = []
            if os.path.exists(self.logo_path):
                header_elements.append(ReportLabImage(self.logo_path, width=1.2*inch, height=0.6*inch)) 
            else:
                header_elements.append(Paragraph("[LOGO]", styles['NormalLeft']))

            header_elements.append(Paragraph("<b>RINGSPANN Power Transmission India Pvt. Ltd.</b>", styles['CustomHeading1']))
            
            header_table_data = [[header_elements[1], header_elements[0]]] 
            header_table = Table(header_table_data, colWidths=[5.5*inch, 1.5*inch])
            header_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (0,0), 'LEFT'),
                ('ALIGN', (1,0), (1,0), 'RIGHT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 10),
                ('LEFTPADDING', (0,0), (0,0), 0),
                ('RIGHTPADDING', (1,0), (1,0), 0),
            ]))
            Story.append(header_table)
            Story.append(Paragraph("Technical Quotation", styles['CustomHeading1']))
            Story.append(Spacer(1, 0.3*inch))

            # --- TOP DETAILS ---
            details_data = [
                ["To:", technical_data.get("to", ""), "Page(s):", technical_data.get("pages", "")],
                ["Attn.:", technical_data.get("attn", ""), "Your Partner:", technical_data.get("your_partner", "")],
                ["E-mail:", technical_data.get("email_to", ""), "Mobile No.:", technical_data.get("mobile_no", "")],
                ["Your Inquiry Ref.:", technical_data.get("your_inquiry_ref", ""), "Fax No.:", technical_data.get("fax_no", "")],
                ["Inquiry Date:", technical_data.get("inquiry_date", ""), "E-mail:", technical_data.get("email_partner", "")],
                ["Quotation No.:", project_details.get("quotation_number", ""), "Date:", technical_data.get("date_technical", datetime.date.today().isoformat())]
            ]

            colWidths = [1.5*inch, 2.5*inch, 1.5*inch, 2.5*inch]
            details_table = Table(details_data, colWidths=colWidths)
            details_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('GRID', (0,0), (-1,-1), 0.25, black),
                ('BOX', (0,0), (-1,-1), 0.25, black),
            ]))
            Story.append(details_table)
            Story.append(Spacer(1, 0.2*inch))

            # "Dear Sir" line and dynamic inquiry date
            Story.append(Paragraph(f"Dear Sir,", styles['NormalLeft']))
            inquiry_date_display = technical_data.get('inquiry_date', '_______')
            Story.append(Paragraph(f"This is with reference to your technical inquiry dated on <u>{inquiry_date_display}</u>, we are pleased to offer as under: -", styles['NormalLeft']))
            Story.append(Spacer(1, 0.2*inch))

            # --- TABLE OF ITEMS ---
            table_header = ["Sr. No", "Description", "Technical Specs", "Unit Price INR", "Unit", "Total Price"]
            table_rows = [table_header]

            for item in table_items:
                description_para = Paragraph(str(item.get("Description", "")), styles['TableDescription'])
                specs_para = Paragraph(str(item.get("Technical Specs", "")), styles['TableDescription'])
                table_rows.append([
                    item.get("Sr. No", ""),
                    description_para,
                    specs_para,
                    item.get("Unit Price INR", ""),
                    item.get("Unit", ""),
                    item.get("Total Price", "")
                ])
            
            # Define column widths for the technical items table
            item_col_widths = [0.5*inch, 2.2*inch, 2.2*inch, 1.0*inch, 0.6*inch, 1.0*inch]
            items_table = Table(table_rows, colWidths=item_col_widths)
            items_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), (0.9,0.9,0.9)),
                ('TEXTCOLOR', (0,0), (-1,0), black),
                ('ALIGN', (0,0), (-1,0), 'CENTER'),
                ('ALIGN', (3,1), (-1,-1), 'RIGHT'),
                ('ALIGN', (0,1), (0,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('TOPPADDING', (0,0), (-1,0), 6),
                ('GRID', (0,0), (-1,-1), 0.25, black),
                ('BOX', (0,0), (-1,-1), 0.25, black),
            ]))
            Story.append(items_table)
            Story.append(Spacer(1, 0.3*inch))

            # --- TECHNICAL TERMS ---
            Story.append(Paragraph("<b>Important Technical Terms</b>", styles['BoldLeft']))
            Story.append(Paragraph("1) All products conform to international standards (ISO, DIN, AGMA)", styles['NormalLeft']))
            Story.append(Paragraph("2) Technical specifications as per enclosed datasheets", styles['NormalLeft']))
            Story.append(Paragraph("3) Installation and commissioning support available", styles['NormalLeft']))
            Story.append(Paragraph("4) Warranty: 12 months from commissioning or 18 months from invoice", styles['NormalLeft']))
            Story.append(Paragraph("5) Delivery: 8-12 weeks from technically clear order", styles['NormalLeft']))
            Story.append(Spacer(1, 0.2*inch))

            Story.append(Paragraph("We are looking forward to your order.", styles['NormalLeft']))
            Story.append(Spacer(1, 0.3*inch))

            Story.append(Paragraph("Yours sincerely,", styles['NormalLeft']))
            Story.append(Paragraph("<b>RINGSPANN Power Transmission India Pvt. Ltd.</b>", styles['BoldLeft']))

            # Build the PDF
            doc.build(Story)

            self.status_bar.config(text=f"Technical PDF generated: {output_pdf_filename}")
            messagebox.showinfo("PDF Generated", f"Technical Quotation PDF saved to:\n{output_pdf_path}")
            
            # Optionally open the generated PDF
            threading.Thread(target=self._open_file_with_default_app, args=(output_pdf_filename,)).start()

        except ImportError:
            messagebox.showerror("Error", "ReportLab library not found. Please install it using 'pip install reportlab'.")
        except Exception as e:
            messagebox.showerror("PDF Generation Error", f"Failed to generate PDF: {e}")
            self.status_bar.config(text="PDF generation failed.")
        finally:
            self._enable_current_frame_buttons()

    def _open_technical_quote_file(self):
        """
        Opens the Technical Quotation screen instead of opening a file.
        Automatically saves project data before showing the technical quote screen.
        """
        self._save_project()
        self._show_technical_quote_screen()

    # Add placeholder methods for missing functionality
    def _get_fernet_cipher(self):
        """Placeholder for encryption functionality"""
        return None
    
    def _load_ringspann_logo(self):
        """Placeholder for logo loading"""
        pass
    
    def _configure_ttk_styles(self):
        """Placeholder for style configuration"""
        pass
    
    def _build_auth_ui(self):
        """Placeholder for auth UI"""
        pass
    
    def _build_project_selection_ui(self):
        """Placeholder for project selection UI"""
        pass
    
    def _build_quotation_setup_ui(self):
        """Placeholder for quotation setup UI"""
        pass
    
    def _build_main_app_ui(self):
        """Placeholder for main app UI"""
        pass
    
    def _build_commercial_quote_ui(self):
        """Placeholder for commercial quote UI"""
        pass
    
    def _get_next_requirement_number(self):
        """Placeholder for requirement numbering"""
        return 1
    
    def _validate_numeric_input(self, P):
        """Placeholder for numeric validation"""
        return True
    
    def _save_project(self):
        """Placeholder for save functionality"""
        pass
    
    def _disable_current_frame_buttons(self):
        """Placeholder for button disabling"""
        pass
    
    def _enable_current_frame_buttons(self):
        """Placeholder for button enabling"""
        pass
    
    def _show_main_app_screen(self):
        """Placeholder for showing main screen"""
        pass
    
    def _open_file_with_default_app(self, filename):
        """Placeholder for opening files"""
        pass
    
    def _open_date_picker(self, date_var):
        """Opens the DatePicker dialog."""
        DatePicker(self.master, date_var, self._save_technical_quote_data_auto)

# --- Main Application Entry Point ---
if __name__ == "__main__":
    print("DEBUG: Application starting...")
    try:
        root = tk.Tk()
        root.withdraw()
        print("DEBUG: Tkinter root window created and withdrawn.")

        app = RingspanApp(root)
        print("DEBUG: RingspanApp instance created.")

        # Ensure database connection is closed when the app exits
        root.protocol("WM_DELETE_WINDOW", lambda: (app.db_manager.close(), root.destroy()))

        if root.winfo_exists():
            root.update_idletasks()
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            window_width = 1024
            window_height = 768
            x_cordinate = int((screen_width/2) - (window_width/2))
            y_cordinate = int((screen_height/2) - (window_height/2))
            root.geometry(f"{window_width}x{window_height}+{x_cordinate}+{y_cordinate}")
            print(f"DEBUG: Setting window geometry to {window_width}x{window_height} at ({x_cordinate},{y_cordinate}).")
            root.deiconify()
            print("DEBUG: Mainloop started.")
            root.mainloop()
            print("DEBUG: Mainloop exited.")
        else:
            print("DEBUG: Root window destroyed during app initialization (e.g., encryption or database error).")
    except Exception as e:
        print(f"ERROR: An unhandled exception occurred during application startup: {e}")
        messagebox.showerror("Application Error", f"An unexpected error occurred during startup: {e}")