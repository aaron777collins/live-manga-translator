import tkinter as tk
from tkinter import ttk
import cv2
import pytesseract
from googletrans import Translator
import pyautogui
import pygetwindow as gw
from PIL import Image, ImageTk
import numpy as np
import threading
import time

class ScreenTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Screen Translator")

        self.translator = Translator()
        self.running = False
        self.languages_to_iterate = {'Japanese (Vertical)': 'jpn_vert',
                                     'Chinese (Simplified)': 'chi_sim_vert',
                                     'Chinese (Traditional)': 'chi_tra_vert'}
        self.current_language_index = 0
        self.language_list = list(self.languages_to_iterate.keys())  # Define this before create_widgets()

        self.create_widgets()  # Now create_widgets() can correctly reference self.language_list

        self.live_feed_window = tk.Toplevel(self.root)
        self.live_feed_window.title("Live Feed")
        self.live_feed_label = tk.Label(self.live_feed_window)
        self.live_feed_label.pack()

        self.translated_window = tk.Toplevel(self.root)
        self.translated_window.title("Translated Image")
        self.translated_label = tk.Label(self.translated_window)
        self.translated_label.pack()

    def create_widgets(self):
        self.window_list = ttk.Combobox(self.root, postcommand=self.preview_window)
        self.window_list.grid(row=0, column=0, padx=10, pady=10)

        self.language_var = tk.StringVar()
        self.language_options = ttk.Combobox(self.root, textvariable=self.language_var,
                                             values=self.language_list)
        self.language_options.grid(row=0, column=1, padx=10, pady=10)
        self.language_options.current(0)  # Default to Japanese

        self.iterate_languages_var = tk.BooleanVar()
        self.iterate_languages_checkbox = tk.Checkbutton(self.root, text="Iterate Through Languages",
                                                         variable=self.iterate_languages_var, onvalue=True, offvalue=False)
        self.iterate_languages_checkbox.grid(row=0, column=2, padx=10, pady=10)

        # Speed control slider
        self.speed_var = tk.DoubleVar()
        self.speed_var.set(0.5)  # Default speed
        self.speed_slider = tk.Scale(self.root, from_=0.1, to=4.0, resolution=0.1,
                                     orient='horizontal', label='Update Speed (s)',
                                     variable=self.speed_var)
        self.speed_slider.grid(row=2, column=0, columnspan=2, sticky='ew', padx=10, pady=10)

        self.start_button = ttk.Button(self.root, text="Start", command=self.start_translation)
        self.start_button.grid(row=1, column=0, padx=10, pady=10)
        self.stop_button = ttk.Button(self.root, text="Stop", command=self.stop_translation)
        self.stop_button.grid(row=1, column=1, padx=10, pady=10)
        self.refresh_window_list()

    def refresh_window_list(self):
        windows = gw.getAllTitles()
        self.window_list['values'] = windows

    def preview_window(self):
        selected_title = self.window_list.get()
        if selected_title:
            try:
                window = gw.getWindowsWithTitle(selected_title)[0]
                if not window.isActive:
                    window.activate()
                preview = pyautogui.screenshot(region=(
                    window.left, window.top, window.width, window.height))
                preview = cv2.cvtColor(np.array(preview), cv2.COLOR_RGB2BGR)
                preview = cv2.resize(preview, (320, 240))
                img = Image.fromarray(preview)
                imgtk = ImageTk.PhotoImage(image=img)
                self.live_feed_label.imgtk = imgtk
                self.live_feed_label.configure(image=imgtk)
            except Exception as e:
                print(f"Window activation failed: {e}")

    def start_translation(self):
        self.running = True
        threading.Thread(target=self.translate_screen, daemon=True).start()

    def stop_translation(self):
        self.running = False

    def translate_screen(self):
        while self.running:
            selected_title = self.window_list.get()
            if selected_title:
                try:
                    window = gw.getWindowsWithTitle(selected_title)[0]
                    if not window.isActive:
                        window.activate()
                    screenshot = pyautogui.screenshot(region=(
                        window.left, window.top, window.width, window.height))
                    screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
                    self.update_live_feed(screenshot)
                    ocr_data = self.get_ocr_data(screenshot, lang=self.languages_to_iterate[self.language_list[self.current_language_index]])
                    grouped_text_data = self.group_text_by_proximity(ocr_data)
                    translated_image = self.overlay_translated_text(screenshot, grouped_text_data)
                    self.update_translated_feed(translated_image)

                    if self.iterate_languages_var.get():
                        self.current_language_index = (self.current_language_index + 1) % len(self.language_list)
                except Exception as e:
                    print(f"Error during translation: {e}")
            time.sleep(self.speed_var.get())  # Use the speed setting

    def get_ocr_data(self, image, lang):
        ocr_data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
        return ocr_data

    def group_text_by_proximity(self, ocr_data):
        grouped_text_data = []
        n_boxes = len(ocr_data['text'])
        for i in range(n_boxes):
            if int(ocr_data['conf'][i]) > 60:  # Confidence threshold
                (x, y, w, h) = (ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i])
                text = ocr_data['text'][i]
                grouped_text_data.append((text, x, y, w, h))
        return grouped_text_data

    def overlay_translated_text(self, image, grouped_text_data):
        for text, x, y, w, h in grouped_text_data:
            if text.strip():  # Ensure the text is not empty
                try:
                    translation = self.translator.translate(text, dest='en')
                    if translation and hasattr(translation, 'text'):
                        translated_text = translation.text
                        cv2.rectangle(image, (x, y), (x + w, y + h), (255, 255, 255), -1)
                        cv2.putText(image, translated_text, (x, y + h), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
                    else:
                        print("Translation failed or returned None.")
                except Exception as e:
                    print(f"Translation failed: {e}")
            else:
                print("Empty text skipped.")
        return image

    def update_live_feed(self, image):
        img = Image.fromarray(image)
        imgtk = ImageTk.PhotoImage(image=img)
        self.live_feed_label.imgtk = imgtk
        self.live_feed_label.configure(image=imgtk)

    def update_translated_feed(self, image):
        img = Image.fromarray(image)
        imgtk = ImageTk.PhotoImage(image=img)
        self.translated_label.imgtk = imgtk
        self.translated_label.configure(image=imgtk)

root = tk.Tk()
app = ScreenTranslatorApp(root)
root.mainloop()
