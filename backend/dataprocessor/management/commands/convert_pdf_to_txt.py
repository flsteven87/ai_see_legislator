# dataprocessor/management/commands/convert_pdf_to_txt.py

from django.core.management.base import BaseCommand
from django.conf import settings
import os
import marker
import logging

class Command(BaseCommand):
    help = 'Convert PDF files to TXT in the data/pdf folder and its subfolders'

    def handle(self, *args, **options):
        input_dir = settings.MEDIA_ROOT
        output_base_dir = os.path.join(settings.BASE_DIR, 'backend', 'data', 'txt')

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
                        # 使用 Marker 的 Python 接口進行 PDF 到 TXT 的轉換
                        text = self.convert_pdf_to_txt(pdf_path)
                        with open(txt_path, 'w', encoding='utf-8') as txt_file:
                            txt_file.write(text)
                        logger.info(f"Converted {pdf_path} to {txt_path}")
                    except Exception as e:
                        logger.error(f"Error converting {pdf_path}: {str(e)}")

    def convert_pdf_to_txt(self, pdf_path):
        # 使用 marker 進行 PDF 到 Markdown 的轉換
        markdown_text = marker.convert_single_pdf(pdf_path)
        return markdown_text

# 使用方法：python manage.py convert_pdf_to_txt