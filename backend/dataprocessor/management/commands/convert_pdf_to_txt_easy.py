# dataprocessor/management/commands/convert_pdf_to_txt_easy.py

from django.core.management.base import BaseCommand
from django.conf import settings
import os
from pdfminer.high_level import extract_text
import logging

class Command(BaseCommand):
    help = 'Convert PDF files to TXT in the backend/data/pdf folder and its subfolders'

    def handle(self, *args, **options):
        input_dir = os.path.join(settings.BASE_DIR, 'data', 'pdf')
        output_base_dir = os.path.join(settings.BASE_DIR, 'data', 'txt')

        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)

        self.process_directory(input_dir, output_base_dir, logger)

        self.stdout.write(self.style.SUCCESS('PDF to TXT conversion completed'))

    def process_directory(self, input_dir, output_base_dir, logger):
        for root, dirs, files in os.walk(input_dir):
            # 創建對應的輸出目錄
            relative_path = os.path.relpath(root, input_dir)
            output_dir = os.path.join(output_base_dir, relative_path)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            for file in files:
                if file.endswith('.pdf'):
                    pdf_path = os.path.join(root, file)
                    txt_path = os.path.join(output_dir, file[:-4] + '.txt')

                    if os.path.exists(txt_path):
                        logger.info(f"Skipping {file}: TXT file already exists")
                        continue

                    try:
                        text = extract_text(pdf_path)
                        with open(txt_path, 'w', encoding='utf-8') as txt_file:
                            txt_file.write(text)
                        logger.info(f"Converted {pdf_path} to {txt_path}")
                    except Exception as e:
                        logger.error(f"Error converting {pdf_path}: {str(e)}")

# 使用方法：python manage.py convert_pdf_to_txt_easy