import os
import re
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = '合併立法院公報 MD 文件'

    def handle(self, *args, **options):
        md_dir = os.path.join(settings.BASE_DIR, 'data', 'md')
        output_dir = os.path.join(settings.BASE_DIR, 'data', 'merged_md')

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        for folder_name in os.listdir(md_dir):
            if folder_name.startswith('第') and '期公報' in folder_name:
                folder_path = os.path.join(md_dir, folder_name)
                if os.path.isdir(folder_path):
                    self.merge_md_files(folder_path, folder_name, output_dir)

    def merge_md_files(self, folder_path, folder_name, output_dir):
        md_files = []
        for subfolder_name in os.listdir(folder_path):
            subfolder_path = os.path.join(folder_path, subfolder_name)
            if os.path.isdir(subfolder_path):
                for file_name in os.listdir(subfolder_path):
                    if file_name.endswith('.md'):
                        page_range = self.extract_page_range(subfolder_name)
                        md_files.append((page_range, os.path.join(subfolder_path, file_name)))

        if not md_files:
            self.stdout.write(self.style.WARNING(f'文件夾 {folder_name} 中沒有找到 MD 文件'))
            return

        md_files.sort(key=lambda x: x[0][0])  # 按起始頁碼排序

        output_file = os.path.join(output_dir, f'{folder_name}.md')
        with open(output_file, 'w', encoding='utf-8') as outfile:
            for _, file_path in md_files:
                with open(file_path, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read())
                    outfile.write('\n\n')  # 在每個文件之間添加空行

        self.stdout.write(self.style.SUCCESS(f'成功合併 {folder_name} 中的 {len(md_files)} 個 MD 文件'))

    def extract_page_range(self, folder_name):
        match = re.search(r'p(\d+)-p(\d+)', folder_name)
        if match:
            return int(match.group(1)), int(match.group(2))
        return 0, 0  # 如果無法提取頁碼範圍，則返回 (0, 0)

# 使用方法：python manage.py merge_md_files